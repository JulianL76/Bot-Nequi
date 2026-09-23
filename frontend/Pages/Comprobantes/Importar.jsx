import { useRef, useState } from 'react';
import { useForm } from '@inertiajs/react';
import { Check, FileText, Upload } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Button, Card } from '../../ui/index.jsx';
import { cn } from '../../ui/cn.js';

export default function Importar() {
  const entrada = useRef(null);
  const [sobre, setSobre] = useState(false);
  const { data, setData, post, processing, progress } = useForm({ archivo: null });

  const enviar = (e) => {
    e.preventDefault();
    if (data.archivo) post('/comprobantes/importar/', { forceFormData: true });
  };

  return (
    <div className="max-w-3xl">
      <Cabecera
        titulo="Importar"
        subtitulo="Se omiten las referencias que ya existan, así que puedes reimportar sin duplicar."
      />

      <Card className="card-pad">
        <form onSubmit={enviar}>
          <label
            onDragOver={(e) => { e.preventDefault(); setSobre(true); }}
            onDragEnter={(e) => { e.preventDefault(); setSobre(true); }}
            onDragLeave={(e) => { e.preventDefault(); setSobre(false); }}
            onDrop={(e) => {
              e.preventDefault();
              setSobre(false);
              const f = e.dataTransfer.files?.[0];
              if (f) setData('archivo', f);
            }}
            className={cn(
              'block cursor-pointer rounded-[var(--radius-card)] border border-dashed p-8 text-center transition-colors md:p-10',
              sobre ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10' : 'border-line-strong hover:border-brand-400 hover:bg-surface-inset',
            )}
          >
            <input
              ref={entrada}
              type="file"
              accept=".xlsx,.xlsm"
              className="hidden"
              onChange={(e) => setData('archivo', e.target.files?.[0] || null)}
            />

            <FileText className="mx-auto mb-2.5 size-9 text-brand-500" strokeWidth={1.5} />
            <p className="t-seccion">Arrastra el archivo o haz clic para elegirlo</p>
            <p className="mt-1 t-meta">Formatos .xlsx y .xlsm</p>

            {data.archivo && (
              <p className="t-meta mt-3 inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-ok-100 px-2.5 py-1 font-semibold text-ok-600 dark:bg-ok-500/15 dark:text-ok-400">
                <Check className="size-3" strokeWidth={3} />
                {data.archivo.name}
              </p>
            )}
          </label>

          {progress && (
            <p className="nums mt-2 t-meta">Subiendo… {progress.percentage}%</p>
          )}

          <Button type="submit" variant="primary" size="lg" className="mt-4 w-full sm:w-auto"
                  disabled={!data.archivo} cargando={processing}>
            <Upload />Importar
          </Button>
        </form>

        {/* El formato se muestra tal cual para no dejar dudas. */}
        <div className="mt-6 border-t border-line pt-4">
          <h2 className="t-seccion">Formato esperado</h2>
          <p className="mb-2.5 mt-0.5 t-meta">La primera fila son los encabezados.</p>

          <div className="table-wrap rounded-[var(--radius-field)] border border-line">
            <table className="table text-xs">
              <thead>
                <tr>
                  <th>Remitente</th><th>Valor</th><th>Referencia</th>
                  <th>Fecha</th><th>Hora</th><th>Ruta</th><th>Estado</th>
                </tr>
              </thead>
              <tbody>
                <tr className="text-muted">
                  <td>Juan Pérez</td><td className="nums">50000</td><td className="font-mono">M01234567</td>
                  <td>20 de junio 2026</td><td className="nums">12:32</td><td className="nums">3</td><td>Sin confirmar</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="hint">
            Es el mismo formato que genera <span className="font-semibold text-content">Exportar Excel</span>:
            puedes exportar, editar y volver a importar.
          </p>
        </div>
      </Card>
    </div>
  );
}
