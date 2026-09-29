from django.urls import path

from workshop_manager.panel import views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
