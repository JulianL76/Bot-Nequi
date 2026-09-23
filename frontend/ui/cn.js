import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Une clases y resuelve conflictos de Tailwind.
 *
 * Sin esto, `cn('p-3', 'p-4')` dejaría ambas y ganaría la que el CSS ordene,
 * no la que pasó quien usa el componente. twMerge hace que la última gane, que
 * es lo que uno espera al sobrescribir un estilo por props.
 */
export function cn(...clases) {
  return twMerge(clsx(clases));
}
