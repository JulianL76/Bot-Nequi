from django.urls import path

from . import views

app_name = "comprobantes"

urlpatterns = [
    path("subir/", views.subir, name="subir"),
    path("subidas/", views.lotes, name="lotes"),
    path("subidas/en-proceso/", views.en_proceso, name="en_proceso"),
    path("lote/<int:lote_id>/", views.lote_detalle, name="lote_detalle"),
    path("lote/<int:lote_id>/progreso/", views.lote_progreso, name="lote_progreso"),
    path("lote/<int:lote_id>/reprocesar/", views.reprocesar, name="reprocesar"),
    path("lote/<int:lote_id>/eliminar/", views.eliminar_lote, name="eliminar_lote"),
    path("lote/<int:lote_id>/pausar/", views.pausar_lote, name="pausar_lote"),
    path("lote/<int:lote_id>/reanudar/", views.reanudar_lote, name="reanudar_lote"),
    path("rutas/", views.rutas, name="rutas"),
    path("rutas/<int:pk>/toggle/", views.ruta_toggle, name="ruta_toggle"),
    path("", views.lista, name="lista"),
    path("exportar/", views.exportar_lista, name="exportar_lista"),
    path("importar/", views.importar_excel, name="importar"),
    path("acciones/", views.acciones_lote, name="acciones_lote"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar, name="eliminar"),
    path("notificaciones/", views.notificaciones, name="notificaciones"),
]
