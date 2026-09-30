from allauth.account.forms import RequestLoginCodeForm as BaseRequestLoginCodeForm
from django import forms

from workshop_manager.accounts.services import ensure_account


class RequestLoginCodeForm(BaseRequestLoginCodeForm):
    """Email address plus "remember me": allauth's code login has no such choice of its own."""

    remember = forms.BooleanField(
        label="Zapamiętaj mnie na tym urządzeniu",
        required=False,
        initial=True,
        help_text="Nie zaznaczaj na cudzym lub wspólnym komputerze.",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Adres e-mail"
        self.fields["email"].widget.attrs.update(
            {"placeholder": "np. jan.kowalski@gmail.com", "autocomplete": "email"}
        )

    def clean_email(self) -> str:
        """Someone who has applied before gets their account now, before the code is sent.

        Nothing about it shows on the page: a known and an unknown address look the same.
        """
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email:
            ensure_account(email)
        self.cleaned_data["email"] = email
        return super().clean_email()
