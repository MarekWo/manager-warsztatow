from django.urls import path

from workshop_manager.help import views

app_name = "help"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:slug>/", views.chapter, name="chapter"),
]
