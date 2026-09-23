/**
 * Barra flotante de acciones en lote.
 *
 * Dos cosas que no se ven en el marcado y son la razón de que esto sea un
 * componente y no un <div> en cada pantalla:
 *
 * 1. Se queda montada hasta que termina la animación de salida. Escrito a mano
 *    como `{seleccion > 0 && <div…>}` el nodo se desmonta en el mismo
 *    fotograma, y eso hace imposible cualquier salida.
 *
 * 2. Va en un portal a <body>. `position: fixed` se ancla al viewport solo si
 *    ningún ancestro crea un bloque contenedor, y basta con que uno tenga
 *    `transform`, `translate`, `filter` o `backdrop-filter` —propios o
 *    animados— para que la barra quede pegada al contenido en vez de al borde
 *    inferior de la pantalla. Colgando de <body> no hay ancestro que valga.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

import { cn } from '../ui/cn.js';

export function BarraAcciones({ visible, ancho = '58rem', children }) {
  const [montada, setMontada] = useState(visible);
  const [saliendo, setSaliendo] = useState(false);

  useEffect(() => {
    if (visible) { setMontada(true); setSaliendo(false); }
    else if (montada) setSaliendo(true);
  }, [visible, montada]);

  if (!montada || typeof document === 'undefined') return null;

  return createPortal(
    <div
      // Se apoya justo encima de la navegación del móvil, que mide 4rem MÁS el
      // área segura del dispositivo; sin sumarla, en un iPhone la barra queda
      // por debajo de la navegación. En pantalla grande esa barra no existe.
      className={cn(
        'fixed bottom-[calc(4rem+env(safe-area-inset-bottom))] left-1/2 -translate-x-1/2 layer-bar lg:bottom-4',
        saliendo
          ? 'animate-[salir-barra_120ms_ease-in_forwards]'
          : 'animate-[entrar-barra_200ms_var(--ease-out-soft)]',
      )}
      style={{ width: `min(${ancho}, calc(100vw - 1rem))` }}
      // Los eventos de animación burbujean: sin comprobar el origen, cualquier
      // animación de un hijo desmontaría la barra a media vida.
      onAnimationEnd={(e) => {
        if (e.target !== e.currentTarget || !saliendo) return;
        setMontada(false);
        setSaliendo(false);
      }}
    >
      {children}
    </div>,
    document.body,
  );
}
