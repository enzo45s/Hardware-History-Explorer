"""Documented IBM commercial names; machine types retain configuration scope."""
import re

FAMILIES = {
    'PS/2 Model 30-286': ('8530-H31',),
    'PS/2 Model 35 SX': ('8535-043',),
    'PS/2 Model 50': ('8550-021',),
    'PS/2 Model 50 Z': ('8550-061',),
    'PS/2 Model 55 SX': ('8555-081',),
    'PS/2 Model 80': ('8580-071', '8580-111'),
}


def commercial_name(value):
    name = re.sub(r'^IBM\s+', '', value.strip(), flags=re.I)
    for canonical, codes in FAMILIES.items():
        if name.casefold() in {canonical.casefold(), *(('PS/2 '+code).casefold() for code in codes)}:
            return canonical
    return None  # Unknown suffixes are never guessed from the machine type.
