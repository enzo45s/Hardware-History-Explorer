"""Conservative commercial-release summaries; never rewrite historical evidence.

An undated price is still undated in storage and in the raw API. This view can
place a model's independently sourced date beside compatible market offers,
while retaining the original records and the date's geographical scope.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import date
import re
import unicodedata
from .geography import european_countries


def key(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


def unknown_market(value):
    value = key(value)
    return value in {'', 'non specificato', 'non indicato', 'sconosciuto', 'unknown', 'unspecified', 'mercato non documentato'} or bool(
        re.fullmatch(r'non specificato dalla fonte(?:\s*\([^)]*\))?', value))


def market_key(row):
    return '' if unknown_market(row['market']) else 'europa' if european_countries(row['market']) else key(row['market'])


DATES = ('release_date', 'discontinuation_date')
LAUNCH_TYPES = {'', 'launch', 'launch_price', 'lancio', 'prezzo di lancio', 'prezzo al lancio',
                'prezzo riportato', 'listino di lancio'}


def compatible(rows):
    """No conflicting values, precision upgrades or backwards date ranges."""
    if len({row.get('model_variant') for row in rows}) > 1:
        return False
    for field in (*DATES, 'currency'):
        if len({row[field] for row in rows if row.get(field) is not None}) > 1:
            return False
    dates = {field: next((row[field] for row in rows if row.get(field)), None) for field in DATES}
    if all(dates.values()):
        def earliest(value):
            parts = [int(part) for part in value.split('-')]
            return date(*(parts + [1] * (3 - len(parts))))
        if earliest(dates['release_date']) > earliest(dates['discontinuation_date']):
            return False
    return True


def complete_launch_dates(dates, prices, consumed):
    """One consistent date may contextualize several distinct launch offers.

    Plan against the unchanged evidence first: never choose a year by input
    order, equate amounts or infer a country from a currency. Regional dates
    only complete their market; a marketless date remains model-level context.
    """
    plans = []
    remaining = [group for group in dates if group['row']['id'] not in consumed]
    for target in prices:
        price = target['row']
        if price.get('release_date') or key(price.get('price_type')) not in LAUNCH_TYPES:
            continue
        candidates = [group for group in remaining if group['row'].get('release_date')
            and (not market_key(group['row']) or market_key(group['row']) == market_key(price))
            and group['row'].get('model_variant') == price.get('model_variant')]
        if not candidates or not compatible([price, *(group['row'] for group in candidates)]):
            continue
        plans.append((target, candidates))
    for target, candidates in plans:
        for group in candidates:
            for field in DATES:
                if target['row'].get(field) is None:
                    target['row'][field] = group['row'].get(field)
            target['originals'].extend(deepcopy(group['originals']))
            consumed.add(group['row']['id'])
        # Shared date evidence can occur in several summaries. Use each
        # offer's own ID so React keys and API offer IDs remain unique.
        target['summary_id'] = target['row']['id']


def release_summaries(releases):
    """Only complementary date/price records with a unique match are combined.

    Never merge two prices from the same country (they may describe different
    configurations) or assign a price of unknown geography to a country. Shared
    dates add context to offers, preserving their original geographical scope.
    """
    rows = sorted(deepcopy(releases), key=lambda row: row['id'])
    known_markets = defaultdict(set)
    for row in rows:
        if market_key(row):
            known_markets[row.get('model_variant')].add(market_key(row))
    dates, prices, others = [], [], []
    duplicates = {}
    for row in rows:
        group = {'row': row, 'originals': [deepcopy(row)]}
        if row.get('price') is not None:
            prices.append(group)
        elif any(row.get(field) for field in DATES):
            signature = (row.get('model_variant'), market_key(row), *(row.get(field) for field in DATES), row.get('currency'), row.get('price_type'))
            if signature in duplicates:
                duplicates[signature]['originals'].append(deepcopy(row))
            else:
                duplicates[signature] = group
                dates.append(group)
        else:
            others.append(group)

    # Equal offers repeated across different European countries become one
    # regional offer. Multiple identical rows in one country remain ambiguous.
    european_prices = defaultdict(list)
    price_groups = []
    for group in prices:
        row = group['row']
        if market_key(row) == 'europa' and row.get('currency'):
            european_prices[tuple(row.get(field) for field in ('model_variant', 'price', 'currency', 'price_type', *DATES))].append(group)
        else:
            price_groups.append(group)
    for repeated in european_prices.values():
        countries = [country for group in repeated for country in european_countries(group['row']['market'])]
        if len(countries) != len(set(countries)):
            price_groups.extend(repeated)
            continue
        target = repeated[0]
        for group in repeated[1:]:
            target['originals'].extend(group['originals'])
        price_groups.append(target)
    prices = sorted(price_groups, key=lambda group: group['row']['id'])

    plans = defaultdict(list)
    for group in dates:
        row = group['row']
        matches = []
        for target in prices:
            price = target['row']
            source_market, target_market = market_key(row), market_key(price)
            if source_market != target_market:
                # Only the date's missing region can use the sole known market.
                if source_market or not target_market or known_markets[row.get('model_variant')] != {target_market}:
                    continue
            if not price.get('release_date') and key(price.get('price_type')) not in LAUNCH_TYPES:
                continue
            if compatible([row, price]):
                matches.append(target)
        if len(matches) == 1:
            plans[matches[0]['row']['id']].append(group)

    consumed = set()
    for target in prices:
        additions = plans.get(target['row']['id'], [])
        if not additions or not compatible([target['row'], *(group['row'] for group in additions)]):
            continue
        for group in additions:
            for field in DATES:
                if target['row'].get(field) is None:
                    target['row'][field] = group['row'].get(field)
            target['originals'].extend(group['originals'])
            consumed.add(group['row']['id'])

    complete_launch_dates(dates, prices, consumed)

    result = []
    groups = prices + [group for group in dates if group['row']['id'] not in consumed] + others
    for group in groups:
        summary = group['row']
        originals = sorted(group['originals'], key=lambda row: row['id'])
        summary['release_ids'] = [row['id'] for row in originals]
        summary['id'] = group.get('summary_id', min(summary['release_ids']))
        summary['merged'] = len(originals) > 1
        summary['original_releases'] = originals
        if market_key(summary) == 'europa':
            summary['market'] = 'Europa'
            summary['countries'] = sorted({country for row in originals for country in european_countries(row['market'])})
            summary['price_countries'] = sorted({country for row in originals if row.get('price') is not None for country in european_countries(row['market'])})
        elif not market_key(summary):
            summary['market'] = 'Mercato non documentato'
        summary['original_markets'] = list(dict.fromkeys(row['market'] for row in originals))
        summary['date_scope'] = 'model' if (market_key(summary) and summary.get('release_date') and not any(
            market_key(row) == market_key(summary) and row.get('release_date') == summary['release_date'] for row in originals)) else 'market'
        # Preserve which source supports each field, not merely the union of URLs.
        summary['field_sources'] = {
            field: sorted({source['id'] for row in originals if row.get(field) is not None and row.get(field) == summary.get(field) for source in row['sources']})
            for field in ('market', *DATES, 'price', 'currency', 'price_type')
        }
        summary['field_sources']['market'] = sorted({source['id'] for row in originals if market_key(row) for source in row['sources']})
        sources = {source['id']: source for row in originals for source in row['sources']}
        summary['sources'] = [sources[identifier] for identifier in sorted(sources)]
        result.append(summary)
    return sorted(result, key=lambda row: row['id'])
