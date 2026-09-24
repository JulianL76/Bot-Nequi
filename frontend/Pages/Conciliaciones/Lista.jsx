import { useState } from 'react';
import { Link, router, usePage } from '@inertiajs/react';
import {
  ArrowLeftRight, CalendarDays, ChartColumn, ChevronLeft, ChevronRight, Eye, List,
  ListChecks, MessageSquareText, Route, Trash2,
} from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { BarraAcciones } from '../../components/BarraAcciones.jsx';
import { Badge, Button, Card, Checkbox, EmptyState } from '../../ui/index.jsx';
import { ConfirmDialog } from '../../ui/Dialog.jsx';
import { claveDia, diaLargo, fechaHora, numero, plural, soloHora } from '../../lib/formato.js';

function BadgeEstadoConc({ lote }) {
  const tonos = {
    completado: 'ok', con_errores: 'bad', pausado: 'warn',
    procesando: 'brand', en_cola: 'brand',
  };
  const tono = tonos[lote.estado] || 'neutral';
  const latiendo = ['procesando', 'en_cola'].includes(lote.estado);
  return (
    <Badge tono={tono} punto={tono !== 'neutral'} className={latiendo ? '[&_.dot]:animate-pulse' : undefined}>
      {lote.estadoTexto}
    </Badge>
  );
}

/** Chips de resultado. Solo se pinta lo que tiene valor: un "0 REVISIÓN"
 *  ocupa el mismo espacio que un dato real y no dice nada. */
function Resultados({ lote }) {
  const chips = [
    { n: lote.ok,         tono: 'ok',    punto: true,  texto: 'ok' },
    { n: lote.pendientes, tono: 'warn',  punto: true,  texto: 'pend.' },
    { n: lote.noEsta,     tono: 'bad',   punto: true,  texto: 'no está' },
    { n: lote.revision,   tono: 'warn',  punto: false, texto: 'revisión' },
    { n: lote.duplicados, tono: 'brand', punto: false, texto: 'dup' },
  ].filter((c) => c.n > 0);

  if (!chips.length) return null;

  return (
    <div className="mt-2.5 flex flex-wrap gap-1.5">
      {chips.map((c) => (
        <Badge key={c.texto} tono={c.tono} punto={c.punto}>
          <span className="nums">{c.n}</span> {c.texto}
        </Badge>
      ))}
    </div>
  );
}

/** Una conciliación del historial. `soloLaHora` cuando el día ya lo dice el
 *  encabezado del grupo: repetirlo en cada fila es ruido. */
function TarjetaLote({ lote: l, seleccion, setSeleccion, soloLaHora = false }) {
  return (
    <Card className="card-pad">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Checkbox
          checked={!!seleccion[l.id]}
          onCheckedChange={(v) => setSeleccion((p) => ({ ...p, [l.id]: !!v }))}
          aria-label={`Seleccionar conciliación ${l.id}`}
        />
        <Link
          href={`/conciliar/lote/${l.id}/`}
          className="font-display font-bold transition-colors hover:text-brand-600 dark:hover:text-brand-400"
        >
          Conciliación #{l.id}
        </Link>
        <BadgeEstadoConc lote={l} />
        {l.ruta != null && (
          <span className="badge-ruta"><Route />Ruta {l.ruta}</span>
        )}
        {l.nObs > 0 && (
          <Badge><MessageSquareText />{l.nObs}</Badge>
        )}

        <span className="nums ml-auto t-meta">
          {soloLaHora ? soloHora(l.creadoEn) : fechaHora(l.creadoEn)}
          {' · '}{numero(l.total)} {plural(l.total, 'imagen', 'imágenes')}
        </span>
      </div>

      <Resultados lote={l} />

      <div className="mt-2.5 flex items-center gap-1 border-t border-line pt-2.5">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/conciliar/lote/${l.id}/`}><Eye />Ver detalle</Link>
        </Button>
      </div>
    </Card>
  );
}

const CLAVE_AGRUPAR = 'conciliaciones:agrupar-por-fecha';

/** La preferencia se guarda: quien concilia por días lo quiere siempre así. */
function useAgruparPorFecha() {
  const [agrupar, setAgrupar] = useState(() => {
    try { return localStorage.getItem(CLAVE_AGRUPAR) === '1'; } catch { return false; }
  });
  const alternar = () => setAgrupar((v) => {
    try { localStorage.setItem(CLAVE_AGRUPAR, v ? '0' : '1'); } catch { /* sin almacenamiento */ }
    return !v;
  });
  return [agrupar, alternar];
}

/** Parte la lista en días conservando el orden que ya trae del servidor. */
function porDia(lotes) {
  const dias = [];
  for (const l of lotes) {
    const clave = claveDia(l.creadoEn);
    const ultimo = dias[dias.length - 1];
    if (ultimo && ultimo.clave === clave) ultimo.lotes.push(l);
    else dias.push({ clave, iso: l.creadoEn, lotes: [l] });
  }
  return dias.map((d) => ({
    ...d,
    // Resumen del día: es lo que se compara contra el cuadre.
    imagenes: d.lotes.reduce((n, l) => n + l.total, 0),
    ok: d.lotes.reduce((n, l) => n + l.ok, 0),
  }));
}

function EncabezadoDia({ dia }) {
  return (
    <div className="sticky top-[var(--h-topbar)] z-10 -mx-1 flex flex-wrap items-baseline gap-x-2 bg-surface-sunken/95 px-1 py-1.5 backdrop-blur">
      <CalendarDays className="size-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
      <span className="t-seccion">{diaLargo(dia.iso)}</span>
      <span className="nums t-meta">
        {numero(dia.lotes.length)} {plural(dia.lotes.length, 'conciliación', 'conciliaciones')}
        {' · '}{numero(dia.imagenes)} {plural(dia.imagenes, 'imagen', 'imágenes')}
        {' · '}{numero(dia.ok)} OK
      </span>
    </div>
  );
}

export default function Lista({ lotes, paginacion }) {
  const { urls } = usePage().props;
  const [seleccion, setSeleccion] = useState({});
  const [confirmar, setConfirmar] = useState(false);
  const ids = Object.keys(seleccion).filter((k) => seleccion[k]);
  const [agrupar, alternarAgrupar] = useAgruparPorFecha();

  return (
    <>
      <Cabecera titulo="Historial de conciliaciones" subtitulo="Cada conciliación agrupa las imágenes de una ruta.">
        <Button
          size="sm"
          variant={agrupar ? 'primary' : 'secondary'}
          onClick={alternarAgrupar}
          aria-pressed={agrupar}
          title={agrupar ? 'Ver como lista continua' : 'Agrupar por fecha'}
        >
          {agrupar ? <List /> : <CalendarDays />}
          <span className="hidden sm:inline">{agrupar ? 'Sin agrupar' : 'Por fecha'}</span>
        </Button>
        <Button size="sm" asChild><Link href={urls.panel}><ChartColumn />Panel</Link></Button>
        <Button variant="primary" size="sm" asChild>
          <Link href={urls.conciliar}><ArrowLeftRight />Conciliar</Link>
        </Button>
      </Cabecera>

      {lotes.length === 0 ? (
        <Card>
          <EmptyState
            icon={ListChecks}
            titulo="Todavía no hay conciliaciones."
            descripcion="Sube las capturas de una ruta y el gestor las cruza con los comprobantes."
          >
            <Button variant="primary" size="sm" asChild>
              <Link href={urls.conciliar}>Conciliar ahora</Link>
            </Button>
          </EmptyState>
        </Card>
      ) : (
        agrupar ? (
          <div className="space-y-4">
            {porDia(lotes).map((dia) => (
              <section key={dia.clave}>
                <EncabezadoDia dia={dia} />
                <div className="rise-lista mt-1.5 space-y-2">
                  {dia.lotes.map((l) => (
                    <TarjetaLote key={l.id} lote={l} seleccion={seleccion}
                                 setSeleccion={setSeleccion} soloLaHora />
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="rise-lista space-y-2">
            {lotes.map((l) => (
              <TarjetaLote key={l.id} lote={l} seleccion={seleccion} setSeleccion={setSeleccion} />
            ))}
          </div>
        )
      )}

      {paginacion.paginas > 1 && (
        <div className="mt-4 flex items-center justify-center gap-1">
          <Button size="sm" icon aria-label="Página anterior" disabled={paginacion.pagina <= 1}
                  onClick={() => router.get(urls.conciliaciones, { page: paginacion.pagina - 1 })}>
            <ChevronLeft />
          </Button>
          <span className="nums px-2 t-meta">
            <span className="font-semibold text-content">{paginacion.pagina}</span> / {paginacion.paginas}
          </span>
          <Button size="sm" icon aria-label="Página siguiente" disabled={paginacion.pagina >= paginacion.paginas}
                  onClick={() => router.get(urls.conciliaciones, { page: paginacion.pagina + 1 })}>
            <ChevronRight />
          </Button>
        </div>
      )}

      <BarraAcciones visible={ids.length > 0} ancho="32rem">
          <div className="flex items-center gap-2 rounded-[var(--radius-card)] border border-line bg-surface-raised p-2 shadow-lg">
            <span className="pl-1 text-xs font-semibold">
              <span className="nums">{ids.length}</span> {plural(ids.length, 'conciliación', 'conciliaciones')}
            </span>
            <Button variant="danger" size="sm" className="ml-auto" onClick={() => setConfirmar(true)}>
              <Trash2 />Eliminar
            </Button>
          </div>
      </BarraAcciones>

      <ConfirmDialog
        abierto={confirmar}
        onOpenChange={setConfirmar}
        titulo={`¿Eliminar ${ids.length} ${plural(ids.length, 'conciliación', 'conciliaciones')}?`}
        mensaje="Se borran los lotes seleccionados con todos sus ítems e imágenes. No se puede deshacer."
        onConfirm={() => router.post('/conciliar/lotes/eliminar-masivo/', { seleccion: ids },
          { onSuccess: () => setSeleccion({}) })}
      />
    </>
  );
}
