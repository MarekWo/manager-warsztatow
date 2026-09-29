from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from workshop_manager.accounts.models import User


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
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email",)}),)
