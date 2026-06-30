from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("pendientes/", views.pendientes, name="pendientes"),
    path("exportar/excel/", views.exportar_excel, name="exportar_excel"),
]
