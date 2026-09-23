/** Formatos compartidos por toda la app. Una sola definición, un solo criterio. */

const PESOS = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 2,
});

const NUMERO = new Intl.NumberFormat('es-CO');

export function pesos(valor) {
  const n = Number(valor);
  return Number.isFinite(n) ? PESOS.format(n) : '—';
}

/** Igual que `pesos` pero sin decimales: para cifras grandes de tablero. */
export function pesosCorto(valor) {
  const n = Number(valor);
  if (!Number.isFinite(n)) return '—';
  return '$' + NUMERO.format(Math.round(n));
}

export function numero(valor) {
  const n = Number(valor);
  return Number.isFinite(n) ? NUMERO.format(n) : '—';
}

export function fechaHora(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString('es-CO', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

/** "hace 5 minutos", "ayer"… para listas donde la hora exacta estorba. */
export function hace(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const seg = (Date.now() - d.getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat('es-CO', { numeric: 'auto' });
  const tramos = [
    [60, 'second', 1],
    [3600, 'minute', 60],
    [86400, 'hour', 3600],
    [604800, 'day', 86400],
    [2629800, 'week', 604800],
    [31557600, 'month', 2629800],
    [Infinity, 'year', 31557600],
  ];
  for (const [limite, unidad, divisor] of tramos) {
    if (seg < limite) return rtf.format(-Math.round(seg / divisor), unidad);
  }
  return '';
}

export function plural(n, singular, pluralForma) {
  return Number(n) === 1 ? singular : (pluralForma ?? singular + 's');
}
