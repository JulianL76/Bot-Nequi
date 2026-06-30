from django.urls import path

from . import views

app_name = "conciliaciones"

urlpatterns = [
    path("", views.conciliar, name="conciliar"),
    path("historial/", views.lista, name="lista"),
    path("lote/<int:lote_id>/", views.lote_detalle, name="lote_detalle"),
    path("lote/<int:lote_id>/progreso/", views.lote_progreso, name="lote_progreso"),
    path("lote/<int:lote_id>/pausar/", views.pausar_conciliacion, name="pausar_conciliacion"),
    path("lote/<int:lote_id>/reanudar/", views.reanudar_conciliacion, name="reanudar_conciliacion"),
    path("lote/<int:lote_id>/reprocesar/", views.reprocesar_lote_conc, name="reprocesar_lote_conc"),
    path("item/<int:pk>/confirmar/", views.confirmar_pendiente, name="confirmar_pendiente"),
    path("item/<int:pk>/ajustar/", views.ajustar_item, name="ajustar_item"),
    path("item/<int:pk>/agregar-confirmar/", views.agregar_confirmar, name="agregar_confirmar"),
    path("item/<int:pk>/reprocesar/", views.reprocesar_item, name="reprocesar_item"),
    path("item/<int:pk>/eliminar/", views.eliminar_item, name="eliminar_item"),
]
