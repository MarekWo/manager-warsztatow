from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "workshop_manager.accounts"
    label = "accounts"
    verbose_name = "Konta"

    def ready(self) -> None:
        from workshop_manager.accounts import sessions  # noqa: F401  (signal receivers)
