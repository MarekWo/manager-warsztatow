# Administrator's guide

The full guide for the organiser is **built into the application, in Polish**: *Panel → Pomoc*
(`/panel/pomoc/`), with a "?" next to harder sections of the panel. Participants have their own
short page, *Jak to działa* (`/pomoc/`), linked in the footer. This page is a summary for the
technical operator and for anyone reading the repository.

## Help chapters

| Chapter | Covers |
|---|---|
| Pierwsze kroki | Signing in with a code, the panel's menu, the life of one workshop. |
| Jak utworzyć warsztat | New or duplicated workshop, sessions, levels and their soft capacity, sections, publication at a set time, the registration window, quick actions, cancelling, locations. |
| Jak ustawić formularz | Standard fields, question kinds, level-bound questions, hiding instead of deleting, templates. |
| Jak rozpatrywać zgłoszenia | Statuses and allowed changes, the decision window with an editable e-mail, bulk decisions, the waiting list and the freed-place suggestion, phone applications, corrections, notes, the event log. |
| Uczestnicy i ich konta | How accounts appear, the code and the one-click link, "Moje warsztaty", withdrawals, the people register. |
| Jak wysłać wiadomość do uczestników | Recipient groups, placeholders, attachment, preview before sending. |
| Wydruki i eksporty | Excel, attendance list, contact list, materials summary (HTML and PDF). |
| Ustawienia poczty i treść e-maili | Own SMTP or the installation's mail, Google app passwords, the test e-mail, notifications, templates and placeholders, the e-mail log and retries. |
| Ustawienia i słowniki | Organisation, logo, bank account, consent texts and versions, workshop types, form templates. |
| RODO — dane osobowe | Consents and the register, a person's data copy, anonymisation, unsubscribing, retention. |
| Najczęstsze pytania | Short answers to typical situations. |

Keeping the help current is part of every functional change: the chapter is updated in the same
commit, and `tests/test_help.py` checks that every "?" in the panel points at a section that
exists. Screenshots come from the demo data: `uv run pytest -m screenshots` retakes them into
`workshop_manager/static/help/`.

## Operator's tasks

| Task | How |
|---|---|
| Update the application | `scripts/update.sh X.Y.Z` (backup, pull, start, health check) — [deploy.md](deploy.md). |
| Add an administrator | `/django-admin/` → *Użytkownicy* → add the address, tick *Status administratora* (and *Status superużytkownika* for full technical access). They sign in with a code. |
| Remove an administrator | Untick *Status administratora* (or *Aktywny*) for that user. |
| Check health | `/healthz` (`db`, `worker`, version); the panel's dashboard shows e-mails that failed. |
| Mail does not go out | Panel → *Ustawienia* → test e-mail; the e-mail log shows the server's error. The fallback transport is `EMAIL_URL`. |
| Restore data | `scripts/restore.sh backups/<stamp> --check`, then without `--check` — [deploy.md](deploy.md#backups). |
| Logs | `docker compose logs --tail=200 web worker`. |

## Data protection duties

- Backups hold personal data for 30 days after it is deleted in the application; say so in the
  privacy policy if the organiser requires it.
- The technical admin (`/django-admin/`) shows raw data; give superuser status only to the
  operator.
- A request for data or deletion is handled in the panel (*Uczestnicy* → the person's card), not
  in the database, so that the event log records it.
