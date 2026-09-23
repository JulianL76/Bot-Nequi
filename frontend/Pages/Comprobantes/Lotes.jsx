import { useState } from 'react';
import { Link, router, usePage } from '@inertiajs/react';
import {
  ChevronLeft, ChevronRight, CloudUpload, Download, Eye, Image, Loader,
  Package, Plus, ReceiptText, RefreshCw, Trash2,
} from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Badge, Button, Card, EmptyState } from '../../ui/index.jsx';
import { ConfirmDialog } from '../../ui/Dialog.jsx';
import { fechaHora, numero, plural } from '../../lib/formato.js';

/** Un lote se lee de un vistazo por su estado: color + texto, nunca color solo. */
export function BadgeEstadoLote({ lote }) {
  const tonos = {
    completado: 'ok',
    con_errores: 'bad',
    pausado: 'warn',
    procesando: 'brand',
    en_cola: 'brand',
  };
  const tono = tonos[lote.estado] || 'neutral';
  const latiendo = lote.estado === 'procesando' || lote.estado === 'en_cola';
  return (
    <Badge tono={tono} punto={tono !== 'neutral'} className={latiendo ? '[&_.dot]:animate-pulse' : undefined}>
      {lote.estadoTexto}
    </Badge>
  );
}

export default function Lotes({ lotes, paginacion }) {
  const { urls } = usePage().props;
  const [aBorrar, setABorrar] = useState(null);

  return (
    <>
      <Cabecera titulo="Subidas" subtitulo="Cada subida agrupa las imágenes procesadas juntas.">
        <Button size="sm" asChild className="hidden md:inline-flex">
          <Link href={urls.enProceso}><Loader />En proceso</Link>
        </Button>
        <Button variant="primary" size="sm" asChild>
          <Link href={urls.subir}><Plus />Subir</Link>
        </Button>
      </Cabecera>

      {lotes.length === 0 ? (
        <Card>
          <EmptyState
            icon={Package}
            titulo="Aún no has subido ningún lote."
            descripcion="Cuando proceses imágenes, cada tanda aparecerá aquí con su resultado."
          >
            <Button variant="primary" size="sm" asChild>
              <Link href={urls.subir}><CloudUpload />Subir comprobantes</Link>
            </Button>
          </EmptyState>
        </Card>
      ) : (
        <div className="rise-lista space-y-2">
          {lotes.map((l) => (
            <Card key={l.id} className="card-pad">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <Link
                  href={`/comprobantes/lote/${l.id}/`}
                  className="font-display font-bold transition-colors hover:text-brand-600 dark:hover:text-brand-400"
                >
                  Subida #{l.id}
                </Link>
                <BadgeEstadoLote lote={l} />
                <span className="nums ml-auto t-meta">
                  {fechaHora(l.creadoEn)} · {numero(l.total)} {plural(l.total, 'imagen', 'imágenes')}
                </span>
              </div>

              <div className="mt-2.5 flex flex-wrap gap-1.5">
                <Badge tono="ok"><span className="nums">{l.exitosas}</span> ok</Badge>
                <Badge tono="warn"><span className="nums">{l.duplicadas}</span> dup</Badge>
                <Badge tono="bad"><span className="nums">{l.fallidas}</span> fallidas</Badge>
              </div>

              <div className="mt-2.5 flex flex-wrap items-center gap-1 border-t border-line pt-2.5">
                <Button variant="ghost" size="sm" asChild>
                  <Link href={`/comprobantes/lote/${l.id}/`}><Eye />Detalle</Link>
                </Button>

                {(l.exitosas > 0 || l.duplicadas > 0) && (
                  <>
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`${urls.comprobantes}?lote=${l.id}`}><ReceiptText />Comprobantes</Link>
                    </Button>
                    {/* Descargas: enlace normal, no visita de Inertia. */}
                    <Button variant="ghost" size="sm" asChild>
                      <a href={`/comprobantes/lote/${l.id}/descargar/`} title="Descargar las imágenes (.zip)">
                        <Image /><span className="hidden sm:inline">Imágenes</span>
                      </a>
                    </Button>
                    <Button variant="ghost" size="sm" asChild className="text-ok-600 dark:text-ok-400">
                      <a href={`${urls.exportarComprobantes}?lote=${l.id}`} title="Descargar Excel de esta subida">
                        <Download /><span className="hidden sm:inline">Excel</span>
                      </a>
                    </Button>
                  </>
                )}

                {l.fallidas > 0 && !['procesando', 'en_cola'].includes(l.estado) && (
                  <Button
                    variant="ghost" size="sm"
                    className="text-warn-600 dark:text-warn-400"
                    onClick={() => router.post(`/comprobantes/lote/${l.id}/reprocesar/`)}
                  >
                    <RefreshCw />Reintentar {l.fallidas}
                  </Button>
                )}

                <Button
                  variant="ghost" size="sm"
                  className="ml-auto text-bad-600 dark:text-bad-400"
                  onClick={() => setABorrar(l)}
                >
                  <Trash2 /><span className="hidden sm:inline">Borrar</span>
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {paginacion.paginas > 1 && (
        <div className="mt-4 flex items-center justify-center gap-1">
          <Button
            size="sm" icon aria-label="Página anterior"
            disabled={paginacion.pagina <= 1}
            onClick={() => router.get(urls.subidas, { page: paginacion.pagina - 1 })}
          >
            <ChevronLeft />
          </Button>
          <span className="nums px-2 t-meta">
            <span className="font-semibold text-content">{paginacion.pagina}</span> / {paginacion.paginas}
          </span>
          <Button
            size="sm" icon aria-label="Página siguiente"
            disabled={paginacion.pagina >= paginacion.paginas}
            onClick={() => router.get(urls.subidas, { page: paginacion.pagina + 1 })}
          >
            <ChevronRight />
          </Button>
        </div>
      )}

      <ConfirmDialog
        abierto={!!aBorrar}
        onOpenChange={(v) => !v && setABorrar(null)}
        titulo={`¿Eliminar la subida #${aBorrar?.id}?`}
        mensaje={`Se borrarán también sus ${numero(aBorrar?.exitosas ?? 0)} ${plural(aBorrar?.exitosas ?? 0, 'comprobante')} y las imágenes. No se puede deshacer.`}
        confirmar="Eliminar subida"
        onConfirm={() => router.post(`/comprobantes/lote/${aBorrar.id}/eliminar/`)}
      />
    </>
  );
}
