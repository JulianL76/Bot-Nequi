import { Link, usePage } from '@inertiajs/react';
import { CircleCheck, Eye, Hourglass, ListChecks } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Badge, Button, Card, CardHeader, CardTitle, EmptyState } from '../../ui/index.jsx';
import { abrirImagen } from '../../components/VisorImagen.jsx';
import { pesos, plural } from '../../lib/formato.js';

export default function Pendientes({ comprobantes, conciliaciones }) {
  const { urls } = usePage().props;
  const nada = !comprobantes.length && !conciliaciones.length;

  if (nada) {
    return (
      <>
        <Cabecera titulo="Pendientes" subtitulo="Lo que espera una decisión tuya." />
        <Card>
          <EmptyState
            icon={CircleCheck}
            titulo="No hay nada pendiente"
            descripcion="Todos los comprobantes están confirmados y no quedan conciliaciones por revisar."
          >
            <Button size="sm" asChild><Link href={urls.comprobantes}>Ver comprobantes</Link></Button>
          </EmptyState>
        </Card>
      </>
    );
  }

  return (
    <>
      <Cabecera
        titulo="Pendientes"
        subtitulo={`${comprobantes.length} sin confirmar · ${conciliaciones.length} ${plural(conciliaciones.length, 'conciliación', 'conciliaciones')} por revisar`}
      />

      {/* `[&>*]:min-w-0`: una celda de grid tiene `min-width: auto`, así que no
          puede encoger por debajo del ancho mínimo de su contenido. Las líneas
          con `truncate` son `white-space: nowrap`, y su mínimo es la frase
          entera: en el móvil la tarjeta medía 406px sobre un viewport de 360 y
          los montos quedaban cortados fuera de la pantalla. */}
      <div className="grid gap-3 [&>*]:min-w-0 lg:grid-cols-2">
        {/* ---------- Comprobantes sin confirmar ---------- */}
        <Card>
          <CardHeader>
            <Hourglass className="size-4 text-warn-600 dark:text-warn-400" />
            <CardTitle>Sin confirmar</CardTitle>
            <Badge tono="warn" className="ml-auto">{comprobantes.length}</Badge>
          </CardHeader>

          {comprobantes.length ? (
            <ul className="max-h-[32rem] divide-y divide-line overflow-y-auto">
              {comprobantes.map((c) => (
                <li key={c.id} className="flex items-center gap-2 px-3 py-2 transition-colors hover:bg-surface-hover">
                  <Link href={`${urls.comprobantes}${c.id}/editar/`} className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{c.de}</span>
                    <span className="block truncate t-meta text-subtle">
                      {c.ref || '—'}{c.fecha ? ` · ${c.fecha}` : ''}{c.hora ? ` ${c.hora}` : ''}
                    </span>
                  </Link>
                  <span className="nums shrink-0 font-bold">{pesos(c.valor)}</span>
                  {c.imagen && (
                    <Button
                      variant="ghost" size="sm" icon
                      aria-label={`Ver comprobante de ${c.de}`}
                      onClick={() => abrirImagen(c.imagen, `${c.de} · ${pesos(c.valor)}`)}
                    >
                      <Eye />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={CircleCheck} titulo="Todo confirmado" />
          )}
        </Card>

        {/* ---------- Conciliaciones por revisar ---------- */}
        <Card>
          <CardHeader>
            <ListChecks className="size-4 text-brand-600 dark:text-brand-400" />
            <CardTitle>Conciliaciones por revisar</CardTitle>
            <Badge tono="brand" className="ml-auto">{conciliaciones.length}</Badge>
          </CardHeader>

          {conciliaciones.length ? (
            <ul className="max-h-[32rem] divide-y divide-line overflow-y-auto">
              {conciliaciones.map((k) => (
                <li key={k.id}>
                  <Link
                    href={`${urls.conciliaciones.replace('historial/', '')}lote/${k.loteId}/#conc-item-${k.id}`}
                    className="flex items-center gap-2 px-3 py-2 transition-colors hover:bg-surface-hover"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{k.de || 'Sin comprobante'}</span>
                      <span className="block truncate t-meta text-subtle">
                        {k.ref || '—'}{k.ruta ? ` · Ruta ${k.ruta}` : ''}
                      </span>
                    </span>
                    {k.valor != null && <span className="nums shrink-0 font-bold">{pesos(k.valor)}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={CircleCheck} titulo="Nada por revisar" />
          )}
        </Card>
      </div>
    </>
  );
}
