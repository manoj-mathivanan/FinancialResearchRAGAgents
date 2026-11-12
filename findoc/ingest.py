"""Extract and verify quarterly Infosys facts from supported NSE HTML filings."""

import argparse
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
from itertools import chain
import json
from pathlib import Path


NSE_ARCHIVE = "https://nsearchives.nseindia.com/corporate/ixbrl/"
FILINGS = {
    date(2025, 3, 31): NSE_ARCHIVE + "INTEGRATED_FILING_INDAS_85350_17042025233634_iXBRL_WEB.html",
    date(2025, 12, 31): NSE_ARCHIVE + "INTEGRATED_FILING_INDAS_135037_14012026203832_iXBRL_WEB.html",
    date(2026, 3, 31): NSE_ARCHIVE + "INTEGRATED_FILING_INDAS_152465_23042026210154_iXBRL_WEB.html",
}
SECTION = "Financial Results Ind-AS"
METRICS = {
    "revenue": "Revenue from operations",
    "owners-profit": "Profit or loss, attributable to owners of parent",
}


class Tables(HTMLParser):
    """Read physical cells in the flat tables used by these filing pages."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.table is not None:
                raise ValueError("Nested tables are unsupported.")
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def one(items, description):
    if len(items) != 1:
        raise ValueError(f"Expected one {description}; found {len(items)}.")
    return items[0]


def read_date(value):
    for fmt in ("%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized filing date: {value}")


def extract_facts(document: bytes, end: date) -> list[dict]:
    if end not in FILINGS:
        raise ValueError(f"No configured filing for {end}.")
    parser = Tables()
    parser.feed(document.decode("utf-8-sig"))
    parser.close()
    general = one(
        [table for table in parser.tables if ["NSE Symbol", "INFY"] in table],
        "Infosys metadata table",
    )
    metadata = {row[0]: row[1] for row in general if len(row) == 2}
    currency = metadata.get("Description of presentation currency")
    scale = metadata.get("Level of rounding used in financial results")
    if currency == "INR (in Actuals)" and not scale:
        raw_unit, divisor = "INR", Decimal("10000000")
    elif currency == "INR" and scale == "Lakhs":
        raw_unit, divisor = "INR lakh", Decimal("100")
    else:
        raise ValueError(f"Unsupported currency or scale: {currency!r}, {scale!r}.")

    table_number, rows = one(
        [(index, table) for index, table in enumerate(parser.tables, 1)
         if set(METRICS.values()).issubset(row[1] for row in table if len(row) == 4)],
        "financial results table",
    )

    def locate(label):
        return one(
            [(index, row) for index, row in enumerate(rows, 1)
             if row[1:2] == [label] and len(row) == 4],
            f"row for {label}",
        )

    start = date(end.year, end.month - 2, 1)
    _, starts = locate("Date of start of reporting period")
    _, ends = locate("Date of end of reporting period")
    column = one(
        [index for index in (2, 3)
         if read_date(starts[index]) == start and read_date(ends[index]) == end],
        f"column covering {start} through {end}",
    )
    _, scopes = locate("Nature of report standalone or consolidated")
    if scopes[column] != "Consolidated":
        raise ValueError("Expected consolidated results.")
    _, audit = locate("Whether results are audited or unaudited")
    if audit[column] != "Audited":
        raise ValueError("Expected audited results.")

    digest = sha256(document).hexdigest()
    facts = []
    for metric, label in METRICS.items():
        row_number, row = locate(label)
        raw_value = row[column]
        amount = Decimal(raw_value.replace(",", ""))
        if not amount.is_finite():
            raise ValueError(f"Non-finite value for {label}.")
        facts.append({
            "metric": metric,
            "row": label,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "value": format(amount / divisor, "f"),
            "source": {
                "url": FILINGS[end],
                "section": SECTION,
                "sha256": digest,
                "table_number": table_number,
                "row_number": row_number,
                "cell_number": column + 1,
                "raw_value": raw_value,
                "raw_unit": raw_unit,
            },
        })
    return facts


def values_by_period(facts):
    values = {}
    for fact in facts:
        key = (fact["metric"], fact["start"], fact["end"])
        if key in values:
            raise ValueError(f"Duplicate fact for {key}.")
        values[key] = Decimal(fact["value"])
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fy25", type=Path, required=True, help="Local NSE Q4 FY2025 HTML filing.")
    parser.add_argument("--fy26", type=Path, required=True, help="Local NSE Q4 FY2026 HTML filing.")
    parser.add_argument("--q3-fy26", type=Path, help="Optional local NSE Q3 FY2026 HTML filing.")
    parser.add_argument("--reference", type=Path, action="append", required=True,
                        help="Manual reference JSON. Repeat to combine references.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs = {
            date(2025, 3, 31): args.fy25,
            date(2026, 3, 31): args.fy26,
        }
        if args.q3_fy26 is not None:
            inputs[date(2025, 12, 31)] = args.q3_fy26
        references = [
            json.loads(path.read_text(encoding="utf-8"))["facts"]
            for path in args.reference
        ]
        facts = [
            fact for end, path in sorted(inputs.items())
            for fact in extract_facts(path.read_bytes(), end)
        ]
        expected = values_by_period(chain.from_iterable(references))
        actual = values_by_period(facts)
        if actual != expected:
            mismatches = sorted(
                key for key in actual.keys() | expected.keys()
                if actual.get(key) != expected.get(key)
            )
            raise ValueError(f"Extracted facts differ from the reference: {mismatches}")
        content_id = sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:12]
        snapshot = {
            "snapshot_id": f"infosys-nse-quarterly-{content_id}",
            "company": "Infosys",
            "symbol": "INFY",
            "scope": "consolidated",
            "accounting_basis": "Ind AS",
            "unit": "INR crore",
            "facts": facts,
        }
        with args.output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(snapshot, indent=2) + "\n")
    except (OSError, ValueError, InvalidOperation) as exc:
        parser.exit(1, f"Ingestion failed: {exc}\n")
    print(f"Verified {len(facts)} extracted facts against the manual reference. Wrote {args.output}.")


if __name__ == "__main__":
    main()
