"""Unambiguous capacity notation only; ranges, bits and options stay textual."""
import re


def ram_literal(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(B|kB|KB|KiB|MB|MiB|GB|GiB)\s*(?:di\s+RAM|RAM)?\s*', value)
    if not match:
        return None
    number = float(match[1].replace(',', '.'))
    return (number, match[2]) if 0 < number <= 1e12 else None
