"""Where e-mail goes out: the SMTP server from Settings, or the installation's `EMAIL_URL`.

With "wysyłaj przez poniższy serwer SMTP" switched on, the connection and the sender come from
`SiteSettings`. Otherwise the default mailer (`MAILERS`, built from `EMAIL_URL`) is used with
`DEFAULT_FROM_EMAIL` as the sender, because that server usually accepts no other sender. In both
cases replies go to the Reply-To from Settings, or else to the organiser's contact address.
"""

from dataclasses import dataclass
from email.headerregistry import Address

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend

from workshop_manager.core.models import SiteSettings, SmtpSecurity

#: Seconds to wait for the SMTP server — a worker must not hang on a dead server.
SMTP_TIMEOUT = 15


@dataclass
class Transport:
    connection: BaseEmailBackend
    from_email: str
    reply_to: str


def format_address(address: str, name: str = "") -> str:
    """`Name <address>` with whatever quoting the name needs (commas, quotes, Polish letters)."""
    if not name:
        return address
    return str(Address(display_name=name, addr_spec=address))


def transport(site: SiteSettings | None = None) -> Transport:
    site = site or SiteSettings.load()
    reply_to = site.reply_to or site.contact_email
    if site.uses_own_smtp():
        connection = SmtpBackend(
            alias="site-settings",
            host=site.smtp_host,
            port=site.smtp_port,
            username=site.smtp_username,
            password=site.smtp_password,
            use_tls=site.smtp_security == SmtpSecurity.STARTTLS,
            use_ssl=site.smtp_security == SmtpSecurity.SSL,
            timeout=SMTP_TIMEOUT,
        )
        sender = site.from_email or site.smtp_username
        from_email = format_address(sender, site.from_name or site.org_short_name)
        return Transport(connection, from_email, reply_to)
    return Transport(mail.mailers.default, settings.DEFAULT_FROM_EMAIL, reply_to)


def build(
    *,
    to_email: str,
    to_name: str = "",
    subject: str,
    text: str,
    html: str = "",
    reply_to: str = "",
    from_email: str,
) -> EmailMultiAlternatives:
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=from_email,
        to=[format_address(to_email, to_name)],
        reply_to=[reply_to] if reply_to else None,
    )
    if html:
        message.attach_alternative(html, "text/html")
    return message


def send_now(message: EmailMultiAlternatives, connection: BaseEmailBackend) -> None:
    """Send one message; raises whatever the backend raises (the caller records it)."""
    connection.send_messages([message])
