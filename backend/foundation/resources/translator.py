import json
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

_STRINGS_PATH = Path(__file__).resolve().parent / "strings.json"
_STRINGS_CACHE = None


def load_strings():
    global _STRINGS_CACHE
    if _STRINGS_CACHE is None or settings.DEBUG:
        try:
            with open(_STRINGS_PATH, "r", encoding="utf-8") as f:
                _STRINGS_CACHE = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load strings.json: {e}")
            _STRINGS_CACHE = {}
    return _STRINGS_CACHE


def translate(key: str, **kwargs) -> str:
    """
    Translates a resource key using strings.json.
    Missing key raises in development and returns the key in production (with logging).
    (FR-1.91 & Interface Spec §10)
    """
    strings = load_strings()
    if key not in strings:
        msg = f"Missing translatable string key: '{key}'"
        logger.error(msg)
        if settings.DEBUG:
            raise KeyError(msg)
        return key

    template = strings[key]
    try:
        return template.format(**kwargs) if kwargs else template
    except Exception as e:
        logger.error(f"Error formatting string key '{key}': {e}")
        return template

