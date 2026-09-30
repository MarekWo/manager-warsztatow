from django.urls import path

from workshop_manager.public import account_views, views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("warsztaty/<slug:slug>/", views.workshop_detail, name="workshop"),
    path("warsztaty/<slug:slug>/zgloszenie/", views.apply, name="apply"),
    path(
        "warsztaty/<slug:slug>/zgloszenie/wyslane/", views.application_sent, name="application_sent"
    ),
    # The participant's pages (PRD §6.5)
    path("moje-warsztaty/", account_views.my_workshops, name="my_workshops"),
    path("moje-warsztaty/<int:pk>/", account_views.my_application, name="my_application"),
    path("moje-dane/", account_views.my_data, name="my_data"),
    path("rezygnacja/<str:token>/", account_views.withdraw, name="withdraw"),
]
