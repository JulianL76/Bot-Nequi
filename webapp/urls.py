import time
"""URL configuration for webapp project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

# Cambia en cada arranque del proceso (o sea, en cada despliegue): hace que
# el service worker tire los cachés viejos en vez de servir assets rancios.
CACHE_VERSION = str(int(time.time()))

urlpatterns = [
    path('admin/', admin.site.urls),
    # PWA: manifest y service worker servidos desde la raíz (scope "/").
    path('manifest.webmanifest',
         TemplateView.as_view(template_name='pwa/manifest.webmanifest',
                              content_type='application/manifest+json'),
         name='manifest'),
    path('sw.js',
         TemplateView.as_view(template_name='pwa/sw.js',
                              extra_context={'cache_version': CACHE_VERSION},
                              content_type='application/javascript'),
         name='sw'),
    path('cuentas/', include('accounts.urls')),
    path('comprobantes/', include('comprobantes.urls')),
    path('conciliar/', include('conciliaciones.urls')),
    path('', include('dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
