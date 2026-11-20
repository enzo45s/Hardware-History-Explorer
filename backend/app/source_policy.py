"""Exclude base-dataset citations from the active bibliography, retaining ETL audit.

Sources are referenced by immutable import claims and external identities. Keep
those internal records so replays and human decisions retain their meaning;
reader/admin source APIs exclude MAME and HHE self-citations, and RetroFlops
references that no longer support any catalog entity.
"""
from collections.abc import Mapping
import re
import unicodedata
from urllib.parse import urlsplit

from sqlalchemy import select, union
from .models import (Source, computer_source, spec_source, release_source,
                     sale_source, review_source, fact_source)


def value(source, field):
    return source.get(field) if isinstance(source, Mapping) else getattr(source, field, None)


def source_text(source, field):
    text = unicodedata.normalize('NFKC', value(source, field) or '').casefold()
    return ' '.join(text.split())


def source_url(source):
    try:
        url = urlsplit(value(source, 'url') or '')
        return ((url.hostname or '').lower().rstrip('.'), url.path.strip('/').casefold().split('/'))
    except ValueError:
        return '', []


GITHUB_HOSTS = {'github.com', 'www.github.com', 'raw.githubusercontent.com', 'codeload.github.com'}


def repository_url(host, parts, owner, repository):
    return host in GITHUB_HOSTS and len(parts) >= 2 and parts[0] == owner and parts[1] in {repository, repository + '.git'}


def is_mame_source(source):
    for field in ('title', 'publisher', 'author', 'source_type'):
        text = source_text(source, field)
        if field == 'source_type':
            text = text.replace('_', ' ')
        if re.search(r'\b(?:mame|mamedev)\b', text):
            return True
    host, parts = source_url(source)
    if host in {'mamedev.org', 'mame.net'} or host.endswith(('.mamedev.org', '.mame.net')):
        return True
    return repository_url(host, parts, 'mamedev', 'mame')


def is_hhe_source(source):
    # Recognize the project's own metadata, not any third-party page mentioning it.
    project_name = r'hardware[ -]history[ -]explorer'
    for field in ('author', 'publisher'):
        if re.match(rf'^(?:hhe|{project_name})(?:$|[\s·:—–(])', source_text(source, field)):
            return True
    if re.match(rf'^(?:hhe|{project_name})(?:$|\s*[·:—–-])', source_text(source, 'title')):
        return True
    if re.match(r'^hhe(?:$|[_-])', source_text(source, 'source_type')):
        return True
    host, parts = source_url(source)
    return (repository_url(host, parts, 'enzo45s', 'hardware-history-explorer') or
            host == 'enzo45s.github.io' and bool(parts) and parts[0] == 'hardware-history-explorer')


def is_retroflops_source(source):
    if any(re.search(r'\bretroflops\b', source_text(source, field).replace('_', ' '))
           for field in ('title', 'author', 'publisher', 'source_type')):
        return True
    host, parts = source_url(source)
    return host in {'retroflops.github.io', 'www.retroflops.github.io'} or repository_url(host, parts, 'retroflops', 'retroflops')


def is_internal_source(source):
    return is_mame_source(source) or is_hhe_source(source)


def current_source_ids(db):
    """Operational use means a current catalog link, not an old import/audit row."""
    links = (computer_source, spec_source, release_source, sale_source, review_source, fact_source)
    return set(db.scalars(union(*(select(table.c.source_id) for table in links))))


def is_visible_source(db, source):
    if is_internal_source(source):
        return False
    return not is_retroflops_source(source) or source.id in current_source_ids(db)


def excluded_source_ids(db):
    sources = list(db.scalars(select(Source)))
    retroflops = {source.id for source in sources if is_retroflops_source(source)}
    unused_retroflops = retroflops - current_source_ids(db) if retroflops else set()
    return [source.id for source in sources if is_internal_source(source) or source.id in unused_retroflops]
