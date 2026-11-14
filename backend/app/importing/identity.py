"""Explicit spelling aliases only; families and individual models stay distinct."""
from .normalize import name_key
from .regional_names import regional_name

MAKERS = {
    'apple': ('Apple', 'Apple Computer', 'Apple Computer Inc.', 'Apple Computer, Inc.', 'Apple Inc.'),
    'ibm': ('IBM', 'International Business Machines', 'International Business Machines Corporation'),
    'commodore': ('Commodore', 'Commodore Business Machines', 'Commodore Business Machines, Inc.', 'Commodore Business Machines (USA)'),
    'dec': ('DEC', 'Digital Equipment Corporation'),
}
MANUFACTURERS = {name_key(alias): key for key, aliases in MAKERS.items() for alias in aliases}
MODELS = {
    'apple': (('Apple II', 'II', 'Apple ]['), ('Apple IIc', 'Apple //c'), ('Apple IIe', 'Apple //e'),
              ('Apple III', 'Apple ///'), ('Macintosh 128K', 'Apple Macintosh 128K')),
    'ibm': (('IBM PC 5150', 'IBM Personal Computer 5150', 'IBM Personal Computer Model 5150', 'PC 5150'),),
    'commodore': (('Commodore 64', 'C64'),),
}


def maker_key(name):
    normalized = name_key(name)
    return MANUFACTURERS.get(normalized, normalized)


def model_key(manufacturer, name):
    normalized = name_key(regional_name(name))
    for aliases in MODELS.get(maker_key(manufacturer), ()):
        if normalized in {name_key(alias) for alias in aliases}:
            return name_key(aliases[0])
    return normalized


def computer_key(manufacturer, model):
    return maker_key(manufacturer), model_key(manufacturer, model)
