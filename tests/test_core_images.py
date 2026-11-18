"""Workshop photos are stored at one sensible size (core.images)."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image

from tests.factories import AdminFactory, WorkshopFactory
from tests.test_panel_workshops import edit_payload, full_workshop
from workshop_manager.core import images
from workshop_manager.workshops.models import Workshop


def picture(width: int, height: int, fmt: str = "PNG", mode: str = "RGB") -> bytes:
    output = BytesIO()
    Image.new(mode, (width, height), "navy").save(output, format=fmt)
    return output.getvalue()


def test_a_large_photo_is_brought_down_keeping_its_proportions():
    upload = SimpleUploadedFile("Zdjęcie z aparatu.png", picture(4000, 3000))
    smaller = images.shrink(upload)
    assert smaller.name == "Zdjęcie z aparatu.jpg"
    with Image.open(smaller) as result:
        assert result.size == (1200, 900)
        assert result.format == "JPEG"


def test_an_opaque_alpha_channel_does_not_keep_a_photo_as_png():
    upload = SimpleUploadedFile("obraz.png", picture(2400, 600, mode="RGBA"))
    with Image.open(images.shrink(upload)) as result:
        assert result.format == "JPEG"


def test_transparency_survives_as_png():
    output = BytesIO()
    Image.new("RGBA", (2400, 600), (10, 20, 120, 0)).save(output, format="PNG")
    upload = SimpleUploadedFile("logo.png", output.getvalue())
    smaller = images.shrink(upload)
    with Image.open(smaller) as result:
        assert (result.format, result.size) == ("PNG", (1200, 300))


def test_a_small_photo_is_not_enlarged():
    with Image.open(images.shrink(SimpleUploadedFile("mini.jpg", picture(300, 200, "JPEG")))) as r:
        assert r.size == (300, 200)


@pytest.mark.django_db
def test_the_panel_stores_an_uploaded_photo_resized(client):
    workshop = full_workshop()
    client.force_login(AdminFactory())
    photo = SimpleUploadedFile("ramy.png", picture(3000, 3000), "image/png")
    response = client.post(
        reverse("panel:workshop_edit", args=[workshop.pk]),
        edit_payload(workshop, cover_image=photo),
    )
    assert response.status_code == 302
    workshop.refresh_from_db()
    assert workshop.cover_image.name.endswith(".jpg")
    assert (workshop.cover_image.width, workshop.cover_image.height) == (1200, 1200)


@pytest.mark.django_db
def test_photos_uploaded_earlier_are_resized_once():
    workshop = WorkshopFactory(cover_image=SimpleUploadedFile("stare.png", picture(2600, 1300)))
    copy = WorkshopFactory(cover_image=workshop.cover_image.name)  # a duplicate shares the file
    call_command("shrink_photos", verbosity=0)
    workshop.refresh_from_db()
    copy.refresh_from_db()
    assert workshop.cover_image.name == copy.cover_image.name
    assert workshop.cover_image.width == 1200
    name = workshop.cover_image.name
    call_command("shrink_photos", verbosity=0)
    assert Workshop.objects.get(pk=workshop.pk).cover_image.name == name
