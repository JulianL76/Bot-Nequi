import { useForm, router, usePage } from '@inertiajs/react';
import { Check, Plus, Route, X } from 'lucide-react';

import { Cabecera } from '../../Layout.jsx';
import { Badge, Button, Card, Campo, EmptyState, Input } from '../../ui/index.jsx';
import { numero, plural } from '../../lib/formato.js';
import { cn } from '../../ui/cn.js';

export default function Rutas({ rutas }) {
  const { urls } = usePage().props;
  const { data, setData, post, processing, reset, errors } = useForm({ numero: '', nombre: '' });

  const crear = (e) => {
    e.preventDefault();
    post(urls.rutas, { onSuccess: () => reset() });
  };

  return (
    <div className="max-w-3xl">
      <Cabecera titulo="Rutas" subtitulo="Las rutas agrupan los comprobantes para conciliar y exportar por zona." />

      <Card className="card-pad mb-3">
        <h2 className="card-title mb-2.5">Nueva ruta</h2>
        <form onSubmit={crear} className="flex flex-wrap items-end gap-3">
          <Campo label="Número *" id="ruta-numero" error={errors.numero} className="min-w-28 flex-1">
            <Input
              id="ruta-numero" type="number" required placeholder="3"
              value={data.numero} onChange={(e) => setData('numero', e.target.value)}
            />
          </Campo>
          <Campo label="Nombre (opcional)" id="ruta-nombre" error={errors.nombre} className="min-w-40 flex-[2]">
            <Input
              id="ruta-nombre" placeholder="Centro"
              value={data.nombre} onChange={(e) => setData('nombre', e.target.value)}
            />
          </Campo>
          <Button type="submit" variant="primary" cargando={processing}><Plus />Crear</Button>
        </form>
      </Card>

      {rutas.length === 0 ? (
        <Card>
          <EmptyState icon={Route} titulo="Todavía no hay rutas." descripcion="Crea la primera con el formulario de arriba." />
        </Card>
      ) : (
        <div className="space-y-2">
          {rutas.map((r) => (
            <Card key={r.id} className={cn('card-pad flex flex-wrap items-center gap-3', !r.activa && 'opacity-70')}>
              <span
                className={cn(
                  'nums grid size-8 shrink-0 place-items-center rounded-[var(--radius-field)] font-display font-bold',
                  r.activa ? 'bg-brand-600 text-white' : 'bg-surface-inset text-subtle',
                )}
              >
                {r.numero}
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">
                  Ruta {r.numero}
                  {r.nombre && <span className="font-normal text-muted"> — {r.nombre}</span>}
                </p>
                <p className="nums t-meta">
                  {numero(r.nComprobantes)} {plural(r.nComprobantes, 'comprobante')}
                </p>
              </div>

              {r.activa ? <Badge tono="ok" punto>Activa</Badge> : <Badge>Inactiva</Badge>}

              <Button size="sm" onClick={() => router.post(`/comprobantes/rutas/${r.id}/toggle/`)}>
                {r.activa ? <><X />Desactivar</> : <><Check />Activar</>}
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
