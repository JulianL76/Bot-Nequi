/**
 * Selección que sobrevive a la paginación.
 *
 * Marcar 30 comprobantes en la página 1, pasar a la 2 y perderlo todo obligaba
 * a confirmar de a una página. Los ids viven en sessionStorage, así que la
 * selección aguanta el cambio de página y el ir y volver de pantalla; los que
 * no están en la página actual viajan igual en el envío.
 *
 * Junto a los ids se guarda un resumen de cada fila (remitente, valor, ref,
 * fecha): sin él no habría forma de sumar ni de listar lo marcado en otras
 * páginas, que el servidor ya no manda.
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

const resumir = (f) => ({
  id: f.id, de: f.de, valor: f.valor, ref: f.ref, fecha: f.fecha, hora: f.hora, estado: f.estado,
});

export function useSeleccionPersistente(filasVisibles) {
  const [seleccion, setSeleccionInterna] = useState(() => leer(CLAVE));
  const [datos, setDatos] = useState(() => leer(CLAVE_DATOS));

  // TanStack pasa un updater o un objeto; hay que admitir ambos.
  const setSeleccion = useCallback((actualizador) => {
    setSeleccionInterna((prev) => (typeof actualizador === 'function' ? actualizador(prev) : actualizador));
  }, []);

  const ids = useMemo(() => Object.keys(seleccion).filter((id) => seleccion[id]), [seleccion]);

  // Guarda el resumen de las filas marcadas que están a la vista y olvida el de
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
  const filas = ids.map((id) => datos[id] || { id: Number(id) });

  return {
    seleccion,
    setSeleccion,
    ids,
    total: ids.length,
    /** Seleccionados que no están en la página que se está viendo. */
    fuera: ids.filter((id) => !visibles.has(id)).length,
    /** Resumen de cada seleccionado, estén o no en esta página. */
    filas,
    /** Suma de los valores conocidos de la selección. */
    suma: filas.reduce((s, f) => s + (Number(f.valor) || 0), 0),
    /** Marcados antes de guardar su resumen: no entran en la suma. */
    sinDatos: filas.filter((f) => f.valor == null).length,
    quitar: (id) => setSeleccionInterna((p) => ({ ...p, [id]: false })),
    limpiar: () => setSeleccionInterna({}),
  };
}
