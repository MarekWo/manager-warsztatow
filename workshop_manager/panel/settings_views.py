"""Panel pages for Settings, e-mail templates and the e-mail log (PRD §7.5, §7.8)."""

import re
from collections.abc import Callable

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csp import csp_override, csp_report_only_override
from django.views.decorators.http import require_POST

from workshop_manager.communications.defaults import (
    DEFAULTS,
    PLACEHOLDERS,
    RECIPIENTS,
    SAMPLE_CONTEXT,
)
from workshop_manager.communications.models import (
    EmailMessage,
    EmailTemplate,
    MessageStatus,
    TemplateKey,
)
from workshop_manager.communications.rendering import render as render_email
from workshop_manager.communications.rendering import site_context
from workshop_manager.communications.services import (
    failed_or_retrying,
    retry_all_waiting,
    retry_now,
    send_test_email,
)
from workshop_manager.core import audit
from workshop_manager.core.models import SiteSettings
from workshop_manager.panel.forms import EmailTemplateForm, SiteSettingsForm, TestEmailForm
from workshop_manager.panel.views import staff_required

#: Changing any of these may fix sending, so waiting messages are tried again at once.
SMTP_FIELDS = {
    "smtp_enabled",
    "smtp_host",
    "smtp_port",
    "smtp_security",
    "smtp_username",
    "smtp_password",
    "smtp_password_clear",
    "from_email",
}

#: E-mail HTML carries inline styles; it is shown in a sandboxed frame with its own policy.
EMAIL_FRAME_CSP = {
    "default-src": ["'none'"],
    "style-src": ["'unsafe-inline'"],
    "img-src": ["*", "data:"],
    "frame-ancestors": ["'self'"],
}


def _email_frame(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    view = csp_override(EMAIL_FRAME_CSP)(view)
    view = csp_report_only_override(EMAIL_FRAME_CSP)(view)
    return xframe_options_sameorigin(view)


# --- Settings ---------------------------------------------------------------------------------


@staff_required
def settings_edit(request: HttpRequest) -> HttpResponse:
    site = SiteSettings.load()
    form = SiteSettingsForm(request.POST or None, request.FILES or None, instance=site)
    if request.method == "POST":
        if form.is_valid():
            smtp_changed = bool(SMTP_FIELDS.intersection(form.changed_data))
            changed = ", ".join(
                str(form.fields[name].label)
                for name in form.changed_data
                if name in form.fields and name != "smtp_password"
            )
            form.save()
            audit.record(request.user, "Zmieniono ustawienia", "Ustawienia", details=changed)
            messages.success(request, "Zapisano ustawienia.")
            if smtp_changed and (waiting := retry_all_waiting()):
                messages.info(
                    request, f"E-maile czekające w kolejce ({waiting}) zostaną wysłane ponownie."
                )
            return redirect("panel:settings")
        messages.error(request, "Popraw zaznaczone pola i zapisz ponownie.")
    context = {
        "form": form,
        "test_form": TestEmailForm(initial={"to_email": getattr(request.user, "email", "")}),
        "site_settings": site,
        "problem_count": failed_or_retrying().count(),
    }
    return render(request, "panel/settings.html", context)


@staff_required
@require_POST
def settings_test_email(request: HttpRequest) -> HttpResponse:
    form = TestEmailForm(request.POST)
    if form.is_valid():
        address = form.cleaned_data["to_email"]
        error = send_test_email(address)
        if error:
            messages.error(
                request, f"Nie udało się wysłać wiadomości testowej. Serwer odpowiedział: {error}"
            )
        else:
            messages.success(
                request,
                f"Wysłano wiadomość testową na {address}. Sprawdź skrzynkę (także folder spam).",
            )
    else:
        messages.error(request, "Podaj poprawny adres e-mail do wiadomości testowej.")
    return redirect(reverse("panel:settings") + "#poczta")


# --- E-mail templates -------------------------------------------------------------------------


def _template_or_404(key: str) -> EmailTemplate:
    if key not in TemplateKey.values:
        raise Http404
    subject, body = DEFAULTS[key]
    template, _created = EmailTemplate.objects.get_or_create(
        key=key, defaults={"subject": subject, "body": body}
    )
    return template


@staff_required
def email_template_list(request: HttpRequest) -> HttpResponse:
    templates = [(_template_or_404(key), RECIPIENTS[key]) for key in TemplateKey.values]
    return render(request, "panel/email_template_list.html", {"templates": templates})


@staff_required
def email_template_edit(request: HttpRequest, key: str) -> HttpResponse:
    template = _template_or_404(key)
    placeholders = PLACEHOLDERS[key]
    form = EmailTemplateForm(request.POST or None, instance=template, placeholders=placeholders)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit.record(request.user, "Zmieniono szablon e-maila", template.get_key_display())
        messages.success(request, "Zapisano szablon e-maila.")
        return redirect("panel:email_template_edit", key=key)
    context = {
        "template": template,
        "form": form,
        "placeholders": placeholders,
        "recipients": RECIPIENTS[key],
    }
    return render(request, "panel/email_template_edit.html", context)


@staff_required
@require_POST
def email_template_reset(request: HttpRequest, key: str) -> HttpResponse:
    template = _template_or_404(key)
    template.subject, template.body = DEFAULTS[key]
    template.save()
    audit.record(request.user, "Przywrócono domyślny szablon e-maila", template.get_key_display())
    messages.success(request, "Przywrócono domyślną treść szablonu.")
    return redirect("panel:email_template_edit", key=key)


@staff_required
@_email_frame
def email_template_preview(request: HttpRequest, key: str) -> HttpResponse:
    """The e-mail as the recipient will see it, filled with example data.

    GET shows the saved template; POST (the "Podgląd" button, aimed at the frame) shows the
    text being edited, before it is saved.
    """
    template = _template_or_404(key)
    subject = request.POST.get("subject", template.subject)
    body = request.POST.get("body", template.body)
    site = SiteSettings.load()
    rendered = render_email(subject, body, site_context(site) | SAMPLE_CONTEXT, site)
    subject_bar = format_html(
        '<div style="font-family:Arial,sans-serif;font-size:15px;padding:10px 16px;'
        'background:#fff;border-bottom:1px solid #ddd;"><strong>Temat:</strong> {}</div>',
        rendered.subject,
    )
    html = re.sub(r"(<body[^>]*>)", lambda m: m[1] + subject_bar, rendered.html, count=1)
    return HttpResponse(html)


# --- E-mail log ---------------------------------------------------------------------------------

LOG_FILTERS = [
    ("", "Wszystkie"),
    ("problems", "Z błędem"),
    ("queued", "W kolejce"),
    ("sent", "Wysłane"),
]


@staff_required
def email_log(request: HttpRequest) -> HttpResponse:
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    emails = EmailMessage.objects.select_related("application")
    if status == "problems":
        emails = emails.filter(
            Q(status=MessageStatus.FAILED) | Q(status=MessageStatus.QUEUED, attempts__gt=0)
        )
    elif status in (MessageStatus.QUEUED, MessageStatus.SENT):
        emails = emails.filter(status=status)
    if query:
        emails = emails.filter(Q(to_email__icontains=query) | Q(subject__icontains=query))
    page = Paginator(emails, 50).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "filters": LOG_FILTERS,
        "status": status,
        "query": query,
        "failed_count": EmailMessage.objects.filter(status=MessageStatus.FAILED).count(),
    }
    return render(request, "panel/email_log.html", context)


@staff_required
def email_detail(request: HttpRequest, pk: int) -> HttpResponse:
    email = get_object_or_404(EmailMessage.objects.select_related("application"), pk=pk)
    return render(request, "panel/email_detail.html", {"email": email})


@staff_required
@_email_frame
def email_html(request: HttpRequest, pk: int) -> HttpResponse:
    email = get_object_or_404(EmailMessage, pk=pk)
    return HttpResponse(email.body_html or "<p>Ta wiadomość nie ma wersji HTML.</p>")


@staff_required
@require_POST
def email_resend(request: HttpRequest, pk: int) -> HttpResponse:
    email = get_object_or_404(EmailMessage, pk=pk)
    was_sent = email.status == MessageStatus.SENT
    target = retry_now(email)
    if was_sent:
        messages.success(request, "Utworzono kopię wiadomości — zostanie wysłana za chwilę.")
    else:
        messages.success(request, "Wiadomość zostanie wysłana ponownie za chwilę.")
    return redirect("panel:email_detail", pk=target.pk)


@staff_required
@require_POST
def email_resend_failed(request: HttpRequest) -> HttpResponse:
    count = retry_all_waiting(include_failed=True)
    messages.success(request, f"Ponowiono wysyłkę wiadomości: {count}.")
    return redirect(reverse("panel:email_log") + "?status=problems")
