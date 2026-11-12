"""Extract page-level evidence from supported NSE earnings-call PDFs."""

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


NSE_ARCHIVE = "https://nsearchives.nseindia.com/corporate/"
DEFAULT_PERIOD = "2025-12-31"


@dataclass(frozen=True)
class Transcript:
    filename: str
    title_pattern: str
    total_pages: int
    cover_page: int
    first_content_page: int


TRANSCRIPTS = {
    "2024-12-31": Transcript(
        "Infosys_21012025151633_SEfiling_Earningscalltranscript.pdf",
        r"Q3 FY.25 Earnings Conference Call\s+January 16, 2025",
        45, 21, 23,
    ),
    DEFAULT_PERIOD: Transcript(
        "Infosys_19012026222220_SEfiling_Earningscalltranscript_19012026.pdf",
        r"Q3 FY.26 Earnings Conference Call\s+January 14, 2026",
        39, 18, 19,
    ),
}


def read_call_pages(pdf: Path) -> tuple[str, list[tuple[int, str]]]:
    result = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(pdf.resolve()), "-"],
        capture_output=True,
        check=True,
        timeout=30,
    )
    pages = result.stdout.decode("utf-8").rstrip("\f\r\n").split("\f")
    matches = [
        (period, transcript) for period, transcript in TRANSCRIPTS.items()
        if len(pages) == transcript.total_pages
        and re.search(transcript.title_pattern, pages[transcript.cover_page - 1])
    ]
    if len(matches) != 1:
        raise ValueError("Expected a supported NSE Q3 earnings-call filing.")
    period, transcript = matches[0]

    entries = []
    first_page = transcript.first_content_page
    for page_number, page in enumerate(pages[first_page - 1:], first_page):
        lines = [
            line for line in page.splitlines()
            if "External Document" not in line and line.strip() != "www.infosys.com"
        ]
        text = " ".join(" ".join(lines).split())
        if not text:
            raise ValueError(f"No extractable text on PDF page {page_number}.")
        entries.append((page_number, text))
    return period, entries
