"""Bounded, read-only selection for the museum entrance. No seeded content."""
from sqlalchemy import case, func, or_, select

from .models import Computer, ComputerImage, Manufacturer, Release


# Editorial display preferences, not identity/deduplication rules. All links
# and images come from the actual records in this archive, never fixed IDs.
PREFERENCES = (
    (('commodore', 'commodore business machines'), ('commodore 64', 'c64')),
    (('olivetti',), ('programma 101', 'olivetti programma 101')),
    (('ibm', 'international business machines'), ('ibm pc 5150', 'pc 5150', 'ibm pc')),
)


def home_data(db, serialize, eager):
    total = db.scalar(select(func.count()).select_from(Computer))
    manufacturers = db.scalar(select(func.count()).select_from(Manufacturer))
    selected_ids = []
    for makers, models in PREFERENCES:
        match = db.scalar(select(Computer.id).join(Computer.manufacturer).where(
            func.lower(func.trim(Computer.model_name)).in_(models),
            func.lower(func.trim(Manufacturer.name)).in_(makers)
        ).order_by(Computer.id).limit(1))
        if match is not None and match not in selected_ids:
            selected_ids.append(match)
    if len(selected_ids) < 3:
        has_photo = or_(Computer.images.any(),
                        (Computer.image_url.is_not(None)) & (Computer.image_url != ''))
        first_release = select(func.min(Release.release_date)).where(
            Release.computer_id == Computer.id).correlate(Computer).scalar_subquery()
        fallback = select(Computer.id).where(Computer.id.not_in(selected_ids)).order_by(
            case((has_photo, 0), else_=1), first_release.asc().nulls_last(), Computer.id
        ).limit(3 - len(selected_ids))
        selected_ids.extend(db.scalars(fallback))
    # Load photo/description relationships for these three records only.
    featured = {c.id: c for c in db.scalars(select(Computer).where(
        Computer.id.in_(selected_ids)).options(*eager))}
    return {'summary': {'systems': total, 'manufacturers': manufacturers},
            'featured': [serialize(featured[id]) for id in selected_ids]}
