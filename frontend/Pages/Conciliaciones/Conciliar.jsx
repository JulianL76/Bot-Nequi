import { useState } from 'react';
import { usePage } from '@inertiajs/react';
import { ArrowLeftRight, CircleCheck, FolderOpen, Route, Sparkles } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Card, Label, Select } from '../../ui/index.jsx';
import { ZonaSubida } from '../../components/ZonaSubida.jsx';
import { csrfToken } from '../../lib/csrf.js';

export default function Conciliar({ rutas, guardadas, urlsPagina }) {
  const { urls } = usePage().props;
  const [ruta, setRuta] = useState('');
  const csrf = csrfToken();

  return (
    <div className="max-w-3xl">
      <Cabecera
        titulo="Conciliar comprobantes por ruta"
        subtitulo="Sube las capturas de la ruta y el gestor las cruza con los comprobantes registrados."
      />

      <Card className="card-pad relative overflow-hidden">
        {/* Formulario clásico: lo intercepta el motor de subida por su id. */}
        <form id="upload-form" method="post" action={urls.conciliar} encType="multipart/form-data">
          <input type="hidden" name="csrfmiddlewaretoken" value={csrf} />

          <div className="mb-3">
            <Label htmlFor="ruta">
              Ruta <span className="text-bad-600">*</span>
            </Label>
            <Select id="ruta" name="ruta" required value={ruta} onChange={(e) => setRuta(e.target.value)}>
              <option value="">Elige la ruta de estas capturas…</option>
              {rutas.map((r) => (
                <option key={r.id} value={r.id}>
                  Ruta {r.numero}{r.nombre ? ` — ${r.nombre}` : ''}
                </option>
              ))}
            </Select>
            <p className="hint">
              La ruta se aplica a todas las imágenes de esta conciliación.
            </p>
          </div>

          <ZonaSubida guardadas={guardadas} verbo="conciliar" urls={urlsPagina} csrf={csrf} />

          <ul className="mt-4 space-y-1.5 t-meta">
            <li className="flex items-start gap-2">
              <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-ok-600 dark:text-ok-400" />
              Cada imagen se sube por separado: puedes seguir agregando más y lo ya subido no se pierde.
            </li>
            <li className="solo-pc flex items-start gap-2">
              <FolderOpen className="mt-0.5 size-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
              También puedes soltar un <strong className="font-semibold text-content">.zip</strong> con las capturas dentro.
            </li>
            <li className="flex items-start gap-2">
              <Sparkles className="mt-0.5 size-3.5 shrink-0 text-accent-500" />
              Al terminar verás el resultado ítem por ítem: OK, pendiente, no está, revisión o duplicado.
            </li>
          </ul>

          <button
            id="btn-procesar"
            type="submit"
            className="btn-primary btn-lg mt-5 w-full sm:w-auto"
            disabled={!ruta}
          >
            <ArrowLeftRight />
            <span id="btn-text">Conciliar</span>
          </button>
          {!ruta && <p className="hint">Elige una ruta para poder conciliar.</p>}
        </form>

        <div
          id="upload-overlay"
          style={{ display: 'none' }}
          className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-surface/95 p-6 text-center backdrop-blur-sm"
        >
          <span className="size-10 animate-spin rounded-full border-[3px] border-brand-200 border-t-brand-600 dark:border-brand-900" />
          <h2 className="text-base font-bold" id="upload-title">Preparando la conciliación…</h2>
          <p className="max-w-sm t-cuerpo text-muted" id="upload-msg">
            Ya está todo subido; ahora se encola el cruce. Tarda solo un momento.
          </p>
        </div>
      </Card>

      {rutas.length === 0 && (
        <p className="mt-3 rounded-[var(--radius-field)] border border-warn-500/25 bg-warn-100 px-3 py-2 text-xs text-warn-600 dark:bg-warn-500/10 dark:text-warn-400">
          <Route className="mr-1 inline size-3.5" />
          No hay rutas activas. Crea una en Configuración → Rutas antes de conciliar.
        </p>
      )}
    </div>
  );
}
