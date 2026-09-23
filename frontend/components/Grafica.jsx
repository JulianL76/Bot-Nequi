/**
 * Gráficas en SVG.
 *
 * Por qué a mano y no con una librería: las dos formas que necesita esta app
 * —una serie temporal y un ranking de cinco barras— salen en ~5 kB de SVG,
 * frente a los 287 kB (comprimidos) que pesaba ApexCharts. Y el dashboard es
 * la primera pantalla tras entrar, así que ese peso se paga siempre.
 *
 * Decisiones de diseño, no de gusto:
 *
 * · **Un solo tono.** Son magnitudes, no identidades que haya que distinguir.
 *   Con una sola serie no hace falta leyenda: el título la nombra.
 * · **Los estados no se grafican por color.** Verde y ámbar contiguos no se
 *   separan bien ni con visión normal (ΔE 14.4, bajo el umbral de 15), así que
 *   la distribución por estado va como fichas con etiqueta.
 * · **Un solo eje.** Montos y conteos nunca comparten gráfica.
 * · **Marcas finas, rejilla discreta**, y etiquetas directas en vez de un
 *   número sobre cada punto.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { numero, pesosCorto } from '../lib/formato.js';
import { cn } from '../ui/cn.js';

/** Ancho real del contenedor: dibujar en píxeles evita deformar los trazos. */
function useAncho() {
  const ref = useRef(null);
  const [ancho, setAncho] = useState(0);

  useLayoutEffect(() => {
    if (!ref.current) return undefined;
    const obs = new ResizeObserver(([e]) => setAncho(e.contentRect.width));
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  return [ref, ancho];
}

/** El color de marca cambia con el tema; ambos pasos están validados. */
function useOscuro() {
  const [oscuro, setOscuro] = useState(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('dark'),
  );
  useEffect(() => {
    const obs = new MutationObserver(() => setOscuro(document.documentElement.classList.contains('dark')));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => obs.disconnect();
  }, []);
  return oscuro;
}

const MARCA = { claro: '#3b45e0', oscuro: '#5c63f2' };

function Tooltip({ x, y, ancho, children }) {
  // Se voltea cerca del borde derecho para no salirse del contenedor.
  const derecha = x > ancho - 120;
  return (
    <div
      className="pointer-events-none absolute z-10 whitespace-nowrap rounded-[var(--radius-field)] border border-line bg-surface-raised px-2 py-1 text-[11px] shadow-lg"
      style={{ left: derecha ? undefined : x + 10, right: derecha ? ancho - x + 10 : undefined, top: y }}
    >
      {children}
    </div>
  );
}

/* ============================================================================
   Serie temporal (área + línea)
   ========================================================================== */
export function GraficaArea({ etiquetas, valores, nombre, moneda = true, alto = 200 }) {
  const [ref, ancho] = useAncho();
  const oscuro = useOscuro();
  const [activo, setActivo] = useState(null);

  const color = oscuro ? MARCA.oscuro : MARCA.claro;
  const formato = moneda ? pesosCorto : numero;

  const M = { arriba: 8, derecha: 8, abajo: 20, izquierda: 44 };
  const w = Math.max(ancho, 200);
  const anchoPlot = w - M.izquierda - M.derecha;
  const altoPlot = alto - M.arriba - M.abajo;

  const max = Math.max(...valores, 1);
  const x = (i) => M.izquierda + (valores.length > 1 ? (i / (valores.length - 1)) * anchoPlot : anchoPlot / 2);
  const y = (v) => M.arriba + altoPlot - (v / max) * altoPlot;

  const linea = valores.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const area = `${linea} L${x(valores.length - 1).toFixed(1)},${M.arriba + altoPlot} L${x(0).toFixed(1)},${M.arriba + altoPlot} Z`;

  // Tres marcas en el eje vertical: suficientes para leer la escala.
  const marcasY = [0, max / 2, max];

  const alMover = (e) => {
    const caja = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - caja.left;
    const i = Math.round(((px - M.izquierda) / anchoPlot) * (valores.length - 1));
    setActivo(i >= 0 && i < valores.length ? i : null);
  };

  return (
    <div ref={ref} className="relative" onMouseLeave={() => setActivo(null)}>
      {ancho > 0 && (
        <svg
          width={w}
          height={alto}
          onMouseMove={alMover}
          role="img"
          aria-label={`${nombre}: evolución de ${etiquetas.length} días`}
        >
          {/* Rejilla: recesiva, solo horizontal. */}
          {marcasY.map((v) => (
            <g key={v}>
              <line
                x1={M.izquierda} x2={w - M.derecha} y1={y(v)} y2={y(v)}
                stroke="var(--line)" strokeWidth="1"
              />
              <text
                x={M.izquierda - 6} y={y(v) + 3} textAnchor="end"
                className="nums fill-[var(--content-subtle)] text-[10px]"
              >
                {formato(v)}
              </text>
            </g>
          ))}

          <path d={area} fill={color} opacity={oscuro ? 0.16 : 0.1} />
          <path d={linea} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

          {/* Primera y última fecha: sitúan la serie sin saturar el eje. */}
          <text x={M.izquierda} y={alto - 5} className="fill-[var(--content-subtle)] text-[10px]">
            {etiquetas[0]?.slice(5)}
          </text>
          <text x={w - M.derecha} y={alto - 5} textAnchor="end" className="fill-[var(--content-subtle)] text-[10px]">
            {etiquetas.at(-1)?.slice(5)}
          </text>

          {activo != null && (
            <g>
              <line
                x1={x(activo)} x2={x(activo)} y1={M.arriba} y2={M.arriba + altoPlot}
                stroke="var(--line-strong)" strokeWidth="1" strokeDasharray="3 3"
              />
              {/* Anillo de 2px del color de la superficie: separa el punto del área. */}
              <circle cx={x(activo)} cy={y(valores[activo])} r="4.5" fill={color} stroke="var(--surface)" strokeWidth="2" />
            </g>
          )}
        </svg>
      )}

      {activo != null && (
        <Tooltip x={x(activo)} y={Math.max(y(valores[activo]) - 28, 0)} ancho={w}>
          <span className="block text-subtle">{etiquetas[activo]}</span>
          <span className="nums block font-semibold">{formato(valores[activo])}</span>
        </Tooltip>
      )}
    </div>
  );
}

/* ============================================================================
   Ranking (barras horizontales)
   ========================================================================== */
export function GraficaBarras({ etiquetas, valores, nombre, moneda = true, alto = 200 }) {
  const [ref, ancho] = useAncho();
  const oscuro = useOscuro();
  const [activo, setActivo] = useState(null);

  const color = oscuro ? MARCA.oscuro : MARCA.claro;
  const formato = moneda ? pesosCorto : numero;
  const max = Math.max(...valores, 1);

  return (
    <div ref={ref} className="space-y-1.5">
      {etiquetas.map((etiqueta, i) => (
        <div
          key={etiqueta + i}
          className="group"
          onMouseEnter={() => setActivo(i)}
          onMouseLeave={() => setActivo(null)}
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="t-meta truncate" title={etiqueta}>{etiqueta}</span>
            {/* Etiqueta directa: con cinco barras no hace falta eje de valores. */}
            <span className="t-seccion nums shrink-0">{formato(valores[i])}</span>
          </div>
          <div className="mt-0.5 h-2 w-full overflow-hidden rounded-full bg-surface-inset">
            <div
              className={cn('h-full rounded-full transition-[width,opacity] duration-500 ease-out',
                activo != null && activo !== i && 'opacity-50')}
              style={{ width: `${(valores[i] / max) * 100}%`, background: color }}
              role="img"
              aria-label={`${etiqueta}: ${formato(valores[i])} de ${nombre}`}
            />
          </div>
        </div>
      ))}
      {ancho === 0 && <div className="skeleton" style={{ height: alto }} />}
    </div>
  );
}
