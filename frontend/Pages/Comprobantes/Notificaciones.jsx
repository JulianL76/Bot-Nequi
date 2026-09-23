import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Bell, Inbox, Send } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Badge, Button, Card, EmptyState } from '../../ui/index.jsx';
import { csrfToken } from '../../lib/csrf.js';
import { fechaHora, hace } from '../../lib/formato.js';
import { cn } from '../../ui/cn.js';

/* ============================================================================
   Activación de avisos push
   ========================================================================== */
const TEXTOS = {
  comprobando: 'Comprobando…',
  no_soportado: 'Este navegador no admite notificaciones. En iPhone hay que agregar la app a la pantalla de inicio primero.',
  bloqueado: 'Bloqueadas en la configuración del navegador. Hay que permitirlas desde el candado de la barra de direcciones.',
  apagado: 'Recibe un aviso en este dispositivo cuando termine un lote, aunque la app esté cerrada.',
  activo: 'Activadas en este dispositivo.',
};

/** La clave pública viaja en base64url; el navegador la pide como bytes. */
function aBytes(b64) {
  const s = (b64 + '='.repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(s);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

function CajaPush({ clave, urls }) {
  const [estado, setEstado] = useState('comprobando');
  const [ocupado, setOcupado] = useState(false);

  const post = (url, cuerpo) => fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json' },
    body: cuerpo ? JSON.stringify(cuerpo) : null,
  });

  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) { setEstado('no_soportado'); return; }
    if (Notification.permission === 'denied') { setEstado('bloqueado'); return; }

    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => setEstado(sub ? 'activo' : 'apagado'))
      .catch(() => setEstado('apagado'));
  }, []);

  const activar = async () => {
    setOcupado(true);
    try {
      const permiso = await Notification.requestPermission();
      if (permiso !== 'granted') { setEstado(permiso === 'denied' ? 'bloqueado' : 'apagado'); return; }

      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: aBytes(clave),
      });
      const r = await post(urls.suscribir, sub.toJSON());
      if (!r.ok) throw new Error(`http ${r.status}`);
      setEstado('activo');
      toast.success('Notificaciones activadas');
    } catch (e) {
      toast.error(`No se pudieron activar: ${e.message}`);
    } finally {
      setOcupado(false);
    }
  };

  const desactivar = async () => {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) { setEstado('apagado'); return; }
    const { endpoint } = sub;
    await sub.unsubscribe();
    await post(urls.desuscribir, { endpoint });
    setEstado('apagado');
    toast('Notificaciones desactivadas');
  };

  const probar = async () => {
    const r = await post(urls.probar);
    const d = await r.json();
    if (d.enviadas) toast.success(`Prueba enviada a ${d.enviadas} dispositivo(s)`);
    else toast.warning('No hay dispositivos suscritos');
  };

  if (estado === 'comprobando') return null;

  return (
    <Card className="card-pad mb-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-[var(--radius-field)] bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
          <Bell className="size-4" />
        </span>

        <div className="min-w-56 flex-1">
          <p className="font-semibold">Avisos en este dispositivo</p>
          <p className="t-meta">{TEXTOS[estado]}</p>
        </div>

        <div className="flex items-center gap-1.5">
          {estado === 'apagado' && (
            <Button variant="primary" size="sm" onClick={activar} cargando={ocupado}><Bell />Activar</Button>
          )}
          {estado === 'activo' && (
            <>
              <Button size="sm" onClick={probar}><Send />Probar</Button>
              <Button variant="ghost" size="sm" onClick={desactivar}>Desactivar</Button>
            </>
          )}
        </div>
      </div>
    </Card>
  );
}

/* ============================================================================
   Página
   ========================================================================== */
export default function Notificaciones({ notificaciones, vapidPublicKey, urlsPagina }) {
  return (
    <div className="max-w-3xl">
      <Cabecera titulo="Notificaciones" subtitulo="Avisos de los lotes procesados y de la actividad del gestor." />

      {vapidPublicKey && <CajaPush clave={vapidPublicKey} urls={urlsPagina} />}

      <Card className="overflow-hidden">
        {notificaciones.length === 0 ? (
          <EmptyState
            icon={Inbox}
            titulo="No tienes notificaciones."
            descripcion="Aquí llegarán los avisos cuando termine de procesarse una subida."
          />
        ) : (
          <ul className="divide-y divide-line">
            {notificaciones.map((n) => (
              <li
                key={n.id}
                className={cn('relative flex gap-2.5 p-3', !n.leida && 'bg-brand-50/60 dark:bg-brand-500/5')}
              >
                {/* Sin leer: barra de acento; se distingue sin teñir toda la fila. */}
                {!n.leida && <span className="absolute inset-y-2.5 left-0 w-0.5 rounded-full bg-brand-600" />}

                <span className={cn(
                  'grid size-7 shrink-0 place-items-center rounded-full',
                  n.leida ? 'bg-surface-inset text-subtle' : 'bg-brand-600 text-white',
                )}>
                  <Bell className="size-3.5" />
                </span>

                <div className="min-w-0 flex-1">
                  <p className="t-seccion">{n.titulo}</p>
                  <p className="mt-0.5 t-meta">{n.mensaje}</p>
                  <p className="nums mt-1 t-meta text-subtle" title={fechaHora(n.creadoEn)}>
                    {hace(n.creadoEn)}
                  </p>
                </div>

                {!n.leida && <Badge tono="brand" className="shrink-0 self-start">Nueva</Badge>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
