from django.urls import path

from workshop_manager.panel import dictionary_views, settings_views, views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("warsztaty/", views.workshop_list, name="workshop_list"),
    path("miejsca/", views.location_list, name="location_list"),
    path("miejsca/nowe/", views.location_edit, name="location_add"),
    path("miejsca/<int:pk>/", views.location_edit, name="location_edit"),
    path("warsztaty/nowy/", views.workshop_create, name="workshop_create"),
    path("warsztaty/wiersz/<slug:prefix>/", views.formset_row, name="formset_row"),
    path("warsztaty/<int:pk>/", views.workshop_edit, name="workshop_edit"),
    path("warsztaty/<int:pk>/akcja/<slug:action>/", views.workshop_action, name="workshop_action"),
    path("warsztaty/<int:pk>/duplikuj/", views.workshop_duplicate, name="workshop_duplicate"),
    path("warsztaty/<int:pk>/usun/", views.workshop_delete, name="workshop_delete"),
    path("warsztaty/<int:pk>/formularz/", views.form_editor, name="form_editor"),
    path(
        "warsztaty/<int:pk>/formularz/z-szablonu/",
        views.questions_from_template,
        name="questions_from_template",
    ),
    path("warsztaty/<int:pk>/formularz/pytanie/", views.question_edit, name="question_add"),
    path(
        "warsztaty/<int:pk>/formularz/pytanie/<int:question_pk>/",
        views.question_edit,
        name="question_edit",
    ),
    path(
        "warsztaty/<int:pk>/formularz/pytanie/<int:question_pk>/przesun/<slug:direction>/",
        views.question_move,
        name="question_move",
    ),
    path(
        "warsztaty/<int:pk>/formularz/pytanie/<int:question_pk>/widocznosc/",
        views.question_toggle,
        name="question_toggle",
    ),
    path(
        "warsztaty/<int:pk>/formularz/pytanie/<int:question_pk>/usun/",
        views.question_delete,
        name="question_delete",
    ),
    # Settings and e-mail
    path("ustawienia/", settings_views.settings_edit, name="settings"),
    path("ustawienia/test/", settings_views.settings_test_email, name="settings_test_email"),
    path("ustawienia/e-maile/", settings_views.email_template_list, name="email_template_list"),
    path(
        "ustawienia/e-maile/<slug:key>/",
        settings_views.email_template_edit,
        name="email_template_edit",
    ),
    path(
        "ustawienia/e-maile/<slug:key>/domyslny/",
        settings_views.email_template_reset,
        name="email_template_reset",
    ),
    path(
        "ustawienia/e-maile/<slug:key>/podglad/",
        settings_views.email_template_preview,
        name="email_template_preview",
    ),
    path("e-maile/", settings_views.email_log, name="email_log"),
    path("e-maile/ponow-nieudane/", settings_views.email_resend_failed, name="email_resend_failed"),
    path("e-maile/<int:pk>/", settings_views.email_detail, name="email_detail"),
    path("e-maile/<int:pk>/html/", settings_views.email_html, name="email_html"),
    path("e-maile/<int:pk>/ponow/", settings_views.email_resend, name="email_resend"),
    # Dictionaries
    path("ustawienia/rodzaje/", dictionary_views.type_list, name="dictionary_type_list"),
    path("ustawienia/rodzaje/nowy/", dictionary_views.type_edit, name="dictionary_type_add"),
    path("ustawienia/rodzaje/<int:pk>/", dictionary_views.type_edit, name="dictionary_type_edit"),
    path("ustawienia/szablony/", dictionary_views.template_list, name="dictionary_template_list"),
    path(
        "ustawienia/szablony/nowy/", dictionary_views.template_edit, name="dictionary_template_add"
    ),
    path(
        "ustawienia/szablony/<int:pk>/",
        dictionary_views.template_edit,
        name="dictionary_template_edit",
    ),
    path(
        "ustawienia/szablony/<int:pk>/usun/",
        dictionary_views.template_delete,
        name="dictionary_template_delete",
    ),
    path(
        "ustawienia/szablony/<int:pk>/pytanie/",
        dictionary_views.template_question_edit,
        name="dictionary_question_add",
    ),
    path(
        "ustawienia/szablony/<int:pk>/pytanie/<int:question_pk>/",
        dictionary_views.template_question_edit,
        name="dictionary_question_edit",
    ),
    path(
        "ustawienia/szablony/<int:pk>/pytanie/<int:question_pk>/przesun/<slug:direction>/",
        dictionary_views.template_question_move,
        name="dictionary_question_move",
    ),
    path(
        "ustawienia/szablony/<int:pk>/pytanie/<int:question_pk>/usun/",
        dictionary_views.template_question_delete,
        name="dictionary_question_delete",
    ),
]
