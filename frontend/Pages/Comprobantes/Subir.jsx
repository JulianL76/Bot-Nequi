import { Link, usePage } from '@inertiajs/react';
import { CircleCheck, CloudUpload, FolderOpen, Package, Sparkles } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Button, Card } from '../../ui/index.jsx';
import { ZonaSubida } from '../../components/ZonaSubida.jsx';
import { csrfToken } from '../../lib/csrf.js';

export default function Subir({ guardadas, urlsPagina }) {
  const { urls } = usePage().props;
  const csrf = csrfToken();

  return (
    <div className="max-w-3xl">
      <Cabecera
        titulo="Subir comprobantes"
        subtitulo="Selecciona las fotos: cada una se guarda apenas la eliges, y después se analizan en lote."
      />

      <Card className="card-pad relative overflow-hidden">
        {/*
          Formulario clásico, no una visita de Inertia: el motor de subida lo
          intercepta por id y muestra su propio overlay mientras el servidor
          crea el lote y lo encola.
        */}
        <form id="upload-form" method="post" encType="multipart/form-data">
          <input type="hidden" name="csrfmiddlewaretoken" value={csrf} />

          <ZonaSubida guardadas={guardadas} verbo="procesar" urls={urlsPagina} csrf={csrf} />

          <ul className="mt-4 space-y-1.5 t-meta">
            <li className="flex items-start gap-2">
              <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-ok-600 dark:text-ok-400" />
              Cada imagen se sube por separado: puedes seguir agregando más y lo ya subido no se pierde.
            </li>
            <li className="solo-pc flex items-start gap-2">
              <FolderOpen className="mt-0.5 size-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
              También puedes soltar un <strong className="font-semibold text-content">.zip</strong> con las fotos dentro: se abre en el servidor.
            </li>
            <li className="flex items-start gap-2">
              <Sparkles className="mt-0.5 size-3.5 shrink-0 text-accent-500" />
              El análisis se hace en lotes de 30.
            </li>
          </ul>

          <button id="btn-procesar" type="submit" className="btn-primary btn-lg mt-5 w-full sm:w-auto">
            <CloudUpload />
            <span id="btn-text">Procesar</span>
          </button>
        </form>

        {/* Overlay mientras el servidor crea el lote y lo encola. */}
        <div
          id="upload-overlay"
          style={{ display: 'none' }}
          className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-surface/95 p-6 text-center backdrop-blur-sm"
        >
          <span className="size-10 animate-spin rounded-full border-[3px] border-brand-200 border-t-brand-600 dark:border-brand-900" />
          <h2 className="text-base font-bold" id="upload-title">Preparando el lote…</h2>
          <p className="max-w-sm t-cuerpo text-muted" id="upload-msg">
            Ya está todo subido; ahora se encola el análisis. Tarda solo un momento.
          </p>
        </div>
      </Card>

      <Button variant="ghost" size="sm" asChild className="mt-3">
        <Link href={urls.subidas}><Package />Ver subidas anteriores</Link>
      </Button>
    </div>
  );
}
