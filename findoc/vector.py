"""Embed transcript passages and retrieve evidence with PostgreSQL and pgvector."""

import argparse
import asyncio
from contextlib import contextmanager
from functools import partial
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from uuid import NAMESPACE_URL, uuid5

import psycopg
from psycopg.types.json import Json
from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings
from langchain_postgres import Column, PGEngine, PGVectorStore
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from findoc.tools import transcripts


MODEL = "BAAI/bge-small-en-v1.5"
INDEX_VERSION = MODEL + ":words140-overlap30:v1"
TABLE = "transcript_vectors"
FILTER_COLUMNS = ("company", "period_end", "index_version")


@contextmanager
def vector_engine(dsn: str):
    # PGEngine starts a background async loop. Psycopg needs a selector loop on Windows.
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    engine = PGEngine.from_connection_string(make_url(dsn).set(drivername="postgresql+psycopg"))
    try:
        yield engine
    finally:
        asyncio.run(engine.close())


def open_store(engine: PGEngine, model: Embeddings) -> PGVectorStore:
    return PGVectorStore.create_sync(engine, model, TABLE, metadata_columns=list(FILTER_COLUMNS))


class LocalEmbeddings(Embeddings):
    """Expose the existing FastEmbed model through LangChain's interface."""

    def __init__(self):
        self.model = TextEmbedding(MODEL)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self.model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(self.model.query_embed(text)).tolist()


def passages(text: str):
    words = text.split()
    for start in range(0, len(words), 110):
        yield " ".join(words[start:start + 140])
        if start + 140 >= len(words):
            break


def index_pdf(connection, pdf: Path, model: LocalEmbeddings) -> tuple[str, int]:
    period, pages = transcripts.read_call_pages(pdf)
    digest = sha256(pdf.read_bytes()).hexdigest()
    chunks = [
        (page, ordinal, passage)
        for page, text in pages
        for ordinal, passage in enumerate(passages(text), 1)
    ]
    embeddings = model.embed_documents([chunk[2] for chunk in chunks])
    transcript = transcripts.TRANSCRIPTS[period]
    with connection.transaction():
        # The library's bulk writer commits each row. Replace the quarter atomically.
        connection.execute(
            f"DELETE FROM {TABLE} WHERE company = %s AND period_end = %s AND index_version = %s",
            ("INFY", period, INDEX_VERSION),
        )
        with connection.cursor() as cursor:
            cursor.executemany(f"""
                INSERT INTO {TABLE} (
                    langchain_id, company, period_end, index_version, content, embedding, langchain_metadata
                ) VALUES (%s, %s, %s, %s, %s, %s::vector, %s)
            """, [
                (
                    uuid5(NAMESPACE_URL, f"INFY:{period}:{INDEX_VERSION}:{page}:{ordinal}"),
                    "INFY", period, INDEX_VERSION, passage,
                    json.dumps(embedding, allow_nan=False),
                    Json({
                        "pdf_page": page,
                        "passage_number": ordinal,
                        "transcript_page": page - transcript.cover_page + 1,
                        "source_url": f"{transcripts.NSE_ARCHIVE}{transcript.filename}#page={page}",
                        "source_sha256": digest,
                    }),
                )
                for (page, ordinal, passage), embedding in zip(chunks, embeddings, strict=True)
            ])
    return period, len(chunks)


def search(store: PGVectorStore, model: LocalEmbeddings, question: str, period: str, limit: int = 3):
    if not question.strip():
        raise ValueError("Enter a question.")
    if limit < 1:
        raise ValueError("Search limit must be positive.")
    query_vector = model.embed_query(question)
    filters = {"company": "INFY", "period_end": period, "index_version": INDEX_VERSION}
    candidates = limit
    while True:
        matches = store.similarity_search_with_score_by_vector(query_vector, k=candidates, filter=filters)
        # Keep the best passage from each page, even when overlapping chunks rank together.
        pages = {}
        for document, distance in matches:
            metadata = document.metadata
            pages.setdefault(metadata["pdf_page"], {
                **{key: metadata[key] for key in (
                    "company", "period_end", "pdf_page", "transcript_page", "source_url", "source_sha256"
                )},
                "body": document.page_content,
                "cosine_distance": distance,
            })
        if len(pages) >= limit or len(matches) < candidates:
            return list(pages.values())[:limit]
        candidates *= 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="Index one or more local transcripts.")
    index.add_argument("pdfs", type=Path, nargs="+")
    query = commands.add_parser("search", help="Find the three most similar evidence pages.")
    query.add_argument("question")
    query.add_argument("--period-end", choices=sorted(transcripts.TRANSCRIPTS), required=True)
    comparison = commands.add_parser("evaluate", help="Compare keyword and vector page retrieval.")
    comparison.add_argument("keyword_db", type=Path)
    comparison.add_argument("cases", type=Path)
    args = parser.parse_args()
    dsn = os.getenv("FINDOC_DATABASE_URL")
    if not dsn:
        parser.error("Set FINDOC_DATABASE_URL to a PostgreSQL connection string.")
    try:
        model = LocalEmbeddings()
        with vector_engine(dsn) as engine:
            if args.command == "index":
                try:
                    engine.init_vectorstore_table(
                        TABLE, 384, metadata_columns=[Column(name, "TEXT", nullable=False) for name in FILTER_COLUMNS]
                    )
                except ProgrammingError as exc:
                    if not isinstance(exc.orig, psycopg.errors.DuplicateTable):
                        raise
            else:
                store = open_store(engine, model)
                if args.command == "search":
                    output = search(store, model, args.question, args.period_end)
                else:
                    from findoc.baseline.evaluate import evaluate

                    output = evaluate(partial(search, store, model), args.keyword_db, args.cases)
                print(json.dumps(output, indent=2))
        if args.command == "index":
            with psycopg.connect(dsn, autocommit=True) as connection:
                for pdf in args.pdfs:
                    period, count = index_pdf(connection, pdf, model)
                    print(f"Stored {count} passages for the quarter ended {period}.")
    except (OSError, ValueError, psycopg.Error, SQLAlchemyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Vector retrieval failed: {exc}\n")


if __name__ == "__main__":
    main()
