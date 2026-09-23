/**
 * Selector de fecha.
 *
 * Antes era un <input type="date"> invisible (`opacity: 0`) encima de una
 * etiqueta. Eso obliga al usuario a acertar con el icono nativo del
 * calendario, que no se ve, y en Chrome un clic en cualquier otro punto solo
 * enfoca los dígitos: el selector no llegaba a abrirse.
 *
 * Ahora el calendario es react-day-picker dentro de un popover de Radix, con
 * la apariencia del design system y en español.
 */
import { useState } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { DayPicker } from 'react-day-picker';
import { es } from 'react-day-picker/locale';
import { CalendarDays, X } from 'lucide-react';

import { cn } from '../ui/cn.js';

/** "2026-09-21" ↔ Date, sin pasar por UTC (`new Date('2026-09-21')` resta un día). */
function aFecha(iso) {
  if (!iso) return undefined;
  const [a, m, d] = iso.split('-').map(Number);
  return a && m && d ? new Date(a, m - 1, d) : undefined;
}

function aIso(fecha) {
  if (!fecha) return '';
  const p = (n) => String(n).padStart(2, '0');
  return `${fecha.getFullYear()}-${p(fecha.getMonth() + 1)}-${p(fecha.getDate())}`;
}

const LARGO = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' });

export function SelectorFecha({ valor, onCambio, className }) {
  const [abierto, setAbierto] = useState(false);
  const fecha = aFecha(valor);

  const elegir = (d) => {
    onCambio(aIso(d));
    setAbierto(false);
  };

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
        <CalendarDays className="size-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
        {/* `truncate` y no `whitespace-nowrap`: en un móvil estrecho la fecha
            larga desbordaba la fila de filtros en vez de recortarse. */}
        <span className={cn('truncate', !fecha && 'text-subtle')}>
          {fecha ? LARGO.format(fecha) : 'Fecha'}
        </span>
        {fecha && (
          // No es un <button>: anidarlo dentro del trigger sería HTML inválido.
          <span
            role="button"
            tabIndex={-1}
            aria-label="Quitar filtro de fecha"
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
          <DayPicker
            mode="single"
            locale={es}
            weekStartsOn={1}
            selected={fecha}
            defaultMonth={fecha}
            onSelect={elegir}
            showOutsideDays
            classNames={{
              root: 'text-content',
              months: 'relative',
              month_caption: 'flex h-8 items-center justify-center',
              caption_label: 't-seccion capitalize',
              nav: 'absolute inset-x-0 top-0 flex h-8 items-center justify-between',
              button_previous: 'grid size-7 place-items-center rounded-[var(--radius-field)] text-muted transition-colors hover:bg-surface-hover hover:text-content disabled:opacity-30',
              button_next: 'grid size-7 place-items-center rounded-[var(--radius-field)] text-muted transition-colors hover:bg-surface-hover hover:text-content disabled:opacity-30',
              chevron: 'size-4 fill-current',
              month_grid: 'mt-1 border-collapse',
              weekdays: '',
              weekday: 't-micro pb-1 font-bold text-subtle',
              week: '',
              day: 'p-0',
              day_button: cn(
                'grid size-8 place-items-center rounded-[var(--radius-field)] text-[13px] tabular-nums',
                'transition-colors hover:bg-surface-hover disabled:opacity-30',
              ),
              selected: '[&_button]:bg-brand-600 [&_button]:font-semibold [&_button]:text-white [&_button]:hover:bg-brand-700',
              today: '[&_button]:font-bold [&_button]:text-brand-600 dark:[&_button]:text-brand-400',
              outside: '[&_button]:text-subtle [&_button]:opacity-50',
            }}
          />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
