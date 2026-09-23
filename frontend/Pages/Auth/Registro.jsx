import { useMemo } from 'react';
import { Link, useForm, usePage } from '@inertiajs/react';
import { CircleAlert, User } from 'lucide-react';

import { Button, Card, Campo, Input } from '../../ui/index.jsx';

export default function Registro({ campos, errors }) {
  const { urls } = usePage().props;

  // Los campos los describe Django: si mañana el formulario cambia, esta
  // pantalla lo refleja sin tocar el front.
  const inicial = useMemo(
    () => Object.fromEntries(campos.map((c) => [c.nombre, ''])),
    [campos],
  );
  const { data, setData, post, processing } = useForm(inicial);

  return (
    <Card className="p-4 shadow-sm md:p-6">
      <div className="mb-5 flex flex-col items-center text-center">
        <span className="mb-3 grid size-10 place-items-center rounded-[var(--radius-card)] bg-brand-600 shadow-sm">
          <User className="size-5 text-white" />
        </span>
        <h1 className="t-titulo">Crear cuenta</h1>
        <p className="page-sub">Registra un operador y su negocio.</p>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); post(urls.registro); }} className="space-y-3">
        {errors?.general && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-[var(--radius-field)] border border-bad-500/25 bg-bad-100 px-3 py-2 dark:bg-bad-500/10"
          >
            <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-bad-600 dark:text-bad-400" />
            <p className="t-meta text-bad-600 dark:text-bad-400">{errors.general}</p>
          </div>
        )}

        {campos.map((c) => (
          <Campo
            key={c.nombre}
            id={`campo-${c.nombre}`}
            label={c.etiqueta}
            error={errors?.[c.nombre]}
            hint={c.ayuda || undefined}
          >
            <Input
              id={`campo-${c.nombre}`}
              name={c.nombre}
              type={c.tipo}
              required={c.requerido}
              autoComplete={c.tipo === 'password' ? 'new-password' : 'off'}
              value={data[c.nombre] ?? ''}
              onChange={(e) => setData(c.nombre, e.target.value)}
            />
          </Campo>
        ))}

        <Button type="submit" variant="primary" size="lg" className="mt-1 w-full" cargando={processing}>
          Registrarme
        </Button>
      </form>

      <p className="mt-4 text-center t-meta">
        ¿Ya tienes cuenta?{' '}
        <Link href={urls.entrar} className="font-semibold text-brand-600 hover:underline dark:text-brand-400">
          Inicia sesión
        </Link>
      </p>
    </Card>
  );
}
