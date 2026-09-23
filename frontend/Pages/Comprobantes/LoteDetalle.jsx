import { useState } from 'react';
import { Link, router, usePage } from '@inertiajs/react';
import {
  ChevronLeft, CircleAlert, Download, Image, Pause, Play, ReceiptText, RefreshCw, Trash2,
} from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Button, Card, CardHeader, CardTitle, Badge, Progress } from '../../ui/index.jsx';
import { ConfirmDialog } from '../../ui/Dialog.jsx';
import { BadgeEstadoLote } from './Lotes.jsx';
import { abrirImagen } from '../../components/VisorImagen.jsx';
import { Estadistica, FilaEstadisticas } from '../../components/Estadistica.jsx';
import { useProgreso } from '../../lib/useProgreso.js';
import { fechaHora, numero, plural } from '../../lib/formato.js';

export default function LoteDetalle({ lote, fallidos, urlsPagina }) {
  const { urls } = usePage().props;
  const [aBorrar, setABorrar] = useState(false);

  const activo = ['procesando', 'en_cola'].includes(lote.estado);
  // Solo se sondea mientras hay algo que mirar; al terminar se recarga la vista.
  const { datos, atascado } = useProgreso(urlsPagina.progreso, lote, {
    activo,
    alTerminar: () => router.reload(),
  });
  const d = datos || lote;

  return (
    <>
      <Cabecera
        titulo={`Subida #${lote.id}`}
        subtitulo={`${fechaHora(lote.creadoEn)} · ${numero(lote.total)} ${plural(lote.total, 'imagen', 'imágenes')}`}
      >
        <Button size="sm" asChild>
          <Link href={urls.subidas}>
            <ChevronLeft /><span className="hidden sm:inline">Subidas</span>
          </Link>
        </Button>
      </Cabecera>

      <Card className="card-pad mb-3">
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <BadgeEstadoLote lote={{ ...lote, estadoTexto: d.estadoTexto || d.estado_display || lote.estadoTexto }} />
          <span className="nums text-[13px] font-bold">{d.progreso ?? 0}%</span>
        </div>
        <Progress valor={d.progreso ?? 0} />

        {atascado && activo && (
          <p className="mt-2 text-[11px] text-warn-600 dark:text-warn-400">
            Activo pero sin avanzar hace un rato: seguramente esperando respuesta de la IA.
          </p>
        )}

        <FilaEstadisticas className="mt-3">
          <Estadistica etiqueta={`Procesadas / ${numero(lote.total)}`} valor={numero(d.procesadas)} />
          <Estadistica etiqueta="Exitosas" valor={numero(d.exitosas)} tono="ok" />
          <Estadistica etiqueta="Duplicadas" valor={numero(d.duplicadas)} tono="aviso" />
          <Estadistica etiqueta="Fallidas" valor={numero(d.fallidas)} tono={d.fallidas > 0 ? 'grave' : 'neutro'} />
        </FilaEstadisticas>

        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3">
          {activo && (
            <Button size="sm" onClick={() => router.post(`/comprobantes/lote/${lote.id}/pausar/`)}>
              <Pause />Pausar
            </Button>
          )}
          {lote.estado === 'pausado' && (
            <Button variant="success" size="sm" onClick={() => router.post(`/comprobantes/lote/${lote.id}/reanudar/`)}>
              <Play />Reanudar
            </Button>
          )}
          {d.fallidas > 0 && !activo && (
            <Button variant="primary" size="sm" onClick={() => router.post(`/comprobantes/lote/${lote.id}/reprocesar/`)}>
              <RefreshCw />Reintentar {d.fallidas} {plural(d.fallidas, 'fallida')}
            </Button>
          )}

          <Button size="sm" asChild>
            <Link href={`${urls.comprobantes}?lote=${lote.id}`}><ReceiptText />Comprobantes</Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <a href={`/comprobantes/lote/${lote.id}/descargar/`}><Image />Imágenes (.zip)</a>
          </Button>
          <Button variant="ghost" size="sm" asChild className="text-ok-600 dark:text-ok-400">
            <a href={`${urls.exportarComprobantes}?lote=${lote.id}`}><Download />Excel</a>
          </Button>

          <Button
            variant="ghost" size="sm"
            className="ml-auto text-bad-600 dark:text-bad-400"
            onClick={() => setABorrar(true)}
          >
            <Trash2 />Borrar subida
          </Button>
        </div>
      </Card>

      {fallidos.length > 0 && (
        <Card>
          <CardHeader>
            <CircleAlert className="size-4 text-bad-600 dark:text-bad-400" />
            <CardTitle>Errores</CardTitle>
            <Badge tono="bad" className="nums ml-auto">{fallidos.length}</Badge>
          </CardHeader>

          <div className="max-h-[50vh] space-y-1.5 overflow-y-auto p-2.5">
            {fallidos.map((a) => (
              <div key={a.id} className="flex items-center gap-2.5 rounded-[var(--radius-field)] border border-bad-500/20 bg-bad-100/50 p-2 dark:bg-bad-500/5">
                {a.imagen && (
                  <button
                    type="button"
                    className="shrink-0 overflow-hidden rounded-md transition active:scale-96"
                    aria-label={`Ver ${a.nombre}`}
                    onClick={() => abrirImagen(a.imagen, a.nombre)}
                  >
                    <img src={a.imagen} alt="" className="size-10 border border-line object-cover" />
                  </button>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium">{a.nombre}</p>
                  <p className="text-[11px] text-bad-600 dark:text-bad-400">{a.error}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <ConfirmDialog
        abierto={aBorrar}
        onOpenChange={setABorrar}
        titulo={`¿Eliminar la subida #${lote.id}?`}
        mensaje="Se borrarán también sus comprobantes y las imágenes. No se puede deshacer."
        confirmar="Eliminar subida"
        onConfirm={() => router.post(`/comprobantes/lote/${lote.id}/eliminar/`)}
      />
    </>
  );
}
