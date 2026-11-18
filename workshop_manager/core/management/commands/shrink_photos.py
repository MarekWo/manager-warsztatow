"""Shrink workshop photos uploaded before uploads were resized (core.images).

Idempotent: a photo already within the limit is left alone, so it is safe to run again. Every
workshop sharing a file (duplicates do) is pointed at the new one.
"""

from typing import Any

from django.core.management.base import BaseCommand
from PIL import Image

from workshop_manager.core import images
from workshop_manager.workshops.models import Workshop


class Command(BaseCommand):
    help = "Resize workshop photos that are larger than the standard size."

    def handle(self, *args: Any, **options: Any) -> None:
        names = (
            Workshop.objects.exclude(cover_image="")
            .values_list("cover_image", flat=True)
            .distinct()
        )
        shrunk = 0
        for name in list(names):
            workshop = Workshop.objects.filter(cover_image=name).first()
            if workshop is None:
                continue
            storage = workshop.cover_image.storage
            if not storage.exists(name):
                self.stderr.write(f"missing file: {name}")
                continue
            with storage.open(name) as stored:
                with Image.open(stored) as picture:
                    too_large = images.needs_shrinking(picture)
                if not too_large:
                    continue
                smaller = images.shrink(stored)
            folder = name.rsplit("/", 1)[0] if "/" in name else ""
            new_name = storage.save(f"{folder}/{smaller.name}".lstrip("/"), smaller)
            Workshop.objects.filter(cover_image=name).update(cover_image=new_name)
            storage.delete(name)
            shrunk += 1
            self.stdout.write(f"{name} -> {new_name}")
        self.stdout.write(f"{shrunk} photo(s) resized.")
