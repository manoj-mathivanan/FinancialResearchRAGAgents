"""Compatibility entry point for the SQLite keyword baseline."""

from findoc.baseline.keyword import build_index, main, search
from findoc.tools.transcripts import DEFAULT_PERIOD, NSE_ARCHIVE, TRANSCRIPTS, Transcript, read_call_pages


if __name__ == "__main__":
    main()
