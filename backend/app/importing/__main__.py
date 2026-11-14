"""Local CLI: stage a file; --apply explicitly updates the catalog."""
import argparse
import csv
import json
from pathlib import Path
from collections import Counter
from .engine import stage, apply_job
from .normalize import MAX_BYTES
from .providers import upload_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--provider', choices=['manual', 'wikidata', 'retroflops', 'oldcomputers', '1000bit', 'computerhistory'], default='manual')
    parser.add_argument('--rights-confirmed', action='store_true', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--existing-only', action=argparse.BooleanOptionalAction, default=None,
                        help='Aggiorna solo schede esistenti; predefinito per 1000bit.')
    parser.add_argument('--source-url', help='URL originale per una scheda HTML senza metadati di origine.')
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
        records = upload_records(args.provider, format, raw, args.source_url)
        with SessionLocal() as db:
            job = stage(db, args.provider, args.file.name[:250], format, raw, records=records,
                        options={'upload': True, 'rights_confirmed': True, 'source_url': args.source_url,
                                 'existing_only': args.existing_only if args.existing_only is not None else args.provider == '1000bit'})
            if args.apply:
                job = apply_job(db, job.id)
            print(json.dumps({'id': job.id, 'status': job.status, 'counts': dict(Counter(r.status for r in job.rows))}))
    except (ValueError, KeyError, TypeError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
