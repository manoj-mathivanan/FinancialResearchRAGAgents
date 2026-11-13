"""Build the fixed Infosys quarterly brief from reviewed source facts."""

from datetime import date
import json
from pathlib import Path

from findoc.compare import METRICS, compare_quarters
from findoc.tools.transcripts import NSE_ARCHIVE, TRANSCRIPTS


def infosys_brief(data_dir: Path) -> dict:
    current = json.loads((data_dir / "infosys-q3-fy26.json").read_text(encoding="utf-8"))
    prior = json.loads((data_dir / "infosys-q2-fy26.json").read_text(encoding="utf-8"))
    current_end, prior_end = date(2025, 12, 31), date(2025, 9, 30)
    snapshot = {
        **current,
        "snapshot_id": f"{prior['snapshot_id']}+{current['snapshot_id']}",
        "facts": [
            {**fact, "source": snapshot["source"]}
            for snapshot in (prior, current) for fact in snapshot["facts"]
        ],
    }
    transcript = TRANSCRIPTS[current_end.isoformat()]
    return {
        "metrics": [compare_quarters(snapshot, metric, current_end, prior_end) for metric in METRICS],
        "management": {
            "text": "Management reported an operating margin of 18.4%, or 21.2% after excluding the impact of the labor-code change.",
            "url": f"{NSE_ARCHIVE}{transcript.filename}#page=21",
        },
        "assessment": "Mixed",
        "assessment_basis": "Revenue rose while profit attributable to owners fell. This snapshot gives a mixed signal about business performance.",
        "gap": "This brief covers two reporting quarters and one earnings call. It provides limited evidence about whether the changes will persist.",
    }
