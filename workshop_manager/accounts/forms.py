from allauth.account.forms import RequestLoginCodeForm as BaseRequestLoginCodeForm
from django import forms


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
