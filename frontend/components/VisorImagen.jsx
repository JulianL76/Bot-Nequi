/**
 * Visor de comprobantes.
 *
 * Se abre desde cualquier parte con `abrirImagen(src, pie)` — no hace falta
 * pasar props por media app.
 *
 * Soporta lo que hace falta para revisar comprobantes en campo: rueda, pellizco
 * con dos dedos, doble toque, arrastre y teclado (+ − 0 Esc).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Minus, Plus, X } from 'lucide-react';

const MAX = 8;
const MIN = 1;

let abrir = () => {};
/** API global: cualquier componente puede abrir el visor. */
export function abrirImagen(src, pie) { abrir(src, pie); }

export function VisorImagen() {
  const [estado, setEstado] = useState(null);   // { src, pie } | null
  const [escala, setEscala] = useState(1);
  const desplazamiento = useRef({ x: 0, y: 0 });
  const img = useRef(null);
  const punteros = useRef(new Map());
  const arrastre = useRef({ activo: false, movido: false, x0: 0, y0: 0, bx: 0, by: 0, pinza: 0, escala0: 1 });

  useEffect(() => {
    abrir = (src, pie) => { setEstado({ src, pie }); reiniciar(); };
    return () => { abrir = () => {}; };
  }, []);

  const aplicar = useCallback((nuevaEscala) => {
    const e = Math.min(MAX, Math.max(MIN, nuevaEscala));
    if (e === MIN) desplazamiento.current = { x: 0, y: 0 };
    setEscala(e);
  }, []);

  const reiniciar = useCallback(() => {
    desplazamiento.current = { x: 0, y: 0 };
    setEscala(1);
    if (img.current) img.current.style.transform = '';
  }, []);

  // El desplazamiento se escribe directo en el estilo: pasar por estado de
  // React en cada movimiento del puntero haría un render por fotograma.
  const pintar = useCallback((e = escala) => {
    if (!img.current) return;
    const { x, y } = desplazamiento.current;
    img.current.style.transform = `translate(${x}px, ${y}px) scale(${e})`;
  }, [escala]);

  useEffect(() => { pintar(escala); }, [escala, pintar]);

  useEffect(() => {
    if (!estado) return;
    const alTeclado = (ev) => {
      if (ev.key === '+' || ev.key === '=') aplicar(escala * 1.4);
      if (ev.key === '-') aplicar(escala / 1.4);
      if (ev.key === '0') reiniciar();
    };
    window.addEventListener('keydown', alTeclado);
    return () => window.removeEventListener('keydown', alTeclado);
  }, [estado, escala, aplicar, reiniciar]);

  if (!estado) return null;

  const distancia = () => {
    const [a, b] = [...punteros.current.values()];
    return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
  };

  return (
    <DialogPrimitive.Root open onOpenChange={(v) => !v && setEstado(null)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 layer-viewer bg-ink-950/90 data-[state=open]:animate-[aparecer_150ms_ease-out]" />
        <DialogPrimitive.Content
          className="fixed inset-0 layer-viewer grid place-items-center p-4 focus:outline-none"
          onOpenAutoFocus={(e) => e.preventDefault()}
          // El Content ocupa toda la pantalla, así que para Radix no existe un
          // clic "fuera" y su cierre automático nunca se dispara. Se cierra
          // aquí, solo si la pulsación EMPIEZA en el fondo: con `click` el
          // navegador lo emitiría también al arrastrar la imagen y soltar sobre
          // el fondo (el target pasa a ser el ancestro común) y se cerraría
          // solo al terminar de mover una imagen ampliada.
          onPointerDown={(e) => { if (e.target === e.currentTarget) setEstado(null); }}
        >
          <DialogPrimitive.Title className="sr-only">Comprobante</DialogPrimitive.Title>

          <img
            ref={img}
            src={estado.src}
            alt={estado.pie || 'Comprobante'}
            draggable={false}
            className="max-h-[85vh] max-w-full select-none rounded-[var(--radius-card)] will-change-transform"
            style={{ cursor: escala > 1 ? 'grab' : 'zoom-in' }}
            onWheel={(e) => { e.preventDefault(); aplicar(escala * (e.deltaY < 0 ? 1.15 : 1 / 1.15)); }}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture?.(e.pointerId);
              punteros.current.set(e.pointerId, e);
              const a = arrastre.current;
              if (punteros.current.size === 2) {
                a.pinza = distancia();
                a.escala0 = escala;
                a.activo = false;
                return;
              }
              a.activo = true; a.movido = false;
              a.x0 = e.clientX; a.y0 = e.clientY;
              a.bx = desplazamiento.current.x; a.by = desplazamiento.current.y;
            }}
            onPointerMove={(e) => {
              if (!punteros.current.has(e.pointerId)) return;
              punteros.current.set(e.pointerId, e);
              const a = arrastre.current;
              if (punteros.current.size === 2 && a.pinza) {
                aplicar(a.escala0 * (distancia() / a.pinza));
                return;
              }
              if (!a.activo) return;
              const dx = e.clientX - a.x0;
              const dy = e.clientY - a.y0;
              if (Math.abs(dx) + Math.abs(dy) > 4) a.movido = true;
              if (escala > 1) {
                desplazamiento.current = { x: a.bx + dx, y: a.by + dy };
                pintar();
              }
            }}
            onPointerUp={(e) => {
              punteros.current.delete(e.pointerId);
              const a = arrastre.current;
              if (punteros.current.size < 2) a.pinza = 0;
              if (!a.activo) return;
              a.activo = false;
              // Toque o clic sin arrastre: alterna el zoom.
              if (!a.movido) { if (escala > 1) reiniciar(); else aplicar(2.5); }
            }}
          />

          {estado.pie && (
            <p className="pointer-events-none absolute inset-x-4 top-3 truncate text-xs text-white/70">{estado.pie}</p>
          )}

          <DialogPrimitive.Close
            aria-label="Cerrar"
            className="absolute right-3 top-3 grid size-8 place-items-center rounded-[var(--radius-field)] text-white/70 transition hover:bg-white/10 hover:text-white active:scale-96"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>

          <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-[var(--radius-pill)] border border-white/10 bg-ink-900/85 p-1 text-white/80">
            <button type="button" aria-label="Alejar" onClick={() => aplicar(escala / 1.4)}
                    className="grid size-7 place-items-center rounded-full transition hover:bg-white/10 active:scale-96">
              <Minus className="size-3.5" />
            </button>
            <span className="min-w-12 text-center font-mono text-[11px]">{Math.round(escala * 100)}%</span>
            <button type="button" aria-label="Acercar" onClick={() => aplicar(escala * 1.4)}
                    className="grid size-7 place-items-center rounded-full transition hover:bg-white/10 active:scale-96">
              <Plus className="size-3.5" />
            </button>
            <span className="mx-1 h-4 w-px bg-white/15" />
            <button type="button" onClick={reiniciar} className="h-7 rounded-full px-2.5 text-[11px] font-semibold transition hover:bg-white/10">
              Ajustar
            </button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
