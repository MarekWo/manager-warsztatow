"""A person's rights over their data (PRD §8): consents, a copy of the data, anonymisation.

Deleting a person means anonymising them: the applications stay (the workshop's numbers,
levels and statuses still add up), but nothing in them points at a living person any more —
names, addresses, phone, remarks, answers, notes, comments, the e-mails they got and the event
log entries about them. The account is deleted outright. Backups keep the old data until they
rotate out (30 days), which the privacy policy should say.

A person who still holds or waits for a place in a workshop that has not ended cannot be
anonymised: they (or the organiser) record the withdrawal first, so the organiser is told and
the waiting list moves on as usual.
"""

from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils import timezone

from workshop_manager.applications import decisions
from workshop_manager.applications.models import (
    Answer,
    Application,
    ConsentKind,
    ConsentRecord,
    Participant,
    StatusChange,
)
from workshop_manager.core import audit
from workshop_manager.core.models import AuditEvent, SiteSettings

ANONYMOUS_FIRST_NAME = "Anonim"
REMOVED_TEXT = "(usunięto — dane osoby zanonimizowane)"


class CannotAnonymise(Exception):
    """The person still has places to give up, or the address belongs to an administrator."""


# --- Consents --------------------------------------------------------------------------------


def record_consent(
    participant: Participant,
    kind: str,
    *,
    given: bool = True,
    channel: str,
    application: Application | None = None,
    version: str = "",
    text: str | None = None,
) -> ConsentRecord:
    """Write one entry of the consent register, with the wording in force now."""
    if text is None:
        site = SiteSettings.load()
        text = site.privacy_text if kind == ConsentKind.PRIVACY else site.marketing_text
    return ConsentRecord.objects.create(
        participant=participant,
        application=application,
        kind=kind,
        given=given,
        text=text,
        version=version,
        channel=channel,
    )


def set_marketing_consent(participant: Participant, given: bool, *, channel: str) -> bool:
    """Give or withdraw the consent to news about workshops; False when nothing changed."""
    if participant.marketing_consent == given:
        return False
    with transaction.atomic():
        participant.marketing_consent = given
        participant.marketing_consent_at = timezone.now() if given else None
        participant.save(update_fields=["marketing_consent", "marketing_consent_at", "updated_at"])
        record_consent(participant, ConsentKind.MARKETING, given=given, channel=channel)
    return True


# --- Finding a person's data -----------------------------------------------------------------


def participant_for_user(user: Any) -> Participant | None:
    return Participant.objects.filter(Q(user=user) | Q(email=user.email.lower())).first()


def _emails(participant: Participant) -> QuerySet[Any]:
    from workshop_manager.communications.models import EmailMessage

    return EmailMessage.objects.filter(
        Q(application__participant=participant) | Q(to_email__iexact=participant.email)
    )


def blocking_applications(participant: Participant) -> list[Application]:
    """Applications that still hold or wait for a place in a workshop that has not ended."""
    applications = participant.applications.select_related("workshop").prefetch_related(
        "workshop__sessions"
    )
    return [application for application in applications if decisions.can_withdraw(application)]


# --- A copy of the data ----------------------------------------------------------------------


def _moment(value: Any) -> str | None:
    return timezone.localtime(value).isoformat(timespec="seconds") if value else None


def export_data(participant: Participant, *, for_organiser: bool = False) -> dict[str, Any]:
    """Everything stored about the person, in Polish, ready for `json.dumps`.

    `for_organiser` adds the organiser's own notes — part of a formal request handled by the
    administrator, left out of the copy people download themselves.
    """
    site = SiteSettings.load()
    applications = participant.applications.select_related("workshop", "level").prefetch_related(
        "answers", "history"
    )
    data: dict[str, Any] = {
        "wygenerowano": _moment(timezone.now()),
        "administrator_danych": site.org_name,
        "polityka_prywatnosci": site.privacy_policy_url,
        "osoba": {
            "adres_email": participant.email,
            "imie": participant.first_name,
            "nazwisko": participant.last_name,
            "telefon": participant.phone,
            "konto": participant.user_id is not None,
            "zgoda_na_informacje_o_warsztatach": participant.marketing_consent,
            "pierwsze_zgloszenie": _moment(participant.created_at),
        },
        "zgody": [
            {
                "zgoda": consent.get_kind_display(),
                "udzielona": consent.given,
                "kiedy": _moment(consent.created_at),
                "sposob": consent.get_channel_display(),
                "wersja": consent.version,
                "tresc": consent.text,
            }
            for consent in participant.consents.all()
        ],
        "zgloszenia": [],
        "e_maile": [
            {
                "kiedy": _moment(email.sent_at or email.created_at),
                "do": email.to_email,
                "temat": email.subject,
                "tresc": email.body_text,
            }
            for email in _emails(participant).filter(to_email__iexact=participant.email)
        ],
    }
    for application in applications:
        entry: dict[str, Any] = {
            "warsztat": application.workshop.title,
            "poziom": application.level.name,
            "data_zgloszenia": _moment(application.submitted_at),
            "status": application.get_status_display(),
            "imie": application.first_name,
            "nazwisko": application.last_name,
            "adres_email": application.email,
            "telefon": application.phone,
            "uwagi": application.remarks,
            "potwierdzenie_pelnoletnosci": application.adult_confirmed,
            "wersja_klauzuli": application.privacy_consent_version,
            "odpowiedzi": [
                {"pytanie": answer.label, "odpowiedz": answer.value}
                for answer in application.answers.all()
            ],
            "historia": [
                {
                    "kiedy": _moment(change.changed_at),
                    "status": change.get_new_status_display(),
                    "komentarz": change.comment,
                }
                for change in application.history.all()
            ],
        }
        if for_organiser:
            entry["notatki_organizatora"] = application.admin_notes
        data["zgloszenia"].append(entry)
    return data


# --- Anonymisation ---------------------------------------------------------------------------


def anonymise(participant: Participant, *, user: Any, self_service: bool = False) -> None:
    """Remove the person's data for good (see the module docstring); `user` does it.

    Raises `CannotAnonymise` while applications still hold places or when the address belongs
    to an administrator.
    """
    from workshop_manager.accounts.models import User
    from workshop_manager.communications.models import MessageStatus

    if participant.is_anonymised:
        return
    blocking = blocking_applications(participant)
    if blocking:
        titles = ", ".join(sorted({a.workshop.title for a in blocking}))
        raise CannotAnonymise(
            f"Najpierw trzeba zapisać rezygnację ze zgłoszeń na warsztaty, które jeszcze się nie "
            f"skończyły: {titles}."
        )
    accounts = User.objects.filter(Q(pk=participant.user_id) | Q(email=participant.email))
    if accounts.filter(is_staff=True).exists():
        raise CannotAnonymise("Ten adres należy do administratora — nie można go usunąć tutaj.")

    email = participant.email
    anonymous_email = f"anonim-{participant.pk}@anonim.invalid"
    last_name = f"#{participant.pk}"
    application_ids = list(participant.applications.values_list("pk", flat=True))
    panel_urls = [reverse("panel:application_detail", args=[pk]) for pk in application_ids]
    panel_urls.append(participant.get_panel_url())

    with transaction.atomic():
        Application.objects.filter(pk__in=application_ids).update(
            first_name=ANONYMOUS_FIRST_NAME,
            last_name=last_name,
            email=anonymous_email,
            phone="",
            remarks="",
            admin_notes="",
        )
        Answer.objects.filter(application_id__in=application_ids).update(value="")
        StatusChange.objects.filter(application_id__in=application_ids).update(comment="")

        emails = _emails(participant)
        emails.filter(status__in=[MessageStatus.QUEUED, MessageStatus.SENDING]).update(
            status=MessageStatus.FAILED, last_error="Nie wysłano: dane osoby zanonimizowane."
        )
        emails.update(subject=REMOVED_TEXT, body_text=REMOVED_TEXT, body_html="")
        # Last: the address is what finds e-mails not tied to an application.
        emails.filter(to_email__iexact=email).update(to_email=anonymous_email, to_name="")

        target = f"Uczestnik {ANONYMOUS_FIRST_NAME} {last_name}"
        AuditEvent.objects.filter(url__in=panel_urls).update(target=target, details="")
        AuditEvent.objects.filter(actor_email__iexact=email).update(actor_email="")

        accounts.delete()  # allauth's addresses and codes go with it
        participant.first_name = ANONYMOUS_FIRST_NAME
        participant.last_name = last_name
        participant.email = anonymous_email
        participant.phone = ""
        participant.user = None
        participant.marketing_consent = False
        participant.marketing_consent_at = None
        participant.anonymised_at = timezone.now()
        participant.save()
        how = "na prośbę osoby (w jej koncie)" if self_service else "w panelu"
        audit.record(
            None if self_service else user,
            "Usunięto dane osoby (anonimizacja)",
            target,
            url=participant.get_panel_url(),
            details=f"Zgłoszeń: {len(application_ids)}. Wykonano {how}.",
        )
