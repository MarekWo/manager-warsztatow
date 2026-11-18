"""Bring uploaded photos down to one sensible size.

People upload what the camera or a website gave them — several thousand pixels and megabytes —
and the pages would send exactly that to every phone. A workshop's photo is stored no larger
than `COVER_MAX` on its longer side, as JPEG (PNG when it has transparency), with the camera's
rotation applied; the templates then show it in a fixed frame.
"""

from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

#: Longest side of a stored workshop photo, in pixels: sharp on a phone at double density and in
#: the widest column of the workshop page.
COVER_MAX = 1200
JPEG_QUALITY = 85


def needs_shrinking(image: Image.Image, max_side: int = COVER_MAX) -> bool:
    return max(image.size) > max_side


def shrink(file: Any, *, max_side: int = COVER_MAX) -> ContentFile:
    """`file` (an upload or a stored file) as a new file no larger than `max_side`.

    Always re-encoded, so a 6 MB photo that already fits the limit gets smaller too.
    """
    file.seek(0)
    image: Image.Image = Image.open(file)
    image = ImageOps.exif_transpose(image)
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    transparent = image.mode in ("RGBA", "LA") or "transparency" in image.info
    output = BytesIO()
    stem = PurePosixPath(getattr(file, "name", "") or "zdjecie").stem or "zdjecie"
    if transparent:
        image.save(output, format="PNG", optimize=True)
        name = f"{stem}.png"
    else:
        image.convert("RGB").save(
            output, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True
        )
        name = f"{stem}.jpg"
    return ContentFile(output.getvalue(), name=name)
