import { Link, useForm, usePage } from '@inertiajs/react';
import { Banknote, ChevronRight, CircleAlert } from 'lucide-react';

import { Button, Card, Campo, Input } from '../../ui/index.jsx';

export default function Entrar({ errors }) {
  const { urls } = usePage().props;
  const { data, setData, post, processing } = useForm({ username: '', password: '' });

  return (
    <>
      <Card className="p-4 shadow-sm md:p-6">
        <div className="mb-5 flex flex-col items-center text-center">
          <span className="mb-3 grid size-10 place-items-center rounded-[var(--radius-card)] bg-brand-600 shadow-sm">
            <Banknote className="size-5 text-white" />
          </span>
          <h1 className="t-titulo">Gestor Nequi</h1>
          <p className="page-sub">Ingresa para gestionar comprobantes y conciliaciones.</p>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); post(urls.entrar); }} className="space-y-3">
          {errors?.general && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-[var(--radius-field)] border border-bad-500/25 bg-bad-100 px-3 py-2 dark:bg-bad-500/10"
            >
              <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-bad-600 dark:text-bad-400" />
              <p className="t-meta text-bad-600 dark:text-bad-400">{errors.general}</p>
            </div>
          )}

          <Campo label="Usuario" id="usuario" error={errors?.username}>
            <Input
              id="usuario" name="username" autoComplete="username" autoFocus required
              value={data.username} onChange={(e) => setData('username', e.target.value)}
            />
          </Campo>

          <Campo label="Contraseña" id="clave" error={errors?.password}>
            <Input
              id="clave" name="password" type="password" autoComplete="current-password" required
              value={data.password} onChange={(e) => setData('password', e.target.value)}
            />
          </Campo>

          <Button type="submit" variant="primary" size="lg" className="mt-1 w-full" cargando={processing}>
            Entrar<ChevronRight />
          </Button>
        </form>

        <p className="mt-4 text-center t-meta">
          ¿No tienes cuenta?{' '}
          <Link href={urls.registro} className="font-semibold text-brand-600 hover:underline dark:text-brand-400">
            Regístrate
          </Link>
        </p>
      </Card>

      <p className="mt-3 text-center t-meta text-subtle">
        Gestor Nequi · conciliación de comprobantes
      </p>
    </>
  );
}
