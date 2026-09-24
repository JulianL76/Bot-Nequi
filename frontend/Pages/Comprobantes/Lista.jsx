import { useMemo, useState } from 'react';
import { Link, router, useForm, usePage } from '@inertiajs/react';
import {
  Check, ChevronLeft, ChevronRight, Columns3, Copy, Download,
  Eye, Inbox, Package, Pencil, Plus, Search, Trash2, Undo2, Upload, X,
} from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';

import { Cabecera } from '../../Layout.jsx';
import { SelectorFecha } from '../../components/SelectorFecha.jsx';
import { SelectorHora } from '../../components/SelectorHora.jsx';
import { BarraAcciones } from '../../components/BarraAcciones.jsx';
import {
  Badge, Button, Card, Checkbox, EmptyState, Input, Label, Select,
} from '../../ui/index.jsx';
import { Dialog, DialogContent, ConfirmDialog } from '../../ui/Dialog.jsx';
import {
  TablaComprobantes, COLUMNAS_OCULTABLES, useColumnasVisibles,
} from '../../components/TablaComprobantes.jsx';
import { abrirImagen } from '../../components/VisorImagen.jsx';
import { useSeleccionPersistente } from '../../lib/seleccion.js';
import { fechaHora, numero, pesos, plural } from '../../lib/formato.js';
import { cn } from '../../ui/cn.js';

/* ============================================================================
   Segmentos de filtro
   ========================================================================== */
function Segmento({ activo, onClick, children, tono }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activo}
      className={cn(
        'inline-flex h-6 items-center gap-1 rounded-full px-2.5 text-xs font-medium transition-colors',
        activo
          ? tono === 'bad' ? 'bg-bad-600 text-white shadow-xs'
            : tono === 'ok' ? 'bg-ok-600 text-white shadow-xs'
            : tono === 'warn' ? 'bg-warn-500 text-ink-950 shadow-xs'
            : 'bg-surface text-content shadow-xs'
          : 'text-muted hover:text-content',
      )}
    >
      {children}
    </button>
  );
}

/** Conteo dentro de un chip: discreto, alineado y siempre del mismo ancho. */
function Cuenta({ n }) {
  return <span className="nums ml-1 opacity-60">{numero(n)}</span>;
}

function GrupoSegmentos({ children }) {
  return (
    <div className="flex items-center gap-1 rounded-[var(--radius-pill)] border border-line bg-surface-inset p-0.5">
      {children}
    </div>
  );
}

/* Tamaño de página por defecto del servidor (TAM_PAGINA en comprobantes/views.py).
   Solo viaja en la URL cuando se elige otro distinto. */
const TAM_POR_DEFECTO = 200;

/* ============================================================================
   Página
   ========================================================================== */
export default function Lista({ filas, paginacion, resumen, desglose, filtros, lote, rutas }) {
  const { urls } = usePage().props;

  const [busqueda, setBusqueda] = useState(filtros.q);
  const [columnas, setColumnas] = useColumnasVisibles();
  const [exportar, setExportar] = useState(false);
  const [aEliminar, setAEliminar] = useState(null);
  const [rutaAsignar, setRutaAsignar] = useState('');

  const ids = useMemo(() => filas.map((f) => f.id), [filas]);
  const sel = useSeleccionPersistente(ids);

  /** Navega conservando los filtros actuales y cambiando solo lo que llega. */
  const navegar = (cambios, opciones = {}) => {
    const params = { ...filtros, ...cambios };
    if (paginacion.tam !== TAM_POR_DEFECTO) params.tam = paginacion.tam;
    Object.keys(params).forEach((k) => { if (!params[k]) delete params[k]; });
    router.get(urls.comprobantes, params, { preserveScroll: true, preserveState: true, ...opciones });
  };

  const buscar = (e) => { e.preventDefault(); navegar({ q: busqueda, page: null }); };

  /** Acciones en lote: van por POST al endpoint que ya existía. */
  const accionLote = (accion, extra = {}) => {
    if (!sel.total) return;
    router.post(urls.accionesLote, { accion, seleccion: sel.ids, ...extra }, {
      preserveScroll: true,
      onSuccess: () => sel.limpiar(),
    });
  };

  const hayFiltro = filtros.q || filtros.dia || filtros.hora || filtros.dup || filtros.estado || filtros.lote;

  return (
    <>
      <Cabecera
        titulo="Comprobantes"
        subtitulo={
          resumen.n === desglose.alcance
            ? `${numero(resumen.n)} ${plural(resumen.n, 'comprobante')} · ${pesos(resumen.total)}`
            : `Viendo ${numero(resumen.n)} de ${numero(desglose.alcance)} · ${pesos(resumen.total)}`
        }
      >
        <Button variant="primary" size="sm" asChild className="hidden md:inline-flex">
          <Link href={urls.subir}><Plus />Subir</Link>
        </Button>
      </Cabecera>

      {/* ======================= Búsqueda y filtros ======================= */}
      <Card className="card-pad mb-2.5">
        <form onSubmit={buscar} className="flex flex-col gap-2 md:flex-row">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-subtle" />
            <Input
              type="search"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar remitente, referencia, monto o #id…"
              className="pl-8"
              aria-label="Buscar comprobantes"
            />
          </div>

          <div className="flex gap-2">
            <SelectorFecha
              valor={filtros.dia}
              onCambio={(v) => navegar({ dia: v, page: null })}
              className="flex-1 md:flex-none"
            />
            <SelectorHora
              valor={filtros.hora}
              onCambio={(v) => navegar({ hora: v, page: null })}
            />

            <Button type="submit" variant="primary">Buscar</Button>

            {hayFiltro && (
              <Button
                variant="ghost" icon title="Limpiar filtros" aria-label="Limpiar filtros"
                onClick={() => router.get(urls.comprobantes)}
              >
                <X />
              </Button>
            )}
          </div>
        </form>

        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-2.5">
          {/*
            Los conteos salen del ALCANCE (búsqueda, fecha, hora, subida), no de
            lo ya filtrado: al pulsar "Duplicados" el resto no se va a cero, así
            que siguen sirviendo para decidir.
          */}
          <GrupoSegmentos>
            <Segmento activo={!filtros.dup} onClick={() => navegar({ dup: '', page: null })}>
              Todos<Cuenta n={desglose.alcance} />
            </Segmento>
            <Segmento activo={filtros.dup === '0'} onClick={() => navegar({ dup: '0', page: null })}>
              Originales<Cuenta n={desglose.originales} />
            </Segmento>
            <Segmento activo={filtros.dup === '1'} tono="bad" onClick={() => navegar({ dup: '1', page: null })}>
              Duplicados<Cuenta n={desglose.duplicados} />
            </Segmento>
          </GrupoSegmentos>

          <GrupoSegmentos>
            <Segmento activo={!filtros.estado} onClick={() => navegar({ estado: '', page: null })}>
              Cualquier estado
            </Segmento>
            <Segmento activo={filtros.estado === 'confirmado'} tono="ok" onClick={() => navegar({ estado: 'confirmado', page: null })}>
              Confirmado<Cuenta n={desglose.confirmados} />
            </Segmento>
            <Segmento activo={filtros.estado === 'sin_confirmar'} tono="warn" onClick={() => navegar({ estado: 'sin_confirmar', page: null })}>
              Pendiente<Cuenta n={desglose.pendientes} />
            </Segmento>
          </GrupoSegmentos>

          <div className="ml-auto flex items-center gap-1.5">
            {/* Columnas: cada rol mira cosas distintas y la elección se guarda. */}
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <Button size="sm" className="hidden lg:inline-flex">
                  <Columns3 />Columnas
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end" sideOffset={6}
                  className="card layer-modal min-w-44 p-1 shadow-lg
                             data-[state=open]:animate-[entrar-menu_140ms_var(--ease-out-soft)]
                             data-[state=closed]:animate-[salir-menu_100ms_ease-in]"
                >
                  {COLUMNAS_OCULTABLES.map((c) => (
                    <DropdownMenu.CheckboxItem
                      key={c.id}
                      checked={columnas[c.id] !== false}
                      onCheckedChange={(v) => setColumnas({ ...columnas, [c.id]: !!v })}
                      onSelect={(e) => e.preventDefault()}
                      className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-field)] px-2 py-1.5 text-[13px] outline-none transition-colors data-[highlighted]:bg-surface-hover"
                    >
                      <span className="grid size-3.5 place-items-center">
                        {columnas[c.id] !== false && <Check className="size-3 text-brand-600 dark:text-brand-400" strokeWidth={3} />}
                      </span>
                      {c.label}
                    </DropdownMenu.CheckboxItem>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>

            <Button size="sm" onClick={() => setExportar(true)}>
              <Download className="text-ok-600" />
              <span className="hidden sm:inline">Exportar</span>
            </Button>
            <Button size="sm" asChild>
              <Link href={urls.importar}>
                <Upload className="text-brand-600 dark:text-brand-400" />
                <span className="hidden sm:inline">Importar</span>
              </Link>
            </Button>
          </div>
        </div>
      </Card>

      {/* Aviso: la lista está acotada a una subida concreta */}
      {lote && (
        <div className="mb-2.5 flex items-center gap-2 rounded-[var(--radius-field)] border border-brand-500/20 bg-brand-50 px-3 py-2 text-xs text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
          <Package className="size-3.5 shrink-0" />
          Mostrando solo la <Link href={`/comprobantes/lote/${lote.id}/`} className="font-semibold underline underline-offset-2">subida #{lote.id}</Link>
          <Link href={urls.comprobantes} className="ml-auto inline-flex items-center gap-1 font-medium hover:underline">
            Ver todos <X className="size-3" />
          </Link>
        </div>
      )}

      {/* ======================= Listado ======================= */}
      {filas.length === 0 ? (
        <Card>
          <EmptyState
            icon={hayFiltro ? Search : Inbox}
            titulo={hayFiltro ? 'Ningún comprobante coincide con el filtro.' : 'Aún no hay comprobantes.'}
            descripcion={hayFiltro ? null : 'Sube las fotos y el gestor los lee por ti.'}
          >
            {hayFiltro ? (
              <Button size="sm" onClick={() => router.get(urls.comprobantes)}>Quitar filtros</Button>
            ) : (
              <Button variant="primary" size="sm" asChild><Link href={urls.subir}>Subir comprobantes</Link></Button>
            )}
          </EmptyState>
        </Card>
      ) : (
        <>
          <Card className="hidden overflow-hidden lg:block">
            <TablaComprobantes
              filas={filas}
              seleccion={sel.seleccion}
              onSeleccion={sel.setSeleccion}
              sort={filtros.sort}
              onSort={(s) => navegar({ sort: s })}
              columnasVisibles={columnas}
              urlComprobantes={urls.comprobantes}
              onEliminar={setAEliminar}
            />
          </Card>

          {/* ---------- Tarjetas (móvil) ---------- */}
          <div className="space-y-2 lg:hidden">
            {filas.map((c) => (
              <Card key={c.id} className={cn('p-3', c.esDuplicado && 'border-bad-500/40')}>
                <div className="flex items-start gap-2.5">
                  <Checkbox
                    className="mt-0.5"
                    checked={!!sel.seleccion[c.id]}
                    onCheckedChange={(v) => sel.setSeleccion((p) => ({ ...p, [c.id]: !!v }))}
                    aria-label={`Seleccionar comprobante ${c.id}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="t-seccion truncate">{c.de}</span>
                      {c.estado === 'confirmado'
                        ? <Badge tono="ok" punto className="shrink-0">Conf.</Badge>
                        : <Badge tono="warn" punto className="shrink-0">Pend.</Badge>}
                    </div>
                    <p className="t-dato mt-0.5 text-lg">{pesos(c.valor)}</p>

                    {c.esDuplicado && <Badge tono="bad" className="mt-1"><Copy />Duplicado</Badge>}
                    {!c.esDuplicado && c.nDups > 0 && <Badge tono="ok" className="mt-1">Original · {c.nDups}</Badge>}

                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 t-meta">
                      <span className="font-mono">{c.ref || '—'}</span>
                      <span>{c.fecha || '—'}{c.hora ? ` · ${c.hora}` : ''}</span>
                      <Badge>{c.origen}</Badge>
                    </div>
                    {c.confirmadoEn && (
                      <>
                        {/* Misma información que la columna Estado en escritorio. */}
                        {c.confirmadoVia && (
                          <p className="mt-0.5 truncate t-meta text-subtle">
                            {c.confirmadoVia}{c.ruta != null ? ` · Ruta ${c.ruta}` : ''}
                          </p>
                        )}
                        <p className="nums mt-0.5 t-meta text-subtle">
                          Conf. {fechaHora(c.confirmadoEn)}{c.confirmadoPor ? ` · ${c.confirmadoPor}` : ''}
                        </p>
                      </>
                    )}
                  </div>
                </div>

                <div className="mt-2.5 flex items-center gap-1 border-t border-line pt-2.5">
                  {c.imagen && (
                    <Button variant="ghost" size="sm" onClick={() => abrirImagen(c.imagen, `${c.de} · ${pesos(c.valor)}`)}>
                      <Eye />Ver
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" asChild className="text-brand-600 dark:text-brand-400">
                    <Link href={`${urls.comprobantes}${c.id}/editar/`}><Pencil />Editar</Link>
                  </Button>
                  <Button
                    variant="ghost" size="sm" icon
                    className="ml-auto text-bad-600 dark:text-bad-400"
                    aria-label={`Eliminar comprobante ${c.id}`}
                    onClick={() => setAEliminar(c)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}

      {/* ======================= Paginación ======================= */}
      <div className="mt-4 flex flex-wrap items-center justify-center gap-4">
        {paginacion.paginas > 1 && (
          <div className="flex items-center gap-1">
            <Button
              size="sm" icon aria-label="Página anterior"
              disabled={paginacion.pagina <= 1}
              onClick={() => navegar({ page: paginacion.pagina - 1 }, { preserveState: false })}
            >
              <ChevronLeft />
            </Button>
            <span className="nums px-2 t-meta">
              <span className="font-semibold text-content">{paginacion.pagina}</span> / {paginacion.paginas}
            </span>
            <Button
              size="sm" icon aria-label="Página siguiente"
              disabled={paginacion.pagina >= paginacion.paginas}
              onClick={() => navegar({ page: paginacion.pagina + 1 }, { preserveState: false })}
            >
              <ChevronRight />
            </Button>
          </div>
        )}

        <label className="flex items-center gap-2 t-meta">
          Por página
          <Select
            value={String(paginacion.tam)}
            onChange={(e) => navegar({ tam: e.target.value, page: null })}
            className="h-[var(--h-control-sm)] w-auto text-xs"
          >
            {[200, 500, 1000].map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </label>
      </div>

      {/* ======================= Barra de acciones ======================= */}
      <BarraAcciones visible={sel.total > 0} ancho="58rem">
          <div className="flex flex-wrap items-center gap-1.5 rounded-[var(--radius-card)] border border-line bg-surface-raised p-2 shadow-lg">
            <Button variant="ghost" size="sm" icon onClick={sel.limpiar} title="Quitar selección" aria-label="Quitar selección">
              <X />
            </Button>
            <span className="whitespace-nowrap text-xs font-semibold">
              <span className="nums">{sel.total}</span> seleccionado{sel.total !== 1 ? 's' : ''}
              {sel.fuera > 0 && (
                <span className="font-normal text-muted"> (<span className="nums">{sel.fuera}</span> en otras páginas)</span>
              )}
            </span>

            <div className="ml-auto flex flex-wrap items-center gap-1.5">
              <Button variant="success" size="sm" onClick={() => accionLote('confirmar')}>
                <Check />Confirmar
              </Button>
              <Button size="sm" onClick={() => accionLote('desconfirmar')}>
                <Undo2 /><span className="hidden sm:inline">Desconfirmar</span>
              </Button>

              <span className="mx-0.5 hidden h-5 w-px bg-line sm:block" />

              <Select
                value={rutaAsignar}
                onChange={(e) => setRutaAsignar(e.target.value)}
                aria-label="Ruta a asignar"
                className="h-[var(--h-control-sm)] w-auto text-xs"
              >
                <option value="">Ruta…</option>
                {rutas.map((r) => <option key={r.id} value={r.id}>Ruta {r.numero}</option>)}
              </Select>
              <Button
                variant="primary" size="sm"
                disabled={!rutaAsignar}
                onClick={() => accionLote('asignar_ruta', { ruta: rutaAsignar })}
              >
                Asignar
              </Button>

              <Button size="sm" onClick={() => accionLote('exportar')}>
                <Download /><span className="hidden sm:inline">Excel</span>
              </Button>
              <Button variant="danger" size="sm" icon aria-label="Eliminar seleccionados" onClick={() => setAEliminar('lote')}>
                <Trash2 />
              </Button>
            </div>
          </div>
      </BarraAcciones>

      {/* ======================= Diálogos ======================= */}
      <DialogoExportar
        abierto={exportar}
        onOpenChange={setExportar}
        rutas={rutas}
        filtros={filtros}
        url={urls.exportarComprobantes}
      />

      <ConfirmDialog
        abierto={!!aEliminar}
        onOpenChange={(v) => !v && setAEliminar(null)}
        titulo={aEliminar === 'lote' ? '¿Eliminar los seleccionados?' : '¿Eliminar este comprobante?'}
        mensaje={
          aEliminar === 'lote'
            ? `Se eliminarán ${sel.total} ${plural(sel.total, 'comprobante')}. No se puede deshacer.`
            : aEliminar
              ? `${aEliminar.de} · ${pesos(aEliminar.valor)}. No se puede deshacer.`
              : ''
        }
        onConfirm={() => {
          if (aEliminar === 'lote') accionLote('eliminar');
          else router.post(`${urls.comprobantes}${aEliminar.id}/eliminar/`, {}, { preserveScroll: true });
          setAEliminar(null);
        }}
      />
    </>
  );
}

/* ============================================================================
   Diálogo de exportación
   ========================================================================== */
function DialogoExportar({ abierto, onOpenChange, rutas, filtros, url }) {
  const { data, setData } = useForm({ desde: filtros.dia || '', hasta: filtros.dia || '', ruta: [] });
  const todas = rutas.length > 0 && data.ruta.length === rutas.length + 1;

  const alternarRuta = (valor) => {
    setData('ruta', data.ruta.includes(valor)
      ? data.ruta.filter((r) => r !== valor)
      : [...data.ruta, valor]);
  };

  return (
    <Dialog open={abierto} onOpenChange={onOpenChange}>
      <DialogContent titulo="Exportar a Excel" icon={Download} descripcion="Elige rango de fechas y rutas">
        {/* Descarga de archivo: GET normal, no una visita de Inertia. */}
        <form method="get" action={url} className="card-pad space-y-3">
          {filtros.q && <input type="hidden" name="q" value={filtros.q} />}
          {filtros.dup && <input type="hidden" name="dup" value={filtros.dup} />}
          {filtros.estado && <input type="hidden" name="estado" value={filtros.estado} />}
          {filtros.lote && <input type="hidden" name="lote" value={filtros.lote} />}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="exp-desde">Desde</Label>
              <Input id="exp-desde" type="date" name="desde"
                     value={data.desde} onChange={(e) => setData('desde', e.target.value)} />
            </div>
            <div>
              <Label htmlFor="exp-hasta">Hasta</Label>
              <Input id="exp-hasta" type="date" name="hasta"
                     value={data.hasta} onChange={(e) => setData('hasta', e.target.value)} />
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="label mb-0">Rutas</span>
              <label className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-brand-600 dark:text-brand-400">
                <Checkbox
                  checked={todas}
                  onCheckedChange={(v) => setData('ruta', v ? [...rutas.map((r) => String(r.id)), 'sin'] : [])}
                />
                Todas
              </label>
            </div>

            <div className="max-h-44 space-y-0.5 overflow-y-auto rounded-[var(--radius-field)] border border-line bg-surface-inset p-1.5">
              {rutas.map((r) => (
                <label key={r.id} className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] hover:bg-surface-hover">
                  <Checkbox
                    checked={data.ruta.includes(String(r.id))}
                    onCheckedChange={() => alternarRuta(String(r.id))}
                  />
                  <input type="checkbox" name="ruta" value={r.id} checked={data.ruta.includes(String(r.id))} readOnly hidden />
                  Ruta {r.numero}{r.nombre && <span className="text-muted">— {r.nombre}</span>}
                </label>
              ))}
              <label className="mt-1 flex cursor-pointer items-center gap-2.5 rounded-md border-t border-line px-2 py-1.5 pt-2 text-[13px] hover:bg-surface-hover">
                <Checkbox checked={data.ruta.includes('sin')} onCheckedChange={() => alternarRuta('sin')} />
                <input type="checkbox" name="ruta" value="sin" checked={data.ruta.includes('sin')} readOnly hidden />
                Sin ruta asignada
              </label>
            </div>
            <p className="hint">Sin marcar ninguna se exportan todas las rutas.</p>
          </div>

          <p className="t-meta text-subtle">
            Deja las fechas vacías para exportar todo. También se respetan la búsqueda y los filtros actuales.
          </p>

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" variant="success"><Download />Descargar</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
