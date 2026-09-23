/**
 * Un ítem de conciliación.
 *
 * Jerarquía: antes la referencia, el monto, la fecha y el destinatario pesaban
 * casi lo mismo y la fila no decía por dónde empezar a leer. El orden real de
 * importancia al conciliar es:
 *
 *   1. **Cuánto** — el monto es lo que se compara. Va como dato (15/700).
 *   2. **Cómo salió** — el resultado, con punto de color y texto.
 *   3. **Cuál** — la referencia, que identifica pero no se "lee": mono, 13/400.
 *   4. **Contexto** — fecha, hora, destinatario, lote y ruta: metadatos (11px).
 *
 * El resultado es un ESTADO, no una categoría: por eso lleva siempre punto de
 * color **y** texto. Color solo no sirve — verde y ámbar contiguos no se
 * distinguen con visión normal por debajo del umbral, menos con daltonismo.
 */
import { Link } from '@inertiajs/react';
import { Copy, Eye, MessageSquareText, Pencil } from 'lucide-react';

import { Badge, Button, Checkbox } from '../ui/index.jsx';
import { abrirImagen } from './VisorImagen.jsx';
import { pesos } from '../lib/formato.js';
import { cn } from '../ui/cn.js';

export const RESULTADOS = {
  ok:        { tono: 'ok',    etiqueta: 'OK' },
  pendiente: { tono: 'warn',  etiqueta: 'Pendiente' },
  no_esta:   { tono: 'bad',   etiqueta: 'No está' },
  revision:  { tono: 'warn',  etiqueta: 'Revisión' },
  duplicado: { tono: 'brand', etiqueta: 'Duplicado' },
};

export function BadgeResultado({ resultado, texto }) {
  const r = RESULTADOS[resultado];
  if (!r) return <Badge>Sin resultado</Badge>;
  return <Badge tono={r.tono} punto>{texto || r.etiqueta}</Badge>;
}

export function ItemConciliacion({
  item, seleccionado, onSeleccionar, urlAjustar, acciones, className,
}) {
  return (
    <div
      id={`conc-item-${item.id}`}
      className={cn(
        'flex items-start gap-3 px-3 py-2.5 transition-colors',
        seleccionado ? 'bg-brand-50 dark:bg-brand-500/10' : 'hover:bg-surface-hover',
        className,
      )}
    >
      {onSeleccionar && (
        <Checkbox
          className="mt-1"
          checked={!!seleccionado}
          onCheckedChange={(v) => onSeleccionar(item.id, !!v)}
          aria-label={`Seleccionar ítem ${item.id}`}
        />
      )}

      <div className="min-w-0 flex-1">
        {/* Primera línea: lo que se viene a ver. */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="t-dato">{pesos(item.valor)}</span>
          <BadgeResultado resultado={item.resultado} texto={item.resultadoTexto} />
          {item.comprobante?.manual && <Badge tono="brand">Manual</Badge>}
          {item.observaciones && (
            <span title={item.observaciones} className="text-subtle" aria-label="Tiene observación">
              <MessageSquareText className="size-3.5" />
            </span>
          )}
        </div>

        {/* Segunda línea: identificador y destinatario. */}
        <p className="t-cuerpo mt-0.5 truncate">
          <span className="font-mono text-muted">{item.ref || 'sin referencia'}</span>
          {item.para && <span className="text-content"> · {item.para}</span>}
        </p>

        {/* Tercera línea: el contexto, claramente por debajo. */}
        <p className="t-meta mt-0.5 truncate">
          {[item.fecha, item.hora].filter(Boolean).join(' · ') || 'Sin fecha'}
          {item.ruta != null && ` · Ruta ${item.ruta}`}
          {' · '}
          <Link href={`/conciliar/lote/${item.loteId}/`} className="hover:text-content hover:underline">
            Lote #{item.loteId}
          </Link>
        </p>

        {item.motivoRevision && (
          <p className="t-meta mt-1 text-warn-600 dark:text-warn-400">{item.motivoRevision}</p>
        )}
        {item.aviso && <p className="t-meta mt-0.5">{item.aviso}</p>}

        {item.original && (
          <a
            href={`/conciliar/lote/${item.original.loteId}/#conc-item-${item.original.itemId}`}
            className="t-meta mt-1 inline-flex items-center gap-1 font-medium text-brand-600 hover:underline dark:text-brand-400"
          >
            <Copy className="size-3" />
            Original en conciliación #{item.original.loteId}
            {item.original.ruta ? ` · Ruta ${item.original.ruta}` : ''}
          </a>
        )}
      </div>

      {/* Acciones: aparecen al apuntar la fila en escritorio; siempre en táctil. */}
      <div className="flex shrink-0 items-center gap-0.5">
        {item.imagen && (
          <Button
            variant="ghost" size="sm" icon
            aria-label={`Ver imagen del ítem ${item.id}`}
            onClick={() => abrirImagen(item.imagen, `${item.ref || 'Sin referencia'} · ${pesos(item.valor)}`)}
          >
            <Eye />
          </Button>
        )}
        {urlAjustar && (
          <Button variant="ghost" size="sm" icon asChild className="text-brand-600 dark:text-brand-400">
            <Link href={urlAjustar} aria-label={`Ajustar ítem ${item.id}`}><Pencil /></Link>
          </Button>
        )}
        {acciones}
      </div>
    </div>
  );
}
