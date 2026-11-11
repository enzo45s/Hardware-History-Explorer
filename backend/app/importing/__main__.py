"""Local CLI: stage a file; --apply explicitly updates the catalog."""
import argparse
import csv
import json
from pathlib import Path
from collections import Counter
from .engine import stage, apply_job
from .normalize import MAX_BYTES
from .providers import retroflops_records, wikidata_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--provider', choices=['manual', 'wikidata', 'retroflops', 'oldcomputers', '1000bit', 'computerhistory'], default='manual')
    parser.add_argument('--rights-confirmed', action='store_true', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with args.file.open('rb') as file:
        raw = file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        parser.error('Massimo 8 MB')
    from ..main import engine, SessionLocal
    from migrations.historical_imports import migrate
    migrate(engine)
    format = args.file.suffix.lower().lstrip('.')
    records = None
    try:
        if format == 'json' and args.provider in ('wikidata', 'retroflops'):
            payload = json.loads(raw.decode('utf-8-sig'))
            records = retroflops_records(payload) if args.provider == 'retroflops' else wikidata_records(payload)
        with SessionLocal() as db:
            job = stage(db, args.provider, args.file.name[:250], format, raw, records=records,
                        options={'upload': True, 'rights_confirmed': True})
            if args.apply:
                job = apply_job(db, job.id)
            print(json.dumps({'id': job.id, 'status': job.status, 'counts': dict(Counter(r.status for r in job.rows))}))
    except (ValueError, KeyError, TypeError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
