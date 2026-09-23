import { Link, router, usePage } from '@inertiajs/react';
import { CalendarDays, Download, Hourglass, ReceiptText, Wallet } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '../../ui/index.jsx';
import { Estadistica, FilaEstadisticas } from '../../components/Estadistica.jsx';
import { GraficaArea, GraficaBarras } from '../../components/Grafica.jsx';
import { fechaHora, pesos, numero, plural } from '../../lib/formato.js';

export default function Home({
  saludo, fecha, totalComprobantes, totalMonto, sinConfirmar, montoSinConfirmar,
  conciliacionesPendientes, serie, topContactos, ultimos, urlsPagina,
}) {
  const { urls } = usePage().props;

  // Un día sin movimiento no es un error, pero sin decirlo lo parece.
  const sinDatosHoy = !!fecha && totalComprobantes === 0;

  // El filtro de fecha recarga la página con la fecha nueva; Inertia solo
  // repone las props, no recarga el navegador.
  const cambiarFecha = (valor) => {
    router.get(urls.inicio, valor ? { fecha: valor } : {}, {
      preserveState: true,
      preserveScroll: true,
    });
  };

  return (
    <>
      <Cabecera titulo="Dashboard" subtitulo={saludo}>
        <label className="relative flex h-[var(--h-control)] cursor-pointer items-center gap-1.5 rounded-[var(--radius-field)] border border-line bg-surface px-2.5 transition-colors hover:border-line-strong">
          <CalendarDays className="size-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
          <span className="whitespace-nowrap text-xs font-medium">
            {fecha ? fechaHora(fecha).slice(0, 10) : 'Todo el histórico'}
          </span>
          <input
            type="date"
            value={fecha || ''}
            onChange={(e) => cambiarFecha(e.target.value)}
            aria-label="Filtrar por fecha"
            className="absolute inset-0 size-full cursor-pointer opacity-0"
          />
        </label>

        {fecha && (
          <Button size="sm" variant="ghost" onClick={() => cambiarFecha('all')}>
            Ver todo
          </Button>
        )}

        <Button size="sm" variant="secondary" asChild>
          <a href={urlsPagina.exportar}>
            <Download />
            <span className="hidden sm:inline">Excel</span>
          </a>
        </Button>
      </Cabecera>

      {/*
        El dashboard filtra por hoy de entrada. Si hoy no hubo movimiento, las
        cifras en cero y la gráfica plana parecen un error: hay que decir que
        es el filtro, y ofrecer la salida en el mismo sitio.
      */}
      {sinDatosHoy && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-[var(--radius-card)] border border-line bg-surface px-3 py-2.5">
          <CalendarDays className="size-4 shrink-0 text-subtle" />
          <p className="t-cuerpo text-muted">
            No hay comprobantes registrados el{' '}
            <span className="font-semibold text-content">{fecha}</span>. Las cifras de abajo son de ese día.
          </p>
          <Button size="sm" variant="primary" className="ml-auto" onClick={() => cambiarFecha('all')}>
            Ver todo el histórico
          </Button>
        </div>
      )}

      <FilaEstadisticas className="mb-3">
        <Estadistica
          etiqueta="Comprobantes"
          valor={numero(totalComprobantes)}
          detalle={fecha ? 'en la fecha filtrada' : 'en total'}
          icon={ReceiptText}
        />
        <Estadistica etiqueta="Monto" valor={pesos(totalMonto)} icon={Wallet} />
        <Estadistica
          etiqueta="Sin confirmar"
          valor={numero(sinConfirmar)}
          detalle={pesos(montoSinConfirmar)}
          tono={sinConfirmar > 0 ? 'aviso' : 'ok'}
          icon={Hourglass}
        />
        <Estadistica
          etiqueta="Conciliaciones pendientes"
          valor={numero(conciliacionesPendientes)}
          tono={conciliacionesPendientes > 0 ? 'aviso' : 'ok'}
        />
      </FilaEstadisticas>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Recaudo de los últimos 14 días</CardTitle>
          </CardHeader>
          <div className="p-2">
            <GraficaArea
              etiquetas={serie.etiquetas}
              valores={serie.valores}
              nombre="Recaudo"
              moneda
              alto={220}
            />
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quiénes más envían</CardTitle>
          </CardHeader>
          {topContactos.length ? (
            <div className="p-2">
              <GraficaBarras
                etiquetas={topContactos.map((c) => c.nombre)}
                valores={topContactos.map((c) => c.total)}
                nombre="Total recibido"
                moneda
                alto={220}
              />
            </div>
          ) : (
            <EmptyState titulo="Todavía no hay datos" descripcion="Cuando entren comprobantes aparecerá el ranking." />
          )}
        </Card>
      </div>

      <Card className="mt-3">
        <CardHeader>
          <CardTitle>Últimos comprobantes</CardTitle>
          <Link href={urls.comprobantes} className="ml-auto text-xs font-semibold text-brand-600 hover:underline dark:text-brand-400">
            Ver todos
          </Link>
        </CardHeader>

        {ultimos.length ? (
          <ul className="divide-y divide-line">
            {ultimos.map((c) => (
              <li key={c.id}>
                <Link
                  href={`${urls.comprobantes}${c.id}/editar/`}
                  className="flex items-center gap-3 px-3 py-2 transition-colors hover:bg-surface-hover md:px-4"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{c.de}</span>
                    <span className="block truncate t-meta text-subtle">
                      {c.ref || '—'} · {c.creadoEn ? fechaHora(c.creadoEn) : '—'}
                    </span>
                  </span>
                  <span className="nums shrink-0 font-bold">{pesos(c.valor)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            icon={ReceiptText}
            titulo="Aún no hay comprobantes"
            descripcion="Sube las fotos y el gestor los lee por ti."
          >
            <Button variant="primary" size="sm" asChild>
              <Link href={urls.subir}>Subir comprobantes</Link>
            </Button>
          </EmptyState>
        )}
      </Card>

    </>
  );
}
