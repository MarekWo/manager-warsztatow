from django.contrib import admin

from workshop_manager.communications.models import EmailMessage, EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "subject", "updated_at")


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    """The technical view; administrators use the e-mail log in the panel."""

    list_display = ("subject", "to_email", "status", "attempts", "created_at", "sent_at")
    list_filter = ("status", "template_key")
    search_fields = ("to_email", "subject")
    readonly_fields = ("application", "created_by")
