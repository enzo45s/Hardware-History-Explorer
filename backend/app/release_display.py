"""Commercial offers with explicit date scope and field-level provenance.

Legacy catalogs retain separate assertions. Physical cleanup persists the same
summaries in primary tables and archives originals; both modes use these rules.
Reference variant years never become independently verified launch dates.
"""
from collections import defaultdict
from calendar import monthrange
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


def refined_date(values):
    """Use only a supplied date that refines every other supplied precision."""
    values = {value for value in values if value}
    if not values:
        return None
    precise = max(values, key=len)
    return precise if all(precise == value or precise.startswith(value + '-') for value in values) else None


def compatible(rows):
    """Allow consistent date refinements, never conflicting dates or ranges."""
    if len({row.get('model_variant') for row in rows}) > 1:
        return False
    if len({row['currency'] for row in rows if row.get('currency') is not None}) > 1:
        return False
    dates = {}
    for field in DATES:
        values = [row.get(field) for row in rows if row.get(field)]
        dates[field] = refined_date(values)
        if values and dates[field] is None:
            return False
    if all(dates.values()):
        def bound(value, upper=False):
            parts = [int(part) for part in value.split('-')]
            year = parts[0]
            month = parts[1] if len(parts) > 1 else 12 if upper else 1
            day = parts[2] if len(parts) > 2 else monthrange(year, month)[1] if upper else 1
            return date(year, month, day)
        if bound(dates['release_date']) > bound(dates['discontinuation_date'], upper=True):
            return False
    return True


def merge_date_evidence(target, additions, *, refine=False):
    supporting = [target['row'], *(group['row'] for group in additions)]
    previous_date=target['row'].get('release_date')
    for field in DATES:
        if refine or target['row'].get(field) is None:
            target['row'][field] = refined_date(row.get(field) for row in supporting)
    if not previous_date or previous_date!=target['row'].get('release_date'):
        evidence=[g['row'].get('date_evidence', {'kind':'documented','source_ids':[s['id'] for s in g['row'].get('sources',[])]}) for g in additions if g['row'].get('release_date')==target['row'].get('release_date')]
        evidence=[v for v in evidence if v]
        if evidence:
            target['row']['date_evidence']={'kind':'reference' if all(v['kind']=='reference' for v in evidence) else 'documented',
                'source_ids':sorted({i for v in evidence for i in v.get('source_ids',[])})}
            if target['row']['date_evidence']['kind']=='reference':
                target['row']['date_evidence']['base']=any(v.get('base') for v in evidence)
                target['row']['reference_note']=next((g['row']['reference_note'] for g in additions if g['row'].get('reference_note')), 'Anno di riferimento del modello; data di lancio non documentata.')
            else:target['row'].pop('reference_note',None)
    notes=list(target['row'].get('commercialization_notes',[]))
    references=set(target['row'].get('reference_dates',[]))
    for group in additions:
        notes.extend(group['row'].get('commercialization_notes',[]))
        references.update(group['row'].get('reference_dates',[]))
        target['originals'].extend(deepcopy(group['originals']))
    if notes:target['row']['commercialization_notes']=list(dict.fromkeys(notes))
    if references:target['row']['reference_dates']=sorted(references)


def reference_date_groups(dates, prices):
    """Retire reference variant years as context, rather than extra offers.

    Prefer a registration of the actual base model; otherwise explicitly label
    the first recorded reference year. Documented date disagreements remain
    disagreements. No market or actual launch date is inferred here.
    """
    scoped_offers=any(p['row'].get('model_variant') for p in prices)
    scopes=defaultdict(list);result=[]
    for group in dates:
        row=group['row']
        if (row.get('date_evidence',{}).get('kind')=='reference' and row.get('release_date')
                and not row.get('discontinuation_date') and not market_key(row)):
            scopes[row.get('model_variant') if scoped_offers else None].append(group)
        else:result.append(group)
    for scope,groups in scopes.items():
        launches=[p for p in prices if p['row'].get('model_variant')==scope
            and p['row'].get('date_evidence',{}).get('kind')=='documented_launch']
        if launches:
            target=launches[0]
            refs=set(target['row'].get('reference_dates',[]))
            for group in groups:
                refs.add(group['row']['release_date']);refs.update(group['row'].get('reference_dates',[]))
                target['originals'].extend(deepcopy(group['originals']))
            target['row']['reference_dates']=sorted(refs)
            continue
        documented=[g for g in result if g['row'].get('model_variant')==scope and not market_key(g['row']) and g['row'].get('release_date')]
        if documented and compatible([g['row'] for g in documented]):
            target=documented[0]
        else:
            base=[g for g in groups if g['row']['date_evidence'].get('base')]
            candidates=base or groups
            date_value=refined_date(g['row']['release_date'] for g in candidates)
            target=min((g for g in candidates if date_value is None or g['row']['release_date']==date_value),key=lambda g:(g['row']['release_date'],g['row']['id']))
            target['row']['date_scope']='reference'
            if scope is None:
                target['row'].pop('model_variant',None);target['row'].pop('display_model_variant',None)
            note='Anno di riferimento del modello; data di lancio non documentata.' if base else 'Primo anno registrato nei dati disponibili; data di lancio non documentata.'
            target['row']['reference_note']=note
            result.append(target)
        refs=set(target['row'].get('reference_dates',[]))
        for group in groups:
            refs.add(group['row']['release_date']);refs.update(group['row'].get('reference_dates',[]))
            if group is not target:target['originals'].extend(deepcopy(group['originals']))
        target['row']['reference_dates']=sorted(refs)
    return sorted(result,key=lambda g:g['row']['id'])


def refine_date_groups(groups):
    """Coalesce date-only precision variants only when the whole set agrees."""
    contexts = defaultdict(list)
    for group in groups:
        row = group['row']
        contexts[(row.get('model_variant'), market_key(row), row.get('currency'), row.get('price_type'))].append(group)
    result = []
    for repeated in contexts.values():
        if not compatible([group['row'] for group in repeated]):
            result.extend(repeated)
            continue
        target = repeated[0]
        merge_date_evidence(target, repeated[1:], refine=True)
        result.append(target)
    return sorted(result, key=lambda group: group['row']['id'])


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
        merge_date_evidence(target, candidates)
        for group in candidates:
            consumed.add(group['row']['id'])
        # Shared date evidence can occur in several summaries. Use each
        # offer's own ID so React keys and API offer IDs remain unique.
        target['summary_id'] = target['row']['id']


def coalesce_repeated_offers(groups):
    """Same cited offer, with complementary date precision, is one record.

    Equal prices alone are insufficient. Require the same nonempty citation
    set, market, hardware variant, currency and price type. If the dates in a
    group disagree, no undated row is assigned arbitrarily to either date.
    """
    repeated=defaultdict(list);result=[]
    for group in groups:
        row=group['row']
        citations=tuple(sorted((s['id'],s.get('url') or '') for s in row['sources']))
        if not citations or not row.get('currency'):
            result.append(group);continue
        signature=(row.get('model_variant'),market_key(row),row['price'],row['currency'],row.get('price_type'),citations)
        repeated[signature].append(group)
    for candidates in repeated.values():
        if not compatible([g['row'] for g in candidates]):
            result.extend(candidates);continue
        # Prefer the supplied, most precise date and its qualifications, even
        # when the undated duplicate has the lowest database identifier.
        target=max(candidates,key=lambda g:(len(g['row'].get('release_date') or ''),
            len(g['row'].get('discontinuation_date') or ''),-g['row']['id']))
        merge_date_evidence(target,[g for g in candidates if g is not target],refine=True)
        result.append(target)
    return sorted(result,key=lambda g:g['row']['id'])


def release_summaries(releases):
    """Only complementary date/price records with a unique match are combined.

    Equal amounts with different citations or hardware scopes remain distinct.
    Never assign a price of unknown geography to a country. Shared
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
        original=deepcopy(row)
        proof=row.get('documented_launch')
        if proof:
            row['release_date']=proof['date']
            row['date_evidence']={'kind':'documented_launch','source_ids':[proof['source_id']]}
            row['commercialization_notes']=list(dict.fromkeys([*row.get('commercialization_notes',[]),proof['note']]))
            row.pop('reference_note',None)
        group = {'row': row, 'originals': [original]}
        if row.get('price') is not None:
            if row.get('release_date') and row.get('date_evidence',{}).get('kind')=='reference' and key(row.get('price_type')) in LAUNCH_TYPES:
                context=deepcopy(row)
                context.update(price=None,currency=None,price_type=None,market='Mercato non documentato')
                # Context is not a second offer. Never merge priced originals.
                dates.append({'row':context,'originals':[]})
                row['release_date']=None
            prices.append(group)
        elif any(row.get(field) for field in DATES):
            signature = (row.get('model_variant'), market_key(row), *(row.get(field) for field in DATES), row.get('currency'), row.get('price_type'))
            if signature in duplicates:
                previous=duplicates[signature]
                previous['originals'].append(deepcopy(row))
                if previous['row'].get('date_evidence',{}).get('kind')=='reference' and row.get('date_evidence',{}).get('kind')!='reference':
                    previous['row']=row
            else:
                duplicates[signature] = group
                dates.append(group)
        else:
            others.append(group)

    prices = coalesce_repeated_offers(prices)
    # A virtual reference year belongs to its priced original. If that same
    # offer now has a documented date after deduplication, retain the old year
    # as context on the offer, rather than creating a card with no originals.
    dated_offers={old['id']:group for group in prices if group['row'].get('release_date') for old in group['originals']}
    remaining_dates=[]
    for group in dates:
        owner=dated_offers.get(group['row']['id']) if not group['originals'] else None
        if owner is None:
            remaining_dates.append(group);continue
        owner['row']['reference_dates']=sorted({*owner['row'].get('reference_dates',[]),
            *group['row'].get('reference_dates',[]),group['row']['release_date']})
    dates=remaining_dates
    dates = refine_date_groups(reference_date_groups(dates,prices))

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
        merge_date_evidence(target, additions)
        for group in additions:
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
        if any(row.get('date_scope') == 'model' for row in originals):
            summary['date_scope'] = 'model'
        if summary.get('date_evidence',{}).get('kind')=='reference':
            summary['date_scope']='reference'
        else:
            summary.pop('reference_note',None)
            if summary.get('date_evidence',{}).get('kind')=='documented_launch':summary['date_scope']='model'
        # Preserve which source supports each field, not merely the union of URLs.
        summary['field_sources'] = {
            field: sorted({source['id'] for row in originals if row.get(field) is not None and row.get(field) == summary.get(field) for source in row['sources']})
            for field in ('market', *DATES, 'price', 'currency', 'price_type')
        }
        summary['field_sources']['market'] = sorted({source['id'] for row in originals if market_key(row) for source in row['sources']})
        if summary.get('date_evidence'):
            summary['field_sources']['release_date']=summary['date_evidence'].get('source_ids',[])
        sources = {source['id']: source for row in originals for source in row['sources']}
        summary['sources'] = [sources[identifier] for identifier in sorted(sources)]
        result.append(summary)
    return sorted(result, key=lambda row: row['id'])
