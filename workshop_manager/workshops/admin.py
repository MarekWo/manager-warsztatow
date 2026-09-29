from django.contrib import admin

from workshop_manager.workshops.models import Level, Location, Session, Workshop, WorkshopType


class SessionInline(admin.TabularInline):
    model = Session
    extra = 0


class LevelInline(admin.TabularInline):
    model = Level
    extra = 0


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    """The technical superuser's view; administrators work in the panel."""

    list_display = ("title", "type", "publish_at", "is_archived")
    list_filter = ("type", "is_archived")
    search_fields = ("title",)
    inlines = [SessionInline, LevelInline]


admin.site.register(WorkshopType)
admin.site.register(Location)
