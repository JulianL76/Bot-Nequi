import { useState } from 'react';
import { Link, router, usePage } from '@inertiajs/react';
import { ChevronLeft, ChevronRight, Download, ListChecks, Search, Trash2, X } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { BarraAcciones } from '../../components/BarraAcciones.jsx';
import { Button, Card, Checkbox, EmptyState, Input, Label, Select } from '../../ui/index.jsx';
import { Dialog, DialogContent, ConfirmDialog } from '../../ui/Dialog.jsx';
import { ItemConciliacion } from '../../components/ItemConciliacion.jsx';
import { FichaFiltro } from '../../components/FichaFiltro.jsx';
import { numero, plural } from '../../lib/formato.js';

/** Cada ficha es un filtro. `clave` apunta al conteo dentro del alcance. */
const FILTROS = [
  { valor: '',          etiqueta: 'Total',          clave: 'total',     tono: 'neutro' },
  { valor: 'ok',        etiqueta: 'OK',             clave: 'ok',        tono: 'ok' },
  { valor: 'pendiente', etiqueta: 'Pendientes',     clave: 'pendiente', tono: 'aviso' },
  { valor: 'no_esta',   etiqueta: 'No está',        clave: 'noEsta',    tono: 'grave' },
  { valor: 'revision',  etiqueta: 'Revisión',       clave: 'revision',  tono: 'aviso' },
  { valor: 'duplicado', etiqueta: 'Duplicados',     clave: 'duplicado', tono: 'marca' },
  { valor: 'obs',       etiqueta: 'Con observación', clave: 'obs',      tono: 'marca' },
];

export default function Panel({ items, paginacion, stats, filtros, rutas }) {
  const { urls } = usePage().props;
  const [seleccion, setSeleccion] = useState({});
  const [exportar, setExportar] = useState(false);
  const [confirmarBorrado, setConfirmarBorrado] = useState(false);

  const seleccionados = Object.keys(seleccion).filter((k) => seleccion[k]);

  const navegar = (cambios) => {
    const params = { ...filtros, ...cambios };
    Object.keys(params).forEach((k) => {
      if (!params[k] || (Array.isArray(params[k]) && !params[k].length)) delete params[k];
    });
    router.get(urls.panel, params, { preserveScroll: true, preserveState: true });
  };

  const todosVisibles = items.length > 0 && items.every((i) => seleccion[i.id]);
  const filtroActivo = FILTROS.find((f) => f.valor && f.valor === filtros.r);

  return (
    <>
      <Cabecera
        titulo="Panel de conciliaciones"
        subtitulo="Todos los ítems del negocio, de cualquier lote o ruta."
      >
        <Button size="sm" asChild>
          <Link href={urls.conciliaciones}><ListChecks />Historial</Link>
        </Button>
      </Cabecera>

      {/*
        Las fichas SON el filtro: antes había dos filas diciendo lo mismo.
        Sus cifras se calculan sobre el alcance (fechas y rutas), nunca sobre
        el resultado elegido — si no, al filtrar el resto quedaría en cero.
      */}
      <div className="mb-2.5 grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-7">
        {FILTROS.map((f) => (
          <FichaFiltro
            key={f.valor || 'todos'}
            etiqueta={f.etiqueta}
            valor={numero(stats[f.clave] ?? 0)}
            tono={f.tono}
            total={stats.total}
            activo={filtros.r === f.valor}
            onClick={() => navegar({ r: filtros.r === f.valor ? '' : f.valor, page: null })}
          />
        ))}
      </div>

      <Card className="card-pad mb-2.5">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="p-desde">Desde</Label>
            <Input id="p-desde" type="date" value={filtros.desde}
                   onChange={(e) => navegar({ desde: e.target.value, page: null })} className="w-auto" />
          </div>
          <div>
            <Label htmlFor="p-hasta">Hasta</Label>
            <Input id="p-hasta" type="date" value={filtros.hasta}
                   onChange={(e) => navegar({ hasta: e.target.value, page: null })} className="w-auto" />
          </div>

          <div>
            <Label htmlFor="p-orden">Orden</Label>
            <Select id="p-orden" value={filtros.sort} onChange={(e) => navegar({ sort: e.target.value })} className="w-auto">
              <option value="">Más reciente</option>
              <option value="valor">Valor ↑</option>
              <option value="-valor">Valor ↓</option>
              <option value="ref">Referencia</option>
              <option value="resultado">Resultado</option>
              <option value="para">Destinatario</option>
            </Select>
          </div>

          <div>
            <Label htmlFor="p-tam">Por página</Label>
            <Select id="p-tam" value={String(paginacion.tam)}
                    onChange={(e) => navegar({ tam: e.target.value, page: null })} className="w-auto">
              {[25, 50, 100, 200].map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </div>

          <div className="ml-auto flex items-center gap-1.5">
            {(filtros.desde || filtros.hasta || filtros.r) && (
              <Button size="sm" variant="ghost" onClick={() => router.get(urls.panel)}>
                <X />Limpiar
              </Button>
            )}
            <Button size="sm" onClick={() => setExportar(true)}>
              <Download className="text-ok-600" />Exportar
            </Button>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        {items.length === 0 ? (
          <EmptyState
            icon={Search}
            titulo="Ningún ítem coincide con el filtro."
            descripcion="Prueba ampliando el rango de fechas o quitando el filtro de resultado."
          >
            <Button size="sm" onClick={() => router.get(urls.panel)}>Quitar filtros</Button>
          </EmptyState>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-3 py-2">
              <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted">
                <Checkbox
                  checked={todosVisibles}
                  indeterminate={seleccionados.length > 0 && !todosVisibles}
                  onCheckedChange={(v) => {
                    const nuevo = { ...seleccion };
                    items.forEach((i) => { nuevo[i.id] = !!v; });
                    setSeleccion(nuevo);
                  }}
                />
                Seleccionar todos los de esta página
              </label>

              {/* Relación explícita entre lo que se ve y el universo: sin esto
                  hay que deducirla comparando la ficha activa con la lista. */}
              <p className="ml-auto t-meta">
                Viendo <span className="nums font-semibold text-content">{numero(paginacion.total)}</span>
                {paginacion.total !== stats.total && (
                  <> de <span className="nums">{numero(stats.total)}</span></>
                )}
                {' '}{plural(paginacion.total, 'ítem', 'ítems')}
                {filtroActivo && <> · {filtroActivo.etiqueta}</>}
              </p>
            </div>

            <div className="divide-y divide-line">
              {items.map((it) => (
                <ItemConciliacion
                  key={it.id}
                  item={it}
                  seleccionado={seleccion[it.id]}
                  onSeleccionar={(id, v) => setSeleccion((p) => ({ ...p, [id]: v }))}
                  urlAjustar={`/conciliar/item/${it.id}/ajustar/`}
                />
              ))}
            </div>
          </>
        )}
      </Card>

      {paginacion.paginas > 1 && (
        <div className="mt-4 flex items-center justify-center gap-1">
          <Button size="sm" icon aria-label="Página anterior"
                  disabled={paginacion.pagina <= 1}
                  onClick={() => navegar({ page: paginacion.pagina - 1 })}>
            <ChevronLeft />
          </Button>
          <span className="nums px-2 t-meta">
            <span className="font-semibold text-content">{paginacion.pagina}</span> / {paginacion.paginas}
          </span>
          <Button size="sm" icon aria-label="Página siguiente"
                  disabled={paginacion.pagina >= paginacion.paginas}
                  onClick={() => navegar({ page: paginacion.pagina + 1 })}>
            <ChevronRight />
          </Button>
        </div>
      )}

      {/* Barra de acciones sobre lo seleccionado */}
      <BarraAcciones visible={seleccionados.length > 0} ancho="40rem">
          <div className="flex items-center gap-1.5 rounded-[var(--radius-card)] border border-line bg-surface-raised p-2 shadow-lg">
            <Button variant="ghost" size="sm" icon onClick={() => setSeleccion({})} aria-label="Quitar selección">
              <X />
            </Button>
            <span className="text-xs font-semibold">
              <span className="nums">{seleccionados.length}</span> {plural(seleccionados.length, 'ítem', 'ítems')}
            </span>
            <Button variant="danger" size="sm" className="ml-auto" onClick={() => setConfirmarBorrado(true)}>
              <Trash2 />Eliminar
            </Button>
          </div>
      </BarraAcciones>

      <ConfirmDialog
        abierto={confirmarBorrado}
        onOpenChange={setConfirmarBorrado}
        titulo={`¿Eliminar ${seleccionados.length} ${plural(seleccionados.length, 'ítem', 'ítems')}?`}
        mensaje="Se borran los ítems de conciliación seleccionados y sus imágenes. No se puede deshacer."
        onConfirm={() => router.post('/conciliar/items/eliminar-masivo/', { seleccion: seleccionados },
          { onSuccess: () => setSeleccion({}) })}
      />

      <Dialog open={exportar} onOpenChange={setExportar}>
        <DialogContent titulo="Exportar el panel" icon={Download} descripcion="Se exporta lo que hay filtrado">
          <form method="get" action={urls.exportarPanel} className="card-pad space-y-3">
            {filtros.r && <input type="hidden" name="r" value={filtros.r} />}
            {filtros.desde && <input type="hidden" name="desde" value={filtros.desde} />}
            {filtros.hasta && <input type="hidden" name="hasta" value={filtros.hasta} />}
            {(filtros.ruta || []).map((id) => <input key={id} type="hidden" name="ruta" value={id} />)}

            <p className="t-cuerpo text-muted">
              Se exportan los <span className="nums font-semibold text-content">{numero(paginacion.total)}</span>{' '}
              {plural(paginacion.total, 'ítem', 'ítems')} que coinciden con los filtros actuales.
            </p>

            <div>
              <Label>Acotar a rutas (opcional)</Label>
              <div className="max-h-40 space-y-0.5 overflow-y-auto rounded-[var(--radius-field)] border border-line bg-surface-inset p-1.5">
                {rutas.map((r) => (
                  <label key={r.id} className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] hover:bg-surface-hover">
                    <input type="checkbox" name="ruta" value={r.id} className="size-3.5" />
                    Ruta {r.numero}{r.nombre && <span className="text-muted">— {r.nombre}</span>}
                  </label>
                ))}
                <label className="mt-1 flex cursor-pointer items-center gap-2.5 rounded-md border-t border-line px-2 py-1.5 pt-2 text-[13px] hover:bg-surface-hover">
                  <input type="checkbox" name="ruta" value="sin" className="size-3.5" />
                  Sin ruta asignada
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => setExportar(false)}>Cancelar</Button>
              <Button type="submit" variant="success"><Download />Descargar</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
