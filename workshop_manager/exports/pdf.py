"""Printable lists as PDF (WeasyPrint), from the same templates as the print pages.

WeasyPrint needs Pango, which the Docker image has; on a machine without it the import fails
and the panel offers the print page only (`available()`). Fonts: DejaVu Sans from the image
has every Polish letter.
"""

from typing import Any

from django.template.loader import render_to_string


def available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def render_pdf(template: str, context: dict[str, Any]) -> bytes:
    from weasyprint import HTML

    html = render_to_string(template, context | {"for_pdf": True})
    return HTML(string=html).write_pdf()
