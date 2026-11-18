"""Exclude base-dataset citations from the active bibliography, retaining ETL audit.

Sources are referenced by immutable import claims and external identities. Keep
those internal records so replays and human decisions retain their meaning;
reader/admin source APIs consistently exclude MAME citations, including new ones.
"""
from collections.abc import Mapping
import re
import unicodedata
from urllib.parse import urlsplit

from sqlalchemy import select
from .models import Source


def is_mame_source(source):
    def value(field):
        return source.get(field) if isinstance(source, Mapping) else getattr(source, field, None)

    for field in ('title', 'publisher', 'author', 'source_type'):
        text = unicodedata.normalize('NFKC', value(field) or '').casefold()
        if field == 'source_type':
            text = text.replace('_', ' ')
        if re.search(r'\b(?:mame|mamedev)\b', text):
            return True
    try:
        url = urlsplit(value('url') or '')
        host = (url.hostname or '').lower().rstrip('.')
    except ValueError:
        return False
    if host in {'mamedev.org', 'mame.net'} or host.endswith(('.mamedev.org', '.mame.net')):
        return True
    if host in {'github.com', 'www.github.com', 'raw.githubusercontent.com', 'codeload.github.com'}:
        parts = url.path.strip('/').casefold().split('/')
        return len(parts) >= 2 and parts[0] == 'mamedev' and parts[1] in {'mame', 'mame.git'}
    return False


def excluded_source_ids(db):
    return [source.id for source in db.scalars(select(Source)) if is_mame_source(source)]
