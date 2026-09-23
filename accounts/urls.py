from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # El inicio de sesión lo sirve una vista propia (pantalla de React con
    # Inertia); el cierre sigue siendo el de Django, que ya hace lo correcto.
    path("login/", views.entrar, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("registro/", views.registro, name="registro"),
]
