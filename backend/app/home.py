"""Bounded, read-only selection for the museum entrance. No seeded content."""
from sqlalchemy import case, func, or_, select

from .models import Computer, Manufacturer, Release


# Editorial display preferences, not identity/deduplication rules. All links
# and images come from the actual records in this archive, never fixed IDs.
SPOTLIGHT_PREFERENCE = (('commodore', 'commodore business machines'), ('commodore 64', 'c64'))
PREFERENCES = (
    (('olivetti',), ('programma 101', 'olivetti programma 101')),
    (('apple', 'apple computer', 'apple computer inc.', 'apple computer inc'), ('apple ii', 'apple ][', 'ii', '][')),
    (('ibm', 'international business machines'), ('ibm pc 5150', 'pc 5150', 'ibm pc')),
)


def home_data(db, serialize, eager):
    total = db.scalar(select(func.count()).select_from(Computer))
    manufacturers = db.scalar(select(func.count()).select_from(Manufacturer))
    def preferred_id(preference):
        makers, models = preference
        return db.scalar(select(Computer.id).join(Computer.manufacturer).where(
            func.lower(func.trim(Computer.model_name)).in_(models),
            func.lower(func.trim(Manufacturer.name)).in_(makers)
        ).order_by(Computer.id).limit(1))
    def fallback_ids(excluded, limit):
        has_photo = or_(Computer.images.any(),
                        (Computer.image_url.is_not(None)) & (Computer.image_url != ''))
        first_release = select(func.min(Release.release_date)).where(
            Release.computer_id == Computer.id).correlate(Computer).scalar_subquery()
        fallback = select(Computer.id).where(Computer.id.not_in(excluded)).order_by(
            case((has_photo, 0), else_=1), first_release.asc().nulls_last(), Computer.id
        ).limit(limit)
        return list(db.scalars(fallback))

    selected_ids = list(dict.fromkeys(id for preference in PREFERENCES
                                     if (id := preferred_id(preference)) is not None))
    spotlight_id = preferred_id(SPOTLIGHT_PREFERENCE)
    if spotlight_id is None:
        # Keep the three collection choices when another actual record can
        # fill the showcase. Small archives still never repeat the same card.
        alternative = fallback_ids(selected_ids, 1)
        spotlight_id = alternative[0] if alternative else (selected_ids[0] if selected_ids else None)
    selected_ids = [id for id in selected_ids if id != spotlight_id]
    if len(selected_ids) < 3:
        selected_ids.extend(fallback_ids(selected_ids + ([spotlight_id] if spotlight_id is not None else []),
                                         3 - len(selected_ids)))
    all_ids = selected_ids + ([spotlight_id] if spotlight_id is not None else [])
    # Load relationships only for the showcase and at most three other cards.
    featured = {c.id: c for c in db.scalars(select(Computer).where(
        Computer.id.in_(all_ids)).options(*eager))}
    return {'summary': {'systems': total, 'manufacturers': manufacturers},
            'spotlight': serialize(featured[spotlight_id]) if spotlight_id is not None else None,
            'featured': [serialize(featured[id]) for id in selected_ids]}
