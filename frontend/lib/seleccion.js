/**
 * Selección que sobrevive a la paginación.
 *
 * Marcar 30 comprobantes en la página 1, pasar a la 2 y perderlo todo obligaba
 * a confirmar de a una página. Los ids viven en sessionStorage, así que la
 * selección aguanta el cambio de página y el ir y volver de pantalla; los que
 * no están en la página actual viajan igual en el envío.
 */
import { useCallback, useEffect, useState } from 'react';

const CLAVE = 'seleccion:comprobantes';

function leer() {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE)) || {};
  } catch {
    return {};
  }
}

function escribir(sel) {
  try {
    const limpio = Object.fromEntries(Object.entries(sel).filter(([, v]) => v));
    if (Object.keys(limpio).length) sessionStorage.setItem(CLAVE, JSON.stringify(limpio));
    else sessionStorage.removeItem(CLAVE);
  } catch { /* modo privado sin almacenamiento: dura lo que dure la página */ }
}

export function useSeleccionPersistente(idsVisibles) {
  const [seleccion, setSeleccionInterna] = useState(leer);

  useEffect(() => { escribir(seleccion); }, [seleccion]);

  // TanStack pasa un updater o un objeto; hay que admitir ambos.
  const setSeleccion = useCallback((actualizador) => {
    setSeleccionInterna((prev) => (typeof actualizador === 'function' ? actualizador(prev) : actualizador));
  }, []);

  const ids = Object.keys(seleccion).filter((id) => seleccion[id]);
  const visibles = new Set(idsVisibles.map(String));

  return {
    seleccion,
    setSeleccion,
    ids,
    total: ids.length,
    /** Seleccionados que no están en la página que se está viendo. */
    fuera: ids.filter((id) => !visibles.has(id)).length,
    limpiar: () => setSeleccionInterna({}),
  };
}
