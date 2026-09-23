/**
 * Ficha de cifra.
 *
 * Para un puñado de números la forma correcta NO es una gráfica: es una cifra
 * grande con su etiqueta. Y el color aquí significa estado, no decoración —
 * por eso `tono` solo acepta los estados reservados y siempre va acompañado de
 * texto, nunca color a secas.
 */
import { cn } from '../ui/cn.js';

const TONOS = {
  neutro: { valor: 'text-content', punto: null },
  ok:     { valor: 'text-ok-600 dark:text-ok-400',   punto: 'bg-ok-500' },
  aviso:  { valor: 'text-warn-600 dark:text-warn-400', punto: 'bg-warn-500' },
  grave:  { valor: 'text-bad-600 dark:text-bad-400',  punto: 'bg-bad-500' },
  marca:  { valor: 'text-brand-600 dark:text-brand-400', punto: 'bg-brand-500' },
};

export function Estadistica({ etiqueta, valor, detalle, tono = 'neutro', icon: Icon, className }) {
  const t = TONOS[tono] || TONOS.neutro;
  return (
    <div className={cn('card card-pad', className)}>
      <div className="flex items-center gap-1.5">
        {t.punto && <span className={cn('dot', t.punto)} />}
        <p className="t-micro">{etiqueta}</p>
        {Icon && <Icon className="ml-auto size-3.5 text-subtle" />}
      </div>
      <p className={cn('t-dato mt-1 text-lg', t.valor)}>{valor}</p>
      {detalle && <p className="t-meta mt-0.5 truncate">{detalle}</p>}
    </div>
  );
}

/** Fila de fichas: una rejilla que no se rompe en móvil. */
export function FilaEstadisticas({ children, className }) {
  return (
    <div className={cn('rise-lista grid grid-cols-2 gap-2 md:grid-cols-4', className)}>{children}</div>
  );
}
