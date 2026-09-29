"""Text helpers that Django's own do not cover for Polish."""

from django.db.models import Model
from django.utils.text import slugify

# NFKD (which slugify relies on) decomposes ą, ę, ó, ś, … but not ł, so it would vanish.
_POLISH = str.maketrans({"ł": "l", "Ł": "L"})


def polish_slugify(value: str) -> str:
    return slugify(value.translate(_POLISH))


def unique_slug(model: type[Model], value: str, *, max_length: int = 200) -> str:
    """A slug for `value` not yet used by any row of `model` (`-2`, `-3`, … appended)."""
    base = polish_slugify(value)[:max_length].strip("-") or "warsztat"
    slug, n = base, 2
    while model._default_manager.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
