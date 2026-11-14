"""Download and index the configured earnings calls as a one-off deployment job."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen

from findoc.tools.transcripts import NSE_ARCHIVE, TRANSCRIPTS


def main() -> None:
    if not os.getenv("FINDOC_DATABASE_URL"):
        raise SystemExit("Set FINDOC_DATABASE_URL before indexing transcripts.")

    with TemporaryDirectory() as directory:
        # The PDF downloads are temporary. The indexed passages live in PostgreSQL.
        pdfs = []
        for transcript in TRANSCRIPTS.values():
            request = Request(NSE_ARCHIVE + transcript.filename, headers={"User-Agent": "Mozilla/5.0"})
            path = Path(directory) / transcript.filename
            with urlopen(request, timeout=30) as response:
                content = response.read(20_000_001)
            if not content.startswith(b"%PDF-") or len(content) > 20_000_000:
                raise ValueError(f"Expected a PDF of at most 20 MB for {transcript.filename}.")
            path.write_bytes(content)
            pdfs.append(str(path))
        subprocess.run([sys.executable, "-m", "findoc.vector", "index", *pdfs], check=True)


if __name__ == "__main__":
    main()
