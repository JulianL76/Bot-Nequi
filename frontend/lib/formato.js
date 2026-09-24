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

/** Clave de agrupación por día: "2026-09-23" en hora LOCAL.
 *  Con `toISOString()` un lote de las 19:00 en Colombia caería en el día
 *  siguiente, porque ese método pasa por UTC. */
export function claveDia(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Encabezado de un día: "Hoy", "Ayer" o "martes, 23 de septiembre de 2026". */
export function diaLargo(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const hoy = claveDia(new Date().toISOString());
  const ayer = claveDia(new Date(Date.now() - 86400000).toISOString());
  const clave = claveDia(iso);
  if (clave === hoy) return 'Hoy';
  if (clave === ayer) return 'Ayer';
  const txt = d.toLocaleDateString('es-CO', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
  return txt.charAt(0).toUpperCase() + txt.slice(1);
}

/** Solo la hora, para cuando el día ya lo dice el encabezado del grupo. */
export function soloHora(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', hour12: false });
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
