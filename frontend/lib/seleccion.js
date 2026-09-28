/**
 * Selección que sobrevive a la paginación.
 *
 * Marcar 30 comprobantes en la página 1, pasar a la 2 y perderlo todo obligaba
 * a confirmar de a una página. Los ids viven en sessionStorage, así que la
 * selección aguanta el cambio de página y el ir y volver de pantalla; los que
 * no están en la página actual viajan igual en el envío.
 *
 * Junto a los ids se guarda el valor de cada fila: sin él no habría forma de
 * sumar lo marcado en otras páginas, que el servidor ya no manda.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

const CLAVE = 'seleccion:comprobantes';
const CLAVE_DATOS = 'seleccion:comprobantes:datos';

function leer(clave) {
  try {
    return JSON.parse(sessionStorage.getItem(clave)) || {};
  } catch {
    return {};
  }
}

function escribir(clave, obj) {
  try {
    if (Object.keys(obj).length) sessionStorage.setItem(clave, JSON.stringify(obj));
    else sessionStorage.removeItem(clave);
  } catch { /* modo privado sin almacenamiento: dura lo que dure la página */ }
}

const resumir = (f) => ({ valor: f.valor });

export function useSeleccionPersistente(filasVisibles) {
  const [seleccion, setSeleccionInterna] = useState(() => leer(CLAVE));
  const [datos, setDatos] = useState(() => leer(CLAVE_DATOS));

  // TanStack pasa un updater o un objeto; hay que admitir ambos.
  const setSeleccion = useCallback((actualizador) => {
    setSeleccionInterna((prev) => (typeof actualizador === 'function' ? actualizador(prev) : actualizador));
  }, []);

  const ids = useMemo(() => Object.keys(seleccion).filter((id) => seleccion[id]), [seleccion]);

  // Guarda el valor de las filas marcadas que están a la vista y olvida el de
  // las desmarcadas. Así la caché nunca crece más que la selección.
  useEffect(() => {
    const visibles = new Map(filasVisibles.map((f) => [String(f.id), f]));
    setDatos((prev) => {
      const nuevo = {};
      ids.forEach((id) => {
        const f = visibles.get(id);
        if (f) nuevo[id] = resumir(f);
        else if (prev[id]) nuevo[id] = prev[id];
      });
      return nuevo;
    });
  }, [ids, filasVisibles]);

  useEffect(() => {
    escribir(CLAVE, Object.fromEntries(ids.map((id) => [id, true])));
  }, [ids]);
  useEffect(() => { escribir(CLAVE_DATOS, datos); }, [datos]);

  const visibles = new Set(filasVisibles.map((f) => String(f.id)));

  return {
    seleccion,
    setSeleccion,
    ids,
    total: ids.length,
    /** Seleccionados que no están en la página que se está viendo. */
    fuera: ids.filter((id) => !visibles.has(id)).length,
    /** Suma de los valores conocidos de la selección. */
    suma: ids.reduce((s, id) => s + (Number(datos[id]?.valor) || 0), 0),
    limpiar: () => setSeleccionInterna({}),
  };
}
