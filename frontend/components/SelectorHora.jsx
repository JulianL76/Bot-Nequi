/**
 * Selector de hora (HH:MM en 24h, que es como se guarda la hora).
 *
 * Dos columnas desplazables en vez de un <input type="time">: el nativo
 * heredaba el mismo problema que el de fecha —invisible bajo la etiqueta, sin
 * forma fiable de abrirlo— y encima su apariencia la pinta el sistema.
 */
import { useEffect, useRef, useState } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Clock, X } from 'lucide-react';

import { cn } from '../ui/cn.js';

const HORAS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
const MINUTOS = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'));

function Columna({ titulo, valores, activo, onElegir }) {
  const lista = useRef(null);

  // Al abrir, el valor elegido debe quedar a la vista: si no, una columna de
  // 60 minutos se abre siempre en el 00 y hay que buscar a mano.
  useEffect(() => {
    const el = lista.current?.querySelector('[data-activo="true"]');
    el?.scrollIntoView({ block: 'center' });
  }, []);

  return (
    <div className="flex min-w-0 flex-col">
      <p className="t-micro px-1 pb-1 text-center">{titulo}</p>
      <div ref={lista} className="h-44 w-14 overflow-y-auto overscroll-contain">
        {valores.map((v) => (
          <button
            key={v}
            type="button"
            data-activo={v === activo}
            onClick={() => onElegir(v)}
            className={cn(
              'block w-full rounded-[var(--radius-field)] py-1 text-center text-[13px] tabular-nums',
              'transition-colors hover:bg-surface-hover',
              v === activo && 'bg-brand-600 font-semibold text-white hover:bg-brand-700',
            )}
          >
            {v}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SelectorHora({ valor, onCambio, className }) {
  const [abierto, setAbierto] = useState(false);
  const [hh = '', mm = ''] = (valor || '').split(':');

  return (
    <Popover.Root open={abierto} onOpenChange={setAbierto}>
      <Popover.Trigger
        className={cn(
          'flex h-[var(--h-control)] min-w-0 items-center gap-1.5 rounded-[var(--radius-field)]',
          'border border-line bg-surface px-2.5 text-xs font-medium',
          'transition-colors hover:border-line-strong',
          'data-[state=open]:border-brand-500 data-[state=open]:ring-2 data-[state=open]:ring-brand-500/20',
          className,
        )}
      >
        <Clock className="size-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
        <span className={cn('truncate tabular-nums', !valor && 'text-subtle')}>
          {valor || 'Hora'}
        </span>
        {valor && (
          <span
            role="button"
            tabIndex={-1}
            aria-label="Quitar filtro de hora"
            className="-mr-1 ml-0.5 grid size-4 place-items-center rounded-full text-subtle hover:bg-surface-hover hover:text-content"
            onClick={(e) => { e.stopPropagation(); onCambio(''); }}
          >
            <X className="size-3" />
          </span>
        )}
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={4}
          className={cn(
            'card layer-modal p-2 shadow-lg',
            'data-[state=open]:animate-[entrar-menu_140ms_var(--ease-out-soft)]',
            'data-[state=closed]:animate-[salir-menu_100ms_ease-in]',
          )}
        >
          <div className="flex gap-1">
            {/* Elegir solo una mitad deja la otra en 00, para que el filtro
                siempre sea una hora válida y no un valor a medias. */}
            <Columna titulo="Hora" valores={HORAS} activo={hh}
                     onElegir={(v) => onCambio(`${v}:${mm || '00'}`)} />
            <Columna titulo="Min" valores={MINUTOS} activo={mm}
                     onElegir={(v) => onCambio(`${hh || '00'}:${v}`)} />
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
