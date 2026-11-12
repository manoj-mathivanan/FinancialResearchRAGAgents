"""Build and query a local keyword index for Infosys Q3 earnings calls."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import subprocess

from findoc.tools.transcripts import DEFAULT_PERIOD, NSE_ARCHIVE, TRANSCRIPTS, read_call_pages


def build_index(pdf: Path, database: Path) -> int:
    period, pages = read_call_pages(pdf)
    digest = sha256(pdf.read_bytes()).hexdigest()
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS earnings_call USING fts5(
                body,
                pdf_page UNINDEXED,
                source_sha256 UNINDEXED,
                tokenize='porter unicode61'
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS earnings_sources (
                period_end TEXT PRIMARY KEY,
                source_sha256 TEXT UNIQUE NOT NULL
            )
        """)
        connection.execute(
            """
            DELETE FROM earnings_call WHERE source_sha256 IN (
                SELECT source_sha256 FROM earnings_sources WHERE period_end = ?
            ) OR (? = ? AND source_sha256 NOT IN (
                SELECT source_sha256 FROM earnings_sources
            ))
            """,
            (period, period, DEFAULT_PERIOD),
        )
        connection.execute(
            """
            INSERT INTO earnings_sources VALUES (?, ?)
            ON CONFLICT(period_end) DO UPDATE SET source_sha256 = excluded.source_sha256
            """,
            (period, digest),
        )
        connection.executemany(
            "INSERT INTO earnings_call VALUES (?, ?, ?)",
            [(body, page, digest) for page, body in pages],
        )
    return len(pages)


def search(database: Path, query: str, limit: int = 3, period_end: str | None = None) -> list[dict]:
    terms = re.findall(r"[^\W_]+", query.casefold())
    if not terms:
        raise ValueError("Enter at least one search term.")
    if not 1 <= limit <= 20:
        raise ValueError("Search limit must be between 1 and 20.")
    expression = " AND ".join(f'"{term}"' for term in terms)
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        has_sources = connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name = 'earnings_sources'"
        ).fetchone()
        # The first version only indexed FY2026 and had no separate source metadata.
        join = (
            "LEFT JOIN earnings_sources USING (source_sha256)" if has_sources else ""
        )
        source_period = "COALESCE(earnings_sources.period_end, ?)" if has_sources else "?"
        rows = connection.execute(
            f"""
            SELECT pdf_page, source_sha256, snippet(earnings_call, 0, '[', ']', ' ... ', 48),
                   {source_period} AS indexed_period
            FROM earnings_call
            {join}
            WHERE earnings_call MATCH ?
            AND (? IS NULL OR indexed_period = ?)
            ORDER BY bm25(earnings_call), indexed_period, pdf_page
            LIMIT ?
            """,
            (DEFAULT_PERIOD, expression, period_end, period_end, limit),
        ).fetchall()
    return [
        {
            "company": "INFY",
            "period_end": period,
            "document_type": "earnings_call",
            "pdf_page": page,
            "transcript_page": page - TRANSCRIPTS[period].cover_page + 1,
            "source_url": f"{NSE_ARCHIVE}{TRANSCRIPTS[period].filename}#page={page}",
            "source_sha256": digest,
            "snippet": snippet,
        }
        for page, digest, snippet, period in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="Index a local copy of the NSE filing.")
    index.add_argument("pdf", type=Path)
    index.add_argument("database", type=Path)
    query = commands.add_parser("search", help="Search the indexed transcript.")
    query.add_argument("database", type=Path)
    query.add_argument("keywords")
    query.add_argument("--limit", type=int, default=3)
    query.add_argument("--period-end", choices=sorted(TRANSCRIPTS), help="Filter to one quarter end.")
    args = parser.parse_args()
    try:
        if args.command == "index":
            if args.pdf.resolve() == args.database.resolve():
                raise ValueError("Use separate paths for the PDF and search database.")
            count = build_index(args.pdf, args.database)
            print(f"Indexed {count} earnings-call pages in {args.database}.")
        else:
            print(json.dumps(search(args.database, args.keywords, args.limit, args.period_end), indent=2))
    except FileNotFoundError as exc:
        parser.exit(1, f"Evidence command failed: {exc}. Check the file paths and install pdftotext.\n")
    except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Evidence command failed: {exc}\n")


if __name__ == "__main__":
    main()
