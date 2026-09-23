import { Link, router, usePage } from '@inertiajs/react';
import { CircleCheck, Package, Pause } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Badge, Button, Card, EmptyState, Progress } from '../../ui/index.jsx';
import { useProgreso } from '../../lib/useProgreso.js';
import { fechaHora, numero, plural } from '../../lib/formato.js';

function TarjetaLote({ lote }) {
  // Cuando el lote termina se recarga la pantalla: ya no pertenece aquí.
  const { datos, atascado } = useProgreso(lote.urlProgreso, lote, {
    alTerminar: () => router.reload({ only: ['lotes'] }),
  });

  const d = datos || lote;

  return (
    <Card className="card-pad">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Link href={`/comprobantes/lote/${lote.id}/`} className="font-display font-bold text-brand-600 hover:underline dark:text-brand-400">
          Subida #{lote.id}
        </Link>
        <Badge tono={atascado ? 'warn' : 'brand'} punto className="badge-vivo">
          {atascado ? 'Esperando a la IA' : (d.estadoTexto || d.estado_display || 'Procesando')}
        </Badge>
        <span className="nums ml-auto t-meta">
          {fechaHora(lote.creadoEn)} · {numero(lote.total)} {plural(lote.total, 'imagen', 'imágenes')}
        </span>
      </div>

      <div className="mt-2.5">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="t-meta">
            <span className="nums font-semibold text-content">{numero(d.procesadas)}</span>
            <span className="nums"> / {numero(lote.total)}</span> procesadas
          </span>
          <span className="t-seccion nums">{d.progreso ?? 0}%</span>
        </div>
        <Progress valor={d.progreso ?? 0} activo={!atascado} />
      </div>

      {atascado && (
        <p className="t-meta mt-2 text-warn-600 dark:text-warn-400">
          Sigue activo, pero la IA no ha respondido en un rato. Puede ser un límite de cuota; se reintenta solo.
        </p>
      )}

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <Badge tono="ok"><span className="nums">{d.exitosas}</span> ok</Badge>
        <Badge tono="warn"><span className="nums">{d.duplicadas}</span> dup</Badge>
        <Badge tono="bad"><span className="nums">{d.fallidas}</span> fallidas</Badge>

        <Button
          size="sm" className="ml-auto"
          onClick={() => router.post(`/comprobantes/lote/${lote.id}/pausar/`)}
        >
          <Pause />Pausar
        </Button>
      </div>
    </Card>
  );
}

export default function EnProceso({ lotes }) {
  const { urls } = usePage().props;

  return (
    <>
      <Cabecera
        titulo="En proceso"
        subtitulo="El avance se actualiza solo; puedes cerrar esta pantalla sin detener el análisis."
      >
        <Button size="sm" asChild><Link href={urls.subidas}><Package />Historial</Link></Button>
      </Cabecera>

      {lotes.length === 0 ? (
        <Card>
          <EmptyState
            icon={CircleCheck}
            titulo="No hay subidas en proceso."
            descripcion="Todo lo que subiste ya terminó de analizarse."
          >
            <Button size="sm" asChild><Link href={urls.subidas}><Package />Ver historial</Link></Button>
          </EmptyState>
        </Card>
      ) : (
        <div className="rise-lista space-y-2">
          {lotes.map((l) => <TarjetaLote key={l.id} lote={l} />)}
        </div>
      )}
    </>
  );
}
