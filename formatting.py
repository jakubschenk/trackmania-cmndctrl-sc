"""TrackMania text formatting utilities."""

import re


def strip_tm_formatting(text: str) -> str:
    """Strip TM formatting codes ($fff, $o, $z, etc.) from a string."""
    return re.sub(r'\$([0-9a-fA-F]{3}|[lhp](\[[^\]]*\])?|.)', '', text)


def strip_shadow(text: str) -> str:
    """Strip $s/$S shadow codes from TM text, preserving $$s escaped literals."""
    return re.sub(r'(?<!\$)\$[sS]', '', text)
