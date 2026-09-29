from django.contrib import admin

from workshop_manager.applications.models import Answer, Application, Participant


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ("label", "value", "question")
    can_delete = False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """The technical superuser's view; administrators review applications in the panel."""

    list_display = ("full_name", "email", "workshop", "level", "status", "submitted_at")
    list_filter = ("status", "workshop")
    search_fields = ("last_name", "first_name", "email")
    inlines = [AnswerInline]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "email", "marketing_consent", "user")
    search_fields = ("last_name", "first_name", "email")
