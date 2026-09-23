/**
 * Zona de subida de imágenes.
 *
 * El marcado reproduce el contrato que espera el motor de FilePond (las clases
 * `fp-*` y el input `.filepond-input`); el motor lo engancha por selectores.
 * Se usa igual en "Subir comprobantes" y en "Conciliar".
 */
import { useEffect, useRef, useState } from 'react';
import { CircleCheck, RefreshCw } from 'lucide-react';
import { cargarFilePond } from '../lib/filepond.js';

export function ZonaSubida({ guardadas = 0, verbo = 'procesar', urls, csrf }) {
  const contenedor = useRef(null);
  const [listo, setListo] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let vivo = true;
    cargarFilePond()
      .then(() => {
        if (!vivo || !window.initPondSubida) return;
        window.initPondSubida({
          urlArchivo: urls.subirArchivo,
          urlDescartar: urls.descartar,
          csrf,
          guardadas,
          textoBoton: verbo === 'conciliar' ? 'Conciliar' : 'Procesar',
          verbo,
        });
        setListo(true);
      })
      .catch(() => vivo && setError('No se pudo cargar el selector de imágenes. Recarga la página.'));
    return () => { vivo = false; };
    // Se monta una vez por pantalla: el motor toma el DOM y lo gestiona él.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={contenedor}>
      {/* Marcador mientras cargan los scripts; el motor lo oculta al terminar. */}
      <div
        className="fp-cargando flex items-center justify-center gap-2.5 rounded-[var(--radius-card)] border border-dashed border-brand-300 bg-brand-50 px-4 py-10 t-cuerpo font-medium text-brand-700 dark:border-brand-500/40 dark:bg-brand-500/10 dark:text-brand-300"
        style={{ display: listo ? 'none' : '' }}
      >
        <span className="size-3.5 animate-spin rounded-full border-2 border-brand-300 border-t-brand-600" />
        Cargando el selector de imágenes…
      </div>

      {error && (
        <p className="mt-2 rounded-[var(--radius-field)] border border-bad-500/25 bg-bad-100 px-3 py-2 t-cuerpo text-bad-600 dark:bg-bad-500/10 dark:text-bad-400">
          {error}
        </p>
      )}

      <input
        type="file"
        name="imagenes"
        multiple
        accept="image/*,.zip,application/zip"
        className="filepond-input"
      />

      {/* Progreso de la subida en curso (una petición por imagen). */}
      <div className="fp-estado mt-3" style={{ display: 'none' }}>
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface-inset">
          <div className="fp-barra h-full rounded-full bg-brand-600 transition-[width] duration-200 ease-out" style={{ width: '0%' }} />
        </div>
        <div className="t-cuerpo mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="fp-texto nums text-muted" />
          <button type="button" className="fp-reintentar btn-secondary btn-sm" style={{ display: 'none' }}>
            <RefreshCw />Reintentar
          </button>
        </div>
      </div>

      {/* Imágenes ya guardadas: sobreviven a recargas y a cerrar la página. */}
      <div
        className="fp-guardadas mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[var(--radius-field)] border border-ok-500/25 bg-ok-100 px-3 py-2 t-cuerpo dark:bg-ok-500/10"
        style={guardadas ? undefined : { display: 'none' }}
      >
        <CircleCheck className="size-3.5 shrink-0 text-ok-600 dark:text-ok-400" />
        <span className="fp-guardadas-txt font-medium text-ok-600 dark:text-ok-400">
          {guardadas} {guardadas === 1 ? 'imagen guardada, lista' : 'imágenes guardadas, listas'} para {verbo}
        </span>
        <button type="button" className="fp-descartar ml-auto font-medium text-muted underline underline-offset-2 hover:text-bad-600">
          Descartar
        </button>
      </div>
    </div>
  );
}
