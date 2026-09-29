from django.urls import path

from workshop_manager.public import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("warsztaty/<slug:slug>/", views.workshop_detail, name="workshop"),
]
