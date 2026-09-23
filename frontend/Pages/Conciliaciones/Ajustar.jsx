import { Link, useForm } from '@inertiajs/react';
import { ChevronLeft, Eye, Image, Save } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Button, Card, Campo, EmptyState, Input, Select } from '../../ui/index.jsx';
import { BadgeResultado } from '../../components/ItemConciliacion.jsx';
import { abrirImagen } from '../../components/VisorImagen.jsx';
import { pesos } from '../../lib/formato.js';

export default function Ajustar({ item, tipos, filtros }) {
  const { data, setData, post, processing, errors } = useForm({
    de: item.de || '',
    para: item.para || '',
    num: item.num || '',
    tipo: item.tipoValor || '',
    ref: item.ref || '',
    valor: String(item.valor ?? ''),
    fecha: item.fecha || '',
    hora: item.hora || '',
    observaciones: item.observaciones || '',
    r: filtros.r,
    sort: filtros.sort,
  });

  const volver = `/conciliar/lote/${item.loteId}/?r=${filtros.r}&sort=${filtros.sort}`;

  return (
    <div className="max-w-5xl">
      <Cabecera
        titulo="Ajustar datos leídos"
        subtitulo={`Ítem #${item.id} de la conciliación #${item.loteId}`}
      >
        <Button size="sm" asChild>
          <Link href={volver}><ChevronLeft /><span className="hidden sm:inline">Volver</span></Link>
        </Button>
      </Cabecera>

      <div className="mb-3">
        <BadgeResultado resultado={item.resultado} texto={item.resultadoTexto} />
      </div>

      <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card className="overflow-hidden lg:sticky lg:top-14">
          {item.imagen ? (
            <button
              type="button"
              className="group relative block w-full"
              onClick={() => abrirImagen(item.imagen, `${item.ref || 'Sin referencia'} · ${pesos(item.valor)}`)}
            >
              <img src={item.imagen} alt="Captura de la conciliación" className="max-h-[26rem] w-full bg-surface-inset object-contain" />
              <span className="absolute inset-0 grid place-items-center bg-ink-950/0 transition-colors group-hover:bg-ink-950/35">
                <span className="flex items-center gap-2 rounded-[var(--radius-field)] bg-surface-raised px-2.5 py-1.5 t-seccion opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
                  <Eye className="size-3.5" />Ampliar
                </span>
              </span>
            </button>
          ) : (
            <EmptyState icon={Image} titulo="Sin imagen" />
          )}
        </Card>

        <Card>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              post(`/conciliar/item/${item.id}/ajustar/`);
            }}
          >
            <div className="card-pad space-y-3">
              <p className="t-meta">
                Corrige lo que la IA leyó mal. Al guardar, pulsa <span className="font-semibold text-content">Reprocesar</span> en
                el detalle para volver a buscar el comprobante con los datos nuevos.
              </p>

              <div className="grid gap-3 sm:grid-cols-2">
                <Campo label="Referencia" id="a-ref" error={errors.ref}>
                  <Input id="a-ref" className="font-mono" value={data.ref} onChange={(e) => setData('ref', e.target.value)} />
                </Campo>
                <Campo label="Valor" id="a-valor" error={errors.valor}>
                  <Input id="a-valor" inputMode="decimal" className="font-semibold"
                         value={data.valor} onChange={(e) => setData('valor', e.target.value)} />
                </Campo>
                <Campo label="Fecha" id="a-fecha" error={errors.fecha}>
                  <Input id="a-fecha" value={data.fecha} onChange={(e) => setData('fecha', e.target.value)} />
                </Campo>
                <Campo label="Hora" id="a-hora" error={errors.hora}>
                  <Input id="a-hora" value={data.hora} onChange={(e) => setData('hora', e.target.value)} />
                </Campo>
                <Campo label="Remitente" id="a-de" error={errors.de}>
                  <Input id="a-de" value={data.de} onChange={(e) => setData('de', e.target.value)} />
                </Campo>
                <Campo label="Destinatario / titular" id="a-para" error={errors.para}>
                  <Input id="a-para" value={data.para} onChange={(e) => setData('para', e.target.value)} />
                </Campo>
                <Campo label="Número destino" id="a-num" error={errors.num}>
                  <Input id="a-num" className="font-mono" value={data.num} onChange={(e) => setData('num', e.target.value)} />
                </Campo>
                <Campo label="Tipo" id="a-tipo" error={errors.tipo}>
                  <Select id="a-tipo" value={data.tipo} onChange={(e) => setData('tipo', e.target.value)}>
                    <option value="">Sin tipo</option>
                    {tipos.map((t) => <option key={t.valor} value={t.valor}>{t.etiqueta}</option>)}
                  </Select>
                </Campo>
              </div>

              <Campo label="Observaciones" id="a-obs" error={errors.observaciones}
                     hint="Nota libre; queda visible en el detalle y en el panel.">
                <textarea
                  id="a-obs" className="field min-h-20"
                  value={data.observaciones}
                  onChange={(e) => setData('observaciones', e.target.value)}
                />
              </Campo>
            </div>

            <div className="flex flex-wrap gap-2 rounded-b-[var(--radius-card)] border-t border-line bg-surface-inset/60 px-3 py-3 md:px-4">
              <Button type="submit" variant="primary" cargando={processing}><Save />Guardar ajustes</Button>
              <Button type="button" variant="ghost" asChild><Link href={volver}>Cancelar</Link></Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
