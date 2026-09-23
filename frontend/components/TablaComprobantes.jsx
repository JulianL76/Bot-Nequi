/**
 * Tabla de comprobantes (TanStack Table + virtualización).
 *
 * Dos cosas que solo se pueden hacer con una tabla de verdad:
 *
 * · **Columnas configurables.** Cada quien mira cosas distintas; el que
 *   concilia no necesita "origen" y el que audita sí. La elección se guarda.
 *
 * · **Virtualización.** Con 200 filas por página el navegador pinta 200 filas
 *   aunque se vean 15. Aquí solo se montan las visibles, así que subir el
 *   tamaño de página no cuesta fluidez.
 *
 * El orden y el filtrado siguen en el servidor: son miles de registros y SQL
 * lo hace mejor que el navegador. TanStack aporta la interfaz, no el cálculo.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from '@inertiajs/react';
import {
  flexRender, getCoreRowModel, useReactTable,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ArrowDown, ArrowUp, ChevronsUpDown, Copy, Eye, Pencil, Trash2 } from 'lucide-react';

import { Badge, Button, Checkbox } from '../ui/index.jsx';
import { abrirImagen } from './VisorImagen.jsx';
import { fechaHora, pesos } from '../lib/formato.js';
import { cn } from '../ui/cn.js';

/** A partir de cuántas filas conviene virtualizar. */
const UMBRAL_VIRTUAL = 60;

const CLAVE_COLUMNAS = 'comprobantes:columnas';

export const COLUMNAS_OCULTABLES = [
  { id: 'ref', label: 'Referencia' },
  { id: 'fecha', label: 'Fecha' },
  { id: 'origen', label: 'Origen' },
  { id: 'estado', label: 'Estado' },
];

export function useColumnasVisibles() {
  const [visibles, setVisibles] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(CLAVE_COLUMNAS)) || {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(CLAVE_COLUMNAS, JSON.stringify(visibles));
    } catch { /* modo privado: la preferencia dura la sesión */ }
  }, [visibles]);

  return [visibles, setVisibles];
}

function CabeceraOrden({ columna, etiqueta, sort, onSort, alineado }) {
  const activo = sort === columna || sort === `-${columna}`;
  const desc = sort === `-${columna}`;
  const Icono = activo ? (desc ? ArrowDown : ArrowUp) : ChevronsUpDown;

  return (
    <button
      type="button"
      onClick={() => onSort(activo && !desc ? `-${columna}` : columna)}
      className={cn(
        'group inline-flex items-center gap-1 transition-colors hover:text-content',
        alineado === 'derecha' && 'w-full justify-end',
      )}
      aria-label={`Ordenar por ${etiqueta}`}
    >
      {etiqueta}
      <Icono
        className={cn('size-3', activo ? 'text-brand-600 dark:text-brand-400' : 'opacity-0 group-hover:opacity-40')}
        strokeWidth={activo ? 3 : 2}
      />
    </button>
  );
}

export function TablaComprobantes({
  filas, seleccion, onSeleccion, sort, onSort, columnasVisibles, urlComprobantes, onEliminar,
}) {
  const contenedor = useRef(null);

  // Shift + clic. El ancla es la última fila marcada a mano, guardada como
  // posición dentro del modelo de filas y no del array de datos: así el rango
  // sigue el orden que se está viendo. Sobrevive a la virtualización porque
  // `getRowModel()` trae todas las filas, no solo las pintadas.
  const ancla = useRef(null);
  const conShift = useRef(false);

  const alMarcarFila = useCallback((fila, tabla, valor) => {
    const filas = tabla.getRowModel().rows;
    const i = filas.findIndex((f) => f.id === fila.id);
    const desde = ancla.current;

    if (conShift.current && desde !== null && desde !== i && desde < filas.length) {
      const rango = {};
      for (let k = Math.min(desde, i); k <= Math.max(desde, i); k++) rango[filas[k].id] = valor;
      // Todo el rango toma el valor de la casilla pulsada: con Shift se marca
      // o se desmarca en bloque, no se invierte fila por fila.
      tabla.setRowSelection((prev) => ({ ...prev, ...rango }));
    } else {
      fila.toggleSelected(valor);
    }

    conShift.current = false;   // la bandera se consume en cada marcado
    ancla.current = i;
  }, []);

  const columnas = useMemo(() => [
    {
      id: 'sel',
      size: 36,
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllRowsSelected()}
          indeterminate={table.getIsSomeRowsSelected() && !table.getIsAllRowsSelected()}
          onCheckedChange={(v) => { ancla.current = null; table.toggleAllRowsSelected(!!v); }}
          aria-label="Seleccionar todos"
        />
      ),
      cell: ({ row, table }) => (
        <Checkbox
          checked={row.getIsSelected()}
          // `onCheckedChange` no trae el evento, así que el Shift se lee aquí.
          // El preventDefault evita que el navegador pinte de azul el texto de
          // todas las filas del rango, que es lo que hace Shift por defecto.
          onPointerDown={(e) => { conShift.current = e.shiftKey; if (e.shiftKey) e.preventDefault(); }}
          onCheckedChange={(v) => alMarcarFila(row, table, !!v)}
          aria-label={`Seleccionar comprobante ${row.original.id}`}
        />
      ),
    },
    {
      id: 'de',
      header: () => <CabeceraOrden columna="de" etiqueta="Remitente" sort={sort} onSort={onSort} />,
      cell: ({ row }) => {
        const c = row.original;
        return (
          <div className="min-w-0">
            <p className="truncate font-medium">{c.de}</p>
            {c.esDuplicado ? (
              <Link href={`${urlComprobantes}?q=${encodeURIComponent(c.ref || '')}`} className="badge-bad mt-0.5">
                <Copy />Duplicado
              </Link>
            ) : c.nDups > 0 ? (
              <Link href={`${urlComprobantes}?q=${encodeURIComponent(c.ref || '')}`} className="badge-ok mt-0.5">
                Original · {c.nDups}
              </Link>
            ) : null}
          </div>
        );
      },
    },
    {
      id: 'valor',
      size: 120,
      header: () => <CabeceraOrden columna="valor" etiqueta="Valor" sort={sort} onSort={onSort} alineado="derecha" />,
      cell: ({ row }) => <span className="nums block text-right font-bold">{pesos(row.original.valor)}</span>,
    },
    {
      id: 'ref',
      size: 130,
      header: () => <CabeceraOrden columna="ref" etiqueta="Referencia" sort={sort} onSort={onSort} />,
      cell: ({ row }) => <span className="font-mono text-muted">{row.original.ref || '—'}</span>,
    },
    {
      id: 'fecha',
      size: 130,
      header: () => <CabeceraOrden columna="fecha_dt" etiqueta="Fecha" sort={sort} onSort={onSort} />,
      cell: ({ row }) => (
        <span className="whitespace-nowrap text-muted">
          {row.original.fecha || '—'}
          {row.original.hora && <span className="text-subtle"> · {row.original.hora}</span>}
        </span>
      ),
    },
    {
      id: 'origen',
      size: 90,
      header: () => <CabeceraOrden columna="origen" etiqueta="Origen" sort={sort} onSort={onSort} />,
      cell: ({ row }) => <Badge>{row.original.origen}</Badge>,
    },
    {
      id: 'estado',
      size: 170,
      header: () => <CabeceraOrden columna="estado" etiqueta="Estado" sort={sort} onSort={onSort} />,
      cell: ({ row }) => {
        const c = row.original;
        if (c.estado !== 'confirmado') return <Badge tono="warn" punto>Pendiente</Badge>;
        return (
          <div className="min-w-0">
            <Badge tono="ok" punto>Confirmado</Badge>
            {c.conciliacion && (
              <a
                href={`/conciliar/lote/${c.conciliacion.loteId}/#conc-item-${c.conciliacion.itemId}`}
                className="mt-0.5 block truncate text-[11px] font-medium text-brand-600 hover:underline dark:text-brand-400"
              >
                conc. #{c.conciliacion.loteId}{c.conciliacion.ruta ? ` · Ruta ${c.conciliacion.ruta}` : ''}
              </a>
            )}
            {!c.conciliacion && c.confirmadoVia && (
              <p className="truncate t-meta text-subtle">{c.confirmadoVia}</p>
            )}
            {c.confirmadoEn && (
              <p className="nums truncate t-meta text-subtle">
                {fechaHora(c.confirmadoEn)}{c.confirmadoPor ? ` · ${c.confirmadoPor}` : ''}
              </p>
            )}
          </div>
        );
      },
    },
    {
      id: 'acciones',
      size: 104,
      header: () => <span className="block text-right">Acciones</span>,
      cell: ({ row }) => {
        const c = row.original;
        return (
          // Las acciones aparecen al apuntar la fila y la tabla queda limpia,
          // PERO solo donde hay puntero: en un móvil no existe el hover, así que
          // con `opacity-0` a secas los botones quedaban invisibles para siempre.
          <div className={cn(
            'flex items-center justify-end gap-0.5 transition-opacity',
            '[@media(hover:hover)]:opacity-0 focus-within:opacity-100 group-hover:opacity-100',
          )}>
            {c.imagen && (
              <Button
                variant="ghost" size="sm" icon
                title="Ver comprobante"
                aria-label={`Ver comprobante de ${c.de}`}
                onClick={() => abrirImagen(c.imagen, `${c.de} · ${pesos(c.valor)}`)}
              >
                <Eye />
              </Button>
            )}
            <Button variant="ghost" size="sm" icon asChild className="text-brand-600 dark:text-brand-400">
              <Link href={`${urlComprobantes}${c.id}/editar/`} title="Editar" aria-label={`Editar comprobante ${c.id}`}>
                <Pencil />
              </Link>
            </Button>
            <Button
              variant="ghost" size="sm" icon
              className="text-bad-600 dark:text-bad-400"
              title="Eliminar"
              aria-label={`Eliminar comprobante ${c.id}`}
              onClick={() => onEliminar(c)}
            >
              <Trash2 />
            </Button>
          </div>
        );
      },
    },
  ], [sort, onSort, urlComprobantes, onEliminar, alMarcarFila]);

  const tabla = useReactTable({
    data: filas,
    columns: columnas,
    state: { rowSelection: seleccion, columnVisibility: columnasVisibles },
    onRowSelectionChange: onSeleccion,
    getRowId: (fila) => String(fila.id),
    getCoreRowModel: getCoreRowModel(),
    enableRowSelection: true,
    manualSorting: true,          // ordena el servidor
    manualPagination: true,
  });

  const rows = tabla.getRowModel().rows;
  const virtualizar = rows.length > UMBRAL_VIRTUAL;

  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => contenedor.current,
    estimateSize: () => 42,
    overscan: 12,
    enabled: virtualizar,
  });

  const items = virtualizar ? virtual.getVirtualItems() : null;
  const paddingArriba = items?.length ? items[0].start : 0;
  const paddingAbajo = items?.length ? virtual.getTotalSize() - items[items.length - 1].end : 0;

  return (
    <div
      ref={contenedor}
      className={cn('table-wrap', virtualizar && 'max-h-[calc(100dvh-16rem)] overflow-y-auto')}
    >
      <table className="table">
        <thead>
          {tabla.getHeaderGroups().map((grupo) => (
            <tr key={grupo.id}>
              {grupo.headers.map((h) => (
                <th key={h.id} style={{ width: h.column.columnDef.size }}>
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>

        <tbody>
          {paddingArriba > 0 && <tr style={{ height: paddingArriba }} aria-hidden />}

          {(items ? items.map((v) => rows[v.index]) : rows).map((fila) => (
            <tr
              key={fila.id}
              data-index={fila.index}
              className={cn(
                'group',
                fila.original.esDuplicado && 'bg-bad-100/40 dark:bg-bad-500/5',
                fila.getIsSelected() && 'bg-brand-50 dark:bg-brand-500/10',
              )}
            >
              {fila.getVisibleCells().map((celda) => (
                <td key={celda.id}>{flexRender(celda.column.columnDef.cell, celda.getContext())}</td>
              ))}
            </tr>
          ))}

          {paddingAbajo > 0 && <tr style={{ height: paddingAbajo }} aria-hidden />}
        </tbody>
      </table>
    </div>
  );
}
