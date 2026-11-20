"""Prepare canonical price JSON and a report; never writes to a catalog or fetches URLs."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.importing.prices import workbook_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    records, report = workbook_records(args.workbook.read_bytes())
    args.output.write_text(json.dumps({'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('models', 'price_records', 'context_only_records',
        'without_price', 'source_columns_repaired', 'invalid_records')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
