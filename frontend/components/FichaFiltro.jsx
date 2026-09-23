/**
 * Ficha de cifra que además filtra.
 *
 * Antes había dos filas diciendo lo mismo: siete fichas con los conteos y
 * siete chips con esos mismos conteos. Ahora la ficha ES el filtro.
 *
 * La cifra se calcula sobre el ALCANCE (fechas y rutas), nunca sobre el
 * resultado elegido: si se calculara sobre lo ya filtrado, al elegir "No está"
 * el resto quedaría en cero y el total valdría lo mismo que esa porción. Los
 * números dejarían de ser una referencia.
 */
import { cn } from '../ui/cn.js';

const TONOS = {
  neutro: { valor: 'text-content',                      punto: null,          activo: 'border-ink-400 bg-surface-inset' },
  ok:     { valor: 'text-ok-600 dark:text-ok-400',      punto: 'bg-ok-500',   activo: 'border-ok-500 bg-ok-100 dark:bg-ok-500/10' },
  aviso:  { valor: 'text-warn-600 dark:text-warn-400',  punto: 'bg-warn-500', activo: 'border-warn-500 bg-warn-100 dark:bg-warn-500/10' },
  grave:  { valor: 'text-bad-600 dark:text-bad-400',    punto: 'bg-bad-500',  activo: 'border-bad-500 bg-bad-100 dark:bg-bad-500/10' },
  marca:  { valor: 'text-brand-600 dark:text-brand-400', punto: 'bg-brand-500', activo: 'border-brand-500 bg-brand-50 dark:bg-brand-500/10' },
};

export function FichaFiltro({ etiqueta, valor, tono = 'neutro', activo, onClick, total }) {
  const t = TONOS[tono] || TONOS.neutro;
  // Proporción sobre el alcance: sitúa la cifra sin necesidad de otra gráfica.
  const pct = total > 0 && valor > 0 ? Math.round((valor / total) * 100) : null;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activo}
      className={cn(
        'card card-pad text-left transition-[border-color,background-color] duration-[var(--t-fast)]',
        'hover:border-line-strong active:scale-[0.99]',
        activo && t.activo,
      )}
    >
      <span className="flex items-center gap-1.5">
        {t.punto && <span className={cn('dot', t.punto)} />}
        <span className="t-micro">{etiqueta}</span>
      </span>

      {/* Cifra grande: figuras proporcionales, no tabulares — tabular-nums da a
          cada dígito el ancho de un cero y a este tamaño se ve suelto. */}
      <span className={cn('t-dato mt-0.5 block text-lg', t.valor)}>{valor}</span>

      <span className="t-meta block h-4 text-subtle">
        {pct != null && pct < 100 ? `${pct}% del total` : ''}
      </span>
    </button>
  );
}
