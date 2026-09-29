from django.contrib import admin

from workshop_manager.forms_builder.models import FormTemplate, Question, TemplateQuestion


class TemplateQuestionInline(admin.TabularInline):
    model = TemplateQuestion
    extra = 0


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    inlines = [TemplateQuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("label", "workshop", "kind", "required", "is_active")
    list_filter = ("kind",)
