import { useState } from 'react';
import { Link, router, useForm, usePage } from '@inertiajs/react';
import {
  Check, ChevronLeft, ListChecks, MessageSquareText, Pause, Play,
  Plus, RefreshCw, Trash2, X,
} from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Badge, Button, Card, EmptyState, Progress, Select } from '../../ui/index.jsx';
import { Dialog, DialogContent, ConfirmDialog } from '../../ui/Dialog.jsx';
import { ItemConciliacion, RESULTADOS } from '../../components/ItemConciliacion.jsx';
import { Estadistica, FilaEstadisticas } from '../../components/Estadistica.jsx';
import { useProgreso } from '../../lib/useProgreso.js';
import { fechaHora, numero, plural } from '../../lib/formato.js';
import { cn } from '../../ui/cn.js';

const FILTROS = [
  { valor: '', etiqueta: 'Todos' },
  { valor: 'ok', etiqueta: 'OK' },
  { valor: 'pendiente', etiqueta: 'Pendientes' },
  { valor: 'no_esta', etiqueta: 'No está' },
  { valor: 'revision', etiqueta: 'Revisión' },
  { valor: 'duplicado', etiqueta: 'Duplicados' },
  { valor: 'obs', etiqueta: 'Con observación' },
];

export default function LoteDetalle({ lote, items, filtros, nObs, urlsPagina }) {
  const { urls } = usePage().props;
  const [observando, setObservando] = useState(null);
  const [aBorrar, setABorrar] = useState(null);

  const activo = ['procesando', 'en_cola'].includes(lote.estado);
  const { datos } = useProgreso(urlsPagina.progreso, lote, { activo, alTerminar: () => router.reload() });
  const d = datos || lote;

  const navegar = (cambios) => {
    const params = { ...filtros, ...cambios };
    Object.keys(params).forEach((k) => { if (!params[k]) delete params[k]; });
    router.get(`/conciliar/lote/${lote.id}/`, params, { preserveScroll: true, preserveState: true });
  };

  /** Acción sobre un ítem; conserva filtro y orden al volver. */
  const accionItem = (id, accion, extra = {}) =>
    router.post(`/conciliar/item/${id}/${accion}/`, { r: filtros.r, sort: filtros.sort, ...extra },
      { preserveScroll: true });

  return (
    <>
      <Cabecera
        titulo={`Conciliación #${lote.id}`}
        subtitulo={`${fechaHora(lote.creadoEn)}${lote.ruta != null ? ` · Ruta ${lote.ruta}` : ''} · ${numero(lote.total)} ${plural(lote.total, 'imagen', 'imágenes')}`}
      >
        <Button size="sm" asChild>
          <Link href={urls.conciliaciones}>
            <ChevronLeft /><span className="hidden sm:inline">Historial</span>
          </Link>
        </Button>
      </Cabecera>

      <Card className="card-pad mb-2.5">
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <Badge tono={activo ? 'brand' : 'ok'} punto className={activo ? '[&_.dot]:animate-pulse' : undefined}>
            {d.estadoTexto || lote.estadoTexto}
          </Badge>
          <span className="nums text-[13px] font-bold">{d.progreso ?? 0}%</span>
        </div>
        <Progress valor={d.progreso ?? 0} />

        <FilaEstadisticas className="mt-3 md:grid-cols-5">
          <Estadistica etiqueta="OK" valor={numero(d.ok)} tono="ok" />
          <Estadistica etiqueta="Pendientes" valor={numero(d.pendientes)} tono={d.pendientes ? 'aviso' : 'neutro'} />
          <Estadistica etiqueta="No está" valor={numero(d.noEsta)} tono={d.noEsta ? 'grave' : 'neutro'} />
          <Estadistica etiqueta="Revisión" valor={numero(d.revision)} tono={d.revision ? 'aviso' : 'neutro'} />
          <Estadistica etiqueta="Duplicados" valor={numero(d.duplicados)} tono={d.duplicados ? 'marca' : 'neutro'} />
        </FilaEstadisticas>

        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3">
          {activo && (
            <Button size="sm" onClick={() => router.post(`/conciliar/lote/${lote.id}/pausar/`)}>
              <Pause />Pausar
            </Button>
          )}
          {lote.estado === 'pausado' && (
            <Button variant="success" size="sm" onClick={() => router.post(`/conciliar/lote/${lote.id}/reanudar/`)}>
              <Play />Reanudar
            </Button>
          )}
          {!activo && (
            <Button size="sm" onClick={() => router.post(`/conciliar/lote/${lote.id}/reprocesar/`, { r: filtros.r, sort: filtros.sort })}>
              <RefreshCw />Reprocesar todo
            </Button>
          )}
          <Button variant="ghost" size="sm" className="ml-auto text-bad-600 dark:text-bad-400"
                  onClick={() => setABorrar('lote')}>
            <Trash2 />Borrar conciliación
          </Button>
        </div>
      </Card>

      {/* ---------- Filtros ---------- */}
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap items-center gap-1 rounded-[var(--radius-pill)] border border-line bg-surface-inset p-0.5">
          {FILTROS.map((f) => {
            const activoF = filtros.r === f.valor;
            const tono = RESULTADOS[f.valor]?.tono;
            return (
              <button
                key={f.valor || 'todos'}
                type="button"
                aria-pressed={activoF}
                onClick={() => navegar({ r: f.valor })}
                className={cn(
                  'inline-flex h-6 items-center gap-1 rounded-full px-2.5 text-xs font-medium transition-colors',
                  activoF
                    ? tono === 'ok' ? 'bg-ok-600 text-white shadow-xs'
                      : tono === 'bad' ? 'bg-bad-600 text-white shadow-xs'
                      : tono === 'warn' ? 'bg-warn-500 text-ink-950 shadow-xs'
                      : tono === 'brand' ? 'bg-brand-600 text-white shadow-xs'
                      : 'bg-surface text-content shadow-xs'
                    : 'text-muted hover:text-content',
                )}
              >
                {f.etiqueta}
                {f.valor === 'obs' && nObs > 0 && <span className="nums opacity-70">{nObs}</span>}
              </button>
            );
          })}
        </div>

        <Select value={filtros.sort} onChange={(e) => navegar({ sort: e.target.value })}
                aria-label="Ordenar" className="ml-auto h-[var(--h-control-sm)] w-auto text-xs">
          <option value="">Orden original</option>
          <option value="valor">Valor ↑</option>
          <option value="-valor">Valor ↓</option>
          <option value="ref">Referencia</option>
          <option value="resultado">Resultado</option>
          <option value="para">Destinatario</option>
        </Select>
      </div>

      {/* ---------- Ítems ---------- */}
      <Card className="overflow-hidden">
        {items.length === 0 ? (
          <EmptyState
            icon={ListChecks}
            titulo="No hay ítems con este filtro."
            descripcion="Prueba con «Todos» para ver la conciliación completa."
          >
            <Button size="sm" onClick={() => navegar({ r: '' })}>Ver todos</Button>
          </EmptyState>
        ) : (
          <div className="divide-y divide-line">
            {items.map((it) => (
              <ItemConciliacion
                key={it.id}
                item={it}
                urlAjustar={`/conciliar/item/${it.id}/ajustar/?r=${filtros.r}&sort=${filtros.sort}`}
                acciones={
                  <>
                    {it.resultado === 'pendiente' && it.comprobante && (
                      <Button
                        variant="success" size="sm"
                        onClick={() => accionItem(it.id, 'confirmar')}
                      >
                        <Check />Confirmar
                      </Button>
                    )}
                    {it.resultado === 'no_esta' && (
                      <Button
                        variant="primary" size="sm"
                        title="Crear el comprobante y confirmarlo"
                        onClick={() => accionItem(it.id, 'agregar-confirmar', {
                          de: it.de, para: it.para, num: it.num, tipo: it.tipo,
                          ref: it.ref, valor: String(it.valor), fecha: it.fecha, hora: it.hora,
                          observaciones: it.observaciones,
                        })}
                      >
                        <Plus />Añadir
                      </Button>
                    )}
                    <Button
                      variant="ghost" size="sm" icon
                      aria-label={`Observación del ítem ${it.id}`}
                      title="Observación"
                      className={it.observaciones ? 'text-brand-600 dark:text-brand-400' : undefined}
                      onClick={() => setObservando(it)}
                    >
                      <MessageSquareText />
                    </Button>
                    <Button
                      variant="ghost" size="sm" icon
                      aria-label={`Reprocesar ítem ${it.id}`} title="Reprocesar"
                      onClick={() => accionItem(it.id, 'reprocesar')}
                    >
                      <RefreshCw />
                    </Button>
                    <Button
                      variant="ghost" size="sm" icon
                      className="text-bad-600 dark:text-bad-400"
                      aria-label={`Eliminar ítem ${it.id}`} title="Eliminar"
                      onClick={() => setABorrar(it)}
                    >
                      <Trash2 />
                    </Button>
                  </>
                }
              />
            ))}
          </div>
        )}
      </Card>

      <DialogoObservacion
        item={observando}
        onClose={() => setObservando(null)}
        filtros={filtros}
      />

      <ConfirmDialog
        abierto={!!aBorrar}
        onOpenChange={(v) => !v && setABorrar(null)}
        titulo={aBorrar === 'lote' ? `¿Eliminar la conciliación #${lote.id}?` : '¿Eliminar este ítem?'}
        mensaje={
          aBorrar === 'lote'
            ? 'Se borran todos sus ítems e imágenes. No se puede deshacer.'
            : 'Se borra el ítem y su imagen. No se puede deshacer.'
        }
        onConfirm={() => {
          if (aBorrar === 'lote') router.post(`/conciliar/lote/${lote.id}/eliminar/`);
          else accionItem(aBorrar.id, 'eliminar');
          setABorrar(null);
        }}
      />
    </>
  );
}

/** Nota libre sobre un ítem (p. ej. "confirmado por WhatsApp con el corresponsal"). */
function DialogoObservacion({ item, onClose, filtros }) {
  const { data, setData, post, processing } = useForm({
    observaciones: item?.observaciones || '',
    r: filtros.r,
    sort: filtros.sort,
  });

  if (!item) return null;

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent titulo="Observación" icon={MessageSquareText} descripcion="Nota libre sobre este ítem">
        <form
          className="card-pad space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            post(`/conciliar/item/${item.id}/observacion/`, { preserveScroll: true, onSuccess: onClose });
          }}
        >
          <p className="t-meta">
            {item.ref || 'Sin referencia'} · queda guardada junto al ítem y se ve en el panel.
          </p>
          <textarea
            className="field min-h-24"
            autoFocus
            value={data.observaciones}
            onChange={(e) => setData('observaciones', e.target.value)}
            placeholder="Ej.: confirmado por WhatsApp con el corresponsal."
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
            <Button type="submit" variant="primary" cargando={processing}>Guardar</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
