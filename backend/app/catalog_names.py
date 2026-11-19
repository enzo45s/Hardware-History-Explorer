"""Public model names exclude source/variant annotations, without losing originals."""
import re


VIDEO = r'(?:PAL(?:-[A-Z]+)?|NTSC(?:-[A-Z]+)?|SECAM|(?:50|60)\s*Hz)'


def split_name(value):
    text = re.sub(r'\\(?=[()[\]])', '', value or '').strip()
    output, attributes = [], []
    i = 0
    while i < len(text):
        if text[i] not in '([':
            output.append(text[i]); i += 1; continue
        stack, end = [text[i]], i + 1
        while end < len(text) and stack:
            char = text[end]
            if char in '([':
                stack.append(char)
            elif char in ')]':
                if stack[-1] != {')': '(', ']': '['}[char]:
                    break
                stack.pop()
            end += 1
        if stack:
            output.append(text[i]); i += 1; continue
        attributes.append(text[i + 1:end - 1].strip())
        output.append(' '); i = end
    base = ' '.join(''.join(output).split())
    suffix = re.fullmatch(rf'(.+?)\s+({VIDEO})', base, re.I)
    if suffix:
        base = suffix[1].strip(); attributes.append(suffix[2])
    # A wholly parenthesized name or a malformed name must not become empty.
    return (base or text), attributes


def catalog_name(value):
    return split_name(value)[0]


def video_attribute(value):
    return re.fullmatch(rf'{VIDEO}(?:\s*[,;/+]\s*{VIDEO})*', value.strip(), re.I) is not None


def video_only_variant(value):
    _, attributes = split_name(value)
    return bool(attributes) and all(video_attribute(a) for a in attributes)
