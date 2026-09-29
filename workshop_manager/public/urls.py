from django.urls import path

from workshop_manager.public import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
]
