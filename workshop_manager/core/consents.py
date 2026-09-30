"""Default consent texts for the application form (PRD §8).

These are only the starting values of `SiteSettings`; the administrator edits the wording in
Settings. Each accepted consent is stored with the version it was given under, so a later change
of the wording never rewrites what a person agreed to.
"""

PRIVACY_VERSION = "2026-10-v1"

PRIVACY_TEXT = (
    "Wyrażam zgodę na przetwarzanie i przechowywanie moich danych osobowych przez "
    "Chrześcijańskie Stowarzyszenie Twórców Sztuki Sakralnej „Ecclesia” w celu organizacji "
    "warsztatów. Dane są wyłącznie na użytek wewnętrzny organizatorów i nie są nikomu "
    "udostępniane. Mogę w każdej chwili zażądać wglądu w nie, ich poprawienia lub usunięcia."
)

PRIVACY_POLICY_URL = "https://ecclesia.jezuici.pl/polityka-prywatnosci-cookies/"

MARKETING_TEXT = "Chcę otrzymywać e-mailem informacje o kolejnych warsztatach Stowarzyszenia."
