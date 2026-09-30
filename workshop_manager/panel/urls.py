from django.urls import path

from workshop_manager.panel import (
    application_views,
    dictionary_views,
    report_views,
    settings_views,
    views,
)

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

urlpatterns += [
    # Applications (PRD §7.3) and the event log (PRD §7.9)
    path("zgloszenia/", application_views.application_list, name="application_list"),
    path("zgloszenia/grupowo/", application_views.application_bulk, name="application_bulk"),
    path("zgloszenia/<int:pk>/", application_views.application_detail, name="application_detail"),
    path(
        "zgloszenia/<int:pk>/decyzja/<slug:status>/",
        application_views.application_decide,
        name="application_decide",
    ),
    path(
        "zgloszenia/<int:pk>/poziom/", application_views.application_level, name="application_level"
    ),
    path("zgloszenia/<int:pk>/dane/", application_views.application_edit, name="application_edit"),
    path(
        "zgloszenia/<int:pk>/rezerwa/<slug:direction>/",
        application_views.application_waitlist_move,
        name="application_waitlist_move",
    ),
    path(
        "warsztaty/<int:pk>/zgloszenia/",
        application_views.workshop_applications,
        name="workshop_applications",
    ),
    path(
        "warsztaty/<int:pk>/zgloszenia/nowe/",
        application_views.application_add,
        name="application_add",
    ),
    path("dziennik/", application_views.audit_log, name="audit_log"),
]

urlpatterns += [
    # Messages to participants (PRD §7.5), printouts and exports (PRD §7.6)
    path("warsztaty/<int:pk>/wiadomosci/", report_views.broadcast_list, name="broadcast_list"),
    path("warsztaty/<int:pk>/wiadomosci/nowa/", report_views.broadcast_edit, name="broadcast_add"),
    path(
        "warsztaty/<int:pk>/wiadomosci/<int:broadcast_pk>/",
        report_views.broadcast_preview,
        name="broadcast_preview",
    ),
    path(
        "warsztaty/<int:pk>/wiadomosci/<int:broadcast_pk>/edytuj/",
        report_views.broadcast_edit,
        name="broadcast_edit",
    ),
    path(
        "warsztaty/<int:pk>/wiadomosci/<int:broadcast_pk>/wyslij/",
        report_views.broadcast_send,
        name="broadcast_send",
    ),
    path(
        "warsztaty/<int:pk>/wiadomosci/<int:broadcast_pk>/usun/",
        report_views.broadcast_delete,
        name="broadcast_delete",
    ),
    path("warsztaty/<int:pk>/zestawienia/", report_views.report_index, name="report_index"),
    path("warsztaty/<int:pk>/zgloszenia.xlsx", report_views.export_xlsx, name="export_xlsx"),
    path("warsztaty/<int:pk>/lista-obecnosci/", report_views.attendance, name="attendance"),
    path("warsztaty/<int:pk>/lista-kontaktowa/", report_views.contacts, name="contacts"),
    path("warsztaty/<int:pk>/materialy/", report_views.materials, name="materials"),
]
