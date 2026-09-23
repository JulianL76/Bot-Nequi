/**
 * Kit de interfaz.
 *
 * Los estilos siguen viniendo del design system en CSS (`.btn-primary`,
 * `.card`, `.field`…): estos componentes no reinventan la apariencia, le ponen
 * una API tipada encima y resuelven lo que CSS no puede — foco atrapado en los
 * diálogos, estados de carga, semántica ARIA.
 *
 * Los primitivos accesibles son de Radix. Base UI sería la opción preferida
 * según la guía, pero sigue en release candidate y esto es una app en uso.
 */
import { Children, forwardRef, isValidElement } from 'react';
import { Slot } from '@radix-ui/react-slot';
import * as SwitchPrimitive from '@radix-ui/react-switch';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import * as SelectPrimitive from '@radix-ui/react-select';
import * as SeparatorPrimitive from '@radix-ui/react-separator';
import { Check, ChevronDown, Minus } from 'lucide-react';
import { cn } from './cn.js';

/* ============================================================================
   Botón
   ========================================================================== */
const VARIANTES = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
  success: 'btn-success',
};

export const Button = forwardRef(function Button(
  { variant = 'secondary', size, icon = false, cargando = false, asChild = false,
    className, children, ...props },
  ref,
) {
  const Comp = asChild ? Slot : 'button';
  return (
    <Comp
      ref={ref}
      // `cargando` no deshabilita: un botón deshabilitado no envía su
      // name/value, y así es como viajan las acciones en lote.
      aria-busy={cargando || undefined}
      className={cn(
        VARIANTES[variant] || VARIANTES.secondary,
        size === 'sm' && 'btn-sm',
        size === 'lg' && 'btn-lg',
        icon && 'btn-icon',
        cargando && 'btn-cargando',
        className,
      )}
      {...props}
    >
      {children}
    </Comp>
  );
});

/* ============================================================================
   Superficies
   ========================================================================== */
export function Card({ className, children, ...props }) {
  return <div className={cn('card', className)} {...props}>{children}</div>;
}

export function CardHeader({ className, children, ...props }) {
  return <div className={cn('card-header', className)} {...props}>{children}</div>;
}

export function CardTitle({ className, children, ...props }) {
  return <h2 className={cn('card-title', className)} {...props}>{children}</h2>;
}

export function CardBody({ className, children, ...props }) {
  return <div className={cn('card-pad', className)} {...props}>{children}</div>;
}

/* ============================================================================
   Estado
   ========================================================================== */
const TONOS = {
  neutral: 'badge-neutral',
  brand: 'badge-brand',
  ok: 'badge-ok',
  warn: 'badge-warn',
  bad: 'badge-bad',
};

export function Badge({ tono = 'neutral', punto = false, className, children, ...props }) {
  const colorPunto = { ok: 'bg-ok-500', warn: 'bg-warn-500', bad: 'bg-bad-500', brand: 'bg-brand-500' }[tono];
  return (
    <span className={cn(TONOS[tono] || TONOS.neutral, className)} {...props}>
      {punto && <span className={cn('dot', colorPunto)} />}
      {children}
    </span>
  );
}

export function Dot({ className }) {
  return <span className={cn('dot', className)} />;
}

/* ============================================================================
   Formularios
   ========================================================================== */
export const Input = forwardRef(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn('field', className)} {...props} />;
});

/* ----------------------------------------------------------------------------
   Select

   Va sobre Radix y no sobre <select> nativo porque la lista desplegable de un
   select nativo la pinta el sistema operativo: no hereda el tema oscuro, ni la
   tipografía, ni los radios. Es lo único de la interfaz que se veía prestado.

   La API se mantiene: recibe <option> como hijos y avisa con
   onChange({ target: { value } }), igual que el nativo. Así los sitios que ya
   lo usaban no cambian.
   -------------------------------------------------------------------------- */

// Radix rechaza un Item con value="" (reserva la cadena vacía para "sin
// valor"), pero aquí "" es una opción legítima en media app —"Sin ruta",
// "Sin tipo", "Orden original"—. Se traduce a un centinela de puertas adentro
// y se devuelve como "" al exterior, que nunca llega a verlo.
const VACIO = '__vacio__';
const aRadix = (v) => (v === '' ? VACIO : v);
const aFuera = (v) => (v === VACIO ? '' : v);

/** Aplana los hijos a {valor, etiqueta, deshabilitada}, admitiendo fragmentos. */
function leerOpciones(hijos) {
  const salida = [];
  const recorrer = (nodos) => Children.forEach(nodos, (n) => {
    if (!isValidElement(n)) return;
    if (n.type === 'option') {
      salida.push({
        valor: n.props.value == null ? '' : String(n.props.value),
        etiqueta: n.props.children,
        deshabilitada: !!n.props.disabled,
      });
    } else if (n.props?.children) {
      recorrer(n.props.children);
    }
  });
  recorrer(hijos);
  return salida;
}

export const Select = forwardRef(function Select(
  { className, children, value, onChange, name, disabled, ...props }, ref,
) {
  const opciones = leerOpciones(children);
  // El nativo siempre entrega cadenas; se normaliza para que comparar un
  // value numérico (el id de una ruta) con su <option> no falle.
  const actual = value == null ? '' : String(value);
  const elegida = opciones.find((o) => o.valor === actual);

  return (
    <>
      <SelectPrimitive.Root
        value={aRadix(actual)}
        onValueChange={(v) => onChange?.({ target: { value: aFuera(v) } })}
        disabled={disabled}
      >
        <SelectPrimitive.Trigger
          ref={ref}
          className={cn('field flex items-center justify-between gap-2 pr-2 text-left', className)}
          {...props}
        >
          <span className="truncate">{elegida ? elegida.etiqueta : ''}</span>
          <SelectPrimitive.Icon asChild>
            <ChevronDown className="size-3.5 shrink-0 text-muted" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>

        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            position="popper"
            sideOffset={4}
            className={cn(
              'card layer-modal overflow-hidden p-1 shadow-lg',
              'min-w-[var(--radix-select-trigger-width)] max-h-[min(18rem,var(--radix-select-content-available-height))]',
              'data-[state=open]:animate-[entrar-menu_140ms_var(--ease-out-soft)]',
              'data-[state=closed]:animate-[salir-menu_100ms_ease-in]',
            )}
          >
            <SelectPrimitive.Viewport>
              {opciones.map((o) => (
                <SelectPrimitive.Item
                  key={o.valor}
                  value={aRadix(o.valor)}
                  disabled={o.deshabilitada}
                  className={cn(
                    'relative flex cursor-pointer select-none items-center gap-2 rounded-[var(--radius-field)]',
                    'py-1.5 pl-2 pr-7 t-cuerpo outline-none',
                    'data-[highlighted]:bg-surface-hover data-[state=checked]:font-semibold',
                    'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                  )}
                >
                  <SelectPrimitive.ItemText>{o.etiqueta}</SelectPrimitive.ItemText>
                  <SelectPrimitive.ItemIndicator className="absolute right-2 text-brand-600 dark:text-brand-400">
                    <Check className="size-3.5" />
                  </SelectPrimitive.ItemIndicator>
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.Viewport>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>

      {/* El trigger de Radix es un <button>: no viaja en un envío nativo. Los
          formularios que postean de verdad (conciliar) necesitan el campo. */}
      {name && <input type="hidden" name={name} value={actual} />}
    </>
  );
});

export function Label({ className, children, ...props }) {
  return <label className={cn('label', className)} {...props}>{children}</label>;
}

export function Hint({ className, children }) {
  return <p className={cn('hint', className)}>{children}</p>;
}

export function ErrorText({ className, children }) {
  return children ? <p className={cn('error-text', className)}>{children}</p> : null;
}

/** Campo completo: etiqueta, control y error, con el `id` ya enlazado. */
export function Campo({ label, id, error, hint, children, className }) {
  return (
    <div className={className}>
      {label && <Label htmlFor={id}>{label}</Label>}
      {children}
      {hint && <Hint>{hint}</Hint>}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

/* ============================================================================
   Interruptor y casilla (Radix: teclado y ARIA resueltos)
   ========================================================================== */
export function Switch({ className, tono = 'brand', ...props }) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        'relative h-5 w-9 shrink-0 cursor-pointer rounded-full border-0 transition-colors duration-[var(--t-fast)]',
        'data-[state=unchecked]:bg-line-strong',
        tono === 'ok' ? 'data-[state=checked]:bg-ok-500' : 'data-[state=checked]:bg-brand-600',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          'block size-3.5 translate-x-[3px] rounded-full bg-white shadow-sm',
          'transition-transform duration-[var(--t-normal)] ease-[var(--ease-spring)]',
          'data-[state=checked]:translate-x-[19px]',
        )}
      />
    </SwitchPrimitive.Root>
  );
}

export function Checkbox({ className, indeterminate = false, ...props }) {
  return (
    <CheckboxPrimitive.Root
      checked={indeterminate ? 'indeterminate' : props.checked}
      className={cn(
        'grid size-4 shrink-0 place-items-center rounded-[4px] border border-line-strong bg-surface',
        'transition-colors duration-[var(--t-fast)] cursor-pointer',
        'data-[state=checked]:border-brand-600 data-[state=checked]:bg-brand-600',
        'data-[state=indeterminate]:border-brand-600 data-[state=indeterminate]:bg-brand-600',
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator className="text-white">
        {indeterminate ? <Minus className="size-3" strokeWidth={3} /> : <Check className="size-3" strokeWidth={3} />}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export function Separator({ className, ...props }) {
  return <SeparatorPrimitive.Root className={cn('h-px bg-line', className)} {...props} />;
}

/* ============================================================================
   Vacíos y carga
   ========================================================================== */
export function EmptyState({ icon: Icon, titulo, descripcion, children, className }) {
  return (
    <div className={cn('empty-state', className)}>
      {Icon && <Icon className="mb-3 size-9 text-subtle" strokeWidth={1.5} />}
      <p className="t-seccion">{titulo}</p>
      {descripcion && <p className="t-meta mt-1 max-w-sm">{descripcion}</p>}
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}

export function Skeleton({ className }) {
  return <div className={cn('skeleton', className)} />;
}

/** Barra de progreso. Anima scaleX, no width: la escala la compone la GPU. */
export function Progress({ valor = 0, activo = false, className }) {
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(valor)}
      className={cn('h-2 w-full overflow-hidden rounded-full bg-surface-inset', className)}
    >
      <div
        // `activo` solo mientras el proceso corre de verdad: el brillo es lo que
        // distingue "avanzando despacio" de "colgado".
        className={cn(
          'h-full w-full origin-left rounded-full bg-brand-600 transition-transform duration-500 ease-out',
          activo && 'barra-viva',
        )}
        style={{ transform: `scaleX(${Math.min(100, Math.max(0, valor)) / 100})` }}
      />
    </div>
  );
}
