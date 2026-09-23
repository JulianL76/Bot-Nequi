/**
 * Sondeo del avance de un lote.
 *
 * El análisis corre en segundo plano, así que la pantalla tiene que preguntar.
 * Tres cosas que este hook resuelve y que la versión anterior no:
 *
 * · Se detiene al desmontar el componente. Antes el temporizador seguía vivo
 *   tras cambiar de pantalla y escribía sobre datos de OTRO lote.
 * · Se detiene si la pestaña está oculta: sondear en segundo plano gasta
 *   batería y datos en el celular, que es donde más se usa.
 * · Distingue "procesando" de "atascado": si no avanza en 20 segundos, lo dice
 *   en vez de fingir que todo va bien.
 */
import { useEffect, useRef, useState } from 'react';

const INTERVALO = 2000;
const ATASCO = 20000;

export function useProgreso(url, inicial, { activo = true, alTerminar } = {}) {
  const [datos, setDatos] = useState(inicial);
  const [atascado, setAtascado] = useState(false);
  const ultimoAvance = useRef({ procesadas: inicial?.procesadas ?? 0, cuando: Date.now() });

  useEffect(() => {
    if (!activo || !url) return undefined;

    let vivo = true;
    let temporizador;

    const consultar = async () => {
      if (!vivo) return;
      if (document.hidden) { temporizador = setTimeout(consultar, INTERVALO); return; }

      try {
        const r = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
        if (!r.ok) throw new Error(r.status);
        const d = await r.json();
        if (!vivo) return;

        if (d.procesadas !== ultimoAvance.current.procesadas) {
          ultimoAvance.current = { procesadas: d.procesadas, cuando: Date.now() };
        }
        setAtascado(Date.now() - ultimoAvance.current.cuando > ATASCO);
        setDatos(d);

        if (d.terminado || d.pausado) { alTerminar?.(d); return; }
      } catch {
        /* Fallo puntual de red: se reintenta en el siguiente ciclo. */
      }
      if (vivo) temporizador = setTimeout(consultar, INTERVALO);
    };

    consultar();
    return () => { vivo = false; clearTimeout(temporizador); };
  }, [url, activo, alTerminar]);

  return { datos, atascado, segundosSinAvanzar: Math.round((Date.now() - ultimoAvance.current.cuando) / 1000) };
}
