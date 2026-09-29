import tomllib
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from workshop_manager import __version__

ROOT = Path(__file__).resolve().parents[1]


def _pep440(version: str) -> str:
    """`1.2.0-dev` in VERSION is `1.2.0.dev0` in pyproject.toml."""
    return version.replace("-dev", ".dev0")


def test_pyproject_version_matches_version_file():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == _pep440(__version__)


def test_polish_only():
    assert settings.LANGUAGE_CODE == "pl"
    assert [code for code, _name in settings.LANGUAGES] == ["pl"]


@pytest.mark.django_db
def test_schedules_are_idempotent():
    from django_q.models import Schedule

    call_command("ensure_schedules")
    call_command("ensure_schedules")
    assert Schedule.objects.filter(name="heartbeat").count() == 1
