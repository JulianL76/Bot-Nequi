import { useState } from 'react';
import { Link, useForm, usePage } from '@inertiajs/react';
import { ChevronLeft, Copy, Eye, Image, Save } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Badge, Button, Card, Campo, EmptyState, Input, Select, Switch } from '../../ui/index.jsx';
import { ConfirmDialog } from '../../ui/Dialog.jsx';
import { abrirImagen } from '../../components/VisorImagen.jsx';
import { fechaHora, pesos } from '../../lib/formato.js';

export default function Editar({ comprobante: c, rutas }) {
  const { urls } = usePage().props;
  const [confirmarQuitar, setConfirmarQuitar] = useState(false);

  const { data, setData, post, processing, errors } = useForm({
    de: c.de || '',
    valor: String(c.valor ?? ''),
    ref: c.ref || '',
    fecha: c.fecha || '',
    hora: c.hora || '',
    ruta: c.rutaId ? String(c.rutaId) : '',
    confirmado: c.estado === 'confirmado' ? '1' : '',
  });

  const estabaConfirmado = c.estado === 'confirmado';

  const guardar = (e) => {
    e?.preventDefault();
    // Quitar la confirmación borra su trazabilidad: se avisa antes.
    if (estabaConfirmado && data.confirmado !== '1' && !confirmarQuitar) {
      setConfirmarQuitar(true);
      return;
    }
    post(`${urls.comprobantes}${c.id}/editar/`);
  };

  return (
    <div className="max-w-6xl">
      <Cabecera titulo={`Comprobante #${c.id}`}>
        <Button size="sm" asChild>
          <Link href={urls.comprobantes}>
            <ChevronLeft /><span className="hidden sm:inline">Volver</span>
          </Link>
        </Button>
      </Cabecera>

      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {c.estado === 'confirmado'
          ? <Badge tono="ok" punto>Confirmado</Badge>
          : <Badge tono="warn" punto>Pendiente</Badge>}
        {c.esDuplicado && <Badge tono="bad"><Copy />Duplicado</Badge>}
      </div>

      <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        {/* ============ Imagen e información de origen ============ */}
        <div className="space-y-3 lg:sticky lg:top-14">
          <Card className="overflow-hidden">
            {c.imagen ? (
              <button
                type="button"
                className="group relative block w-full"
                onClick={() => abrirImagen(c.imagen, `#${c.id} · ${c.de} · ${pesos(c.valor)}`)}
              >
                <img src={c.imagen} alt={`Comprobante #${c.id}`} className="max-h-[22rem] w-full bg-surface-inset object-contain" />
                <span className="absolute inset-0 grid place-items-center bg-ink-950/0 transition-colors group-hover:bg-ink-950/35">
                  <span className="flex items-center gap-2 rounded-[var(--radius-field)] bg-surface-raised px-2.5 py-1.5 t-seccion opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
                    <Eye className="size-3.5" />Ampliar
                  </span>
                </span>
              </button>
            ) : (
              <EmptyState icon={Image} titulo="Sin imagen" descripcion="Este comprobante no tiene foto asociada." />
            )}
          </Card>

          <Card className="card-pad">
            <h2 className="mb-2.5 t-micro">Información</h2>
            <dl className="t-cuerpo grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2">
              <dt className="text-muted">Origen</dt>
              <dd>{c.origen}</dd>

              <dt className="text-muted">Subida</dt>
              <dd>
                {c.loteId
                  ? <Link href={`/comprobantes/lote/${c.loteId}/`} className="font-medium text-brand-600 hover:underline dark:text-brand-400">Lote #{c.loteId}</Link>
                  : '—'}
              </dd>

              <dt className="text-muted">Creado por</dt>
              <dd>{c.creadoPor || '—'}</dd>

              <dt className="text-muted">Creado el</dt>
              <dd className="nums">{fechaHora(c.creadoEn)}</dd>

              {c.fuenteIa && (<><dt className="text-muted">Leído con</dt><dd>{c.fuenteIa}</dd></>)}

              {c.valorRaw && c.valorRaw !== String(c.valor) && (
                <><dt className="text-muted">Valor leído</dt>
                  <dd className="t-meta break-all font-mono">{c.valorRaw}</dd></>
              )}

              <dt className="text-muted">Duplicado</dt>
              <dd>
                {c.esDuplicado ? (
                  <>
                    <span className="font-semibold text-bad-600 dark:text-bad-400">Sí</span>
                    {c.duplicadoDeId && (
                      <> · de <Link href={`${urls.comprobantes}${c.duplicadoDeId}/editar/`} className="font-medium text-brand-600 hover:underline dark:text-brand-400">#{c.duplicadoDeId}</Link></>
                    )}
                  </>
                ) : 'No'}
              </dd>
            </dl>
          </Card>
        </div>

        {/* ============ Formulario ============ */}
        <Card>
          <form onSubmit={guardar}>
            <div className="card-pad space-y-3">
              <h2 className="t-micro">Datos del comprobante</h2>

              <Campo label="Remitente" id="f-de" error={errors.de}>
                <Input id="f-de" value={data.de} onChange={(e) => setData('de', e.target.value)} />
              </Campo>

              <div className="grid gap-3 sm:grid-cols-2">
                <Campo label="Valor" id="f-valor" error={errors.valor}>
                  <Input id="f-valor" inputMode="decimal" className="font-semibold"
                         value={data.valor} onChange={(e) => setData('valor', e.target.value)} />
                </Campo>
                <Campo label="Referencia" id="f-ref" error={errors.ref}>
                  <Input id="f-ref" className="font-mono" value={data.ref} onChange={(e) => setData('ref', e.target.value)} />
                </Campo>
                <Campo label="Fecha" id="f-fecha" error={errors.fecha}>
                  <Input id="f-fecha" value={data.fecha} onChange={(e) => setData('fecha', e.target.value)} />
                </Campo>
                <Campo label="Hora" id="f-hora" error={errors.hora}>
                  <Input id="f-hora" value={data.hora} onChange={(e) => setData('hora', e.target.value)} />
                </Campo>
              </div>
            </div>

            <div className="card-pad space-y-3 border-t border-line">
              <h2 className="t-micro">Ruta y estado</h2>

              <Campo label="Ruta" id="f-ruta" error={errors.ruta}>
                <Select id="f-ruta" value={data.ruta} onChange={(e) => setData('ruta', e.target.value)}>
                  <option value="">Sin ruta</option>
                  {rutas.map((r) => (
                    <option key={r.id} value={r.id}>
                      Ruta {r.numero}{!r.activa ? ' (inactiva)' : ''}
                    </option>
                  ))}
                </Select>
              </Campo>

              <label className="flex cursor-pointer items-center justify-between gap-3 rounded-[var(--radius-field)] border border-line p-3 transition-colors hover:bg-surface-inset">
                <span className="min-w-0">
                  <span className="block t-seccion">Confirmado</span>
                  <span className="block t-meta">Revisado y validado por una persona.</span>
                </span>
                <Switch
                  tono="ok"
                  checked={data.confirmado === '1'}
                  onCheckedChange={(v) => setData('confirmado', v ? '1' : '')}
                  aria-label="Marcar como confirmado"
                />
              </label>

              {estabaConfirmado && (
                <div className="t-meta space-y-0.5 rounded-[var(--radius-field)] border border-ok-500/25 bg-ok-100 p-3 text-ok-600 dark:bg-ok-500/10 dark:text-ok-400">
                  <p className="font-semibold">Registro de confirmación</p>
                  <p>Vía: {c.confirmadoVia || 'Sin registro (confirmado antes del historial)'}</p>
                  {c.confirmadoEn && <p className="nums">Fecha: {fechaHora(c.confirmadoEn)}</p>}
                  {c.confirmadoPor && <p>Por: {c.confirmadoPor}</p>}
                  {c.conciliacion && (
                    <p>
                      <a
                        href={`/conciliar/lote/${c.conciliacion.loteId}/#conc-item-${c.conciliacion.itemId}`}
                        className="font-medium underline underline-offset-2"
                      >
                        Conciliación #{c.conciliacion.loteId}
                        {c.conciliacion.ruta ? ` · Ruta ${c.conciliacion.ruta}` : ''} (ítem #{c.conciliacion.itemId})
                      </a>
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-2 rounded-b-[var(--radius-card)] border-t border-line bg-surface-inset/60 px-3 py-3 md:px-4">
              <Button type="submit" variant="primary" cargando={processing}>
                <Save />Guardar cambios
              </Button>
              <Button type="button" variant="ghost" asChild>
                <Link href={urls.comprobantes}>Cancelar</Link>
              </Button>
            </div>
          </form>
        </Card>
      </div>

      <ConfirmDialog
        abierto={confirmarQuitar}
        onOpenChange={setConfirmarQuitar}
        titulo="¿Quitar la confirmación?"
        mensaje="Se borra el registro de quién, cuándo y por qué vía se confirmó este comprobante."
        confirmar="Quitar confirmación"
        onConfirm={() => post(`${urls.comprobantes}${c.id}/editar/`)}
      />
    </div>
  );
}
