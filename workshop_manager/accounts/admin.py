from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from workshop_manager.accounts.models import User


class UserAddForm(forms.ModelForm):
    """Only the address: everybody signs in with a code (ADR-0001), so there is no password.

    Django's own add form asks for a password; its fields are not on this page, so the form
    failed with nothing to show.
    """

    class Meta:
        model = User
        fields = ("email",)

    def save(self, commit: bool = True) -> Any:
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
        return user


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """The Django admin is the technical superuser's tool; administrators use the panel."""

    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active", "last_login")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dane osobowe", {"fields": ("first_name", "last_name", "phone")}),
        (
            "Uprawnienia",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Daty", {"fields": ("last_login", "date_joined")}),
    )
    add_form = UserAddForm
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email",)}),)
