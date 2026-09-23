/**
 * Armazón de la aplicación.
 *
 * Sustituye a `base.html`. Con Inertia este componente NO se desmonta al
 * navegar: solo cambia la página de adentro. Por eso no hay parpadeo, la barra
 * lateral conserva su scroll y los toasts sobreviven a un cambio de pantalla.
 */
import { useEffect, useState } from 'react';
import { Link, usePage } from '@inertiajs/react';
import { Toaster, toast } from 'sonner';
import { Bell, LogOut, Menu, Moon, Search, Sun, X } from 'lucide-react';

import { MARCA_ICON, estaActivo, rutasAgrupadas, rutasTabs, construirRutas } from './lib/rutas.js';
import { Paleta } from './components/Paleta.jsx';
import { VisorImagen } from './components/VisorImagen.jsx';
import { cn } from './ui/cn.js';

/* ============================================================================
   Tema
   ========================================================================== */
function useTema() {
  const [oscuro, setOscuro] = useState(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('dark'),
  );

  const alternar = () => {
    const raiz = document.documentElement;
    // Cambiar de tema altera color, fondo, borde y sombra de casi todo a la vez.
    // Si cada uno anima su transición, el cambio se ve como una mancha: se
    // apagan todas, se fuerza el reflow y se restauran al frame siguiente.
    raiz.classList.add('cambiando-tema');
    const ahora = raiz.classList.toggle('dark');
    localStorage.theme = ahora ? 'dark' : 'light';
    document.querySelector('meta[name=theme-color]')?.setAttribute('content', ahora ? '#10131d' : '#ffffff');
    void raiz.offsetHeight;
    requestAnimationFrame(() => raiz.classList.remove('cambiando-tema'));
    setOscuro(ahora);
  };

  return [oscuro, alternar];
}

/* ============================================================================
   Piezas del armazón
   ========================================================================== */
function Marca({ compacta = false }) {
  return (
    <span className="flex items-center gap-2">
      <span className="grid size-7 place-items-center rounded-md bg-brand-600">
        <MARCA_ICON className="size-4 text-white" />
      </span>
      {!compacta && <span className="font-display text-sm font-extrabold tracking-tight">Gestor Nequi</span>}
    </span>
  );
}

function ItemMenu({ item, activo, avisos }) {
  const Icono = item.icon;
  const contenido = (
    <>
      <Icono />
      <span>{item.label}</span>
      {item.avisos && avisos > 0 && (
        <span className="ml-auto grid h-4 min-w-4 place-items-center rounded-full bg-bad-500 px-1 text-[10px] font-bold text-white">
          {avisos}
        </span>
      )}
    </>
  );

  // El admin de Django vive fuera de esta app: enlace normal, carga completa.
  if (item.externo) {
    return <a href={item.url} className="nav-link">{contenido}</a>;
  }
  return (
    <Link href={item.url} className={cn('nav-link', activo && 'active')} aria-current={activo ? 'page' : undefined}>
      {contenido}
    </Link>
  );
}

function BarraLateral({ urls, componente, avisos, usuario }) {
  const grupos = rutasAgrupadas(urls);

  // Si una página manda una prop llamada `urls`, pisa la compartida y el menú
  // se queda sin enlaces. Pasó una vez; mejor que grite a que se vea vacío.
  if (!grupos.length && import.meta.env.DEV) {
    console.error(
      'El menú está vacío: las props compartidas `urls` llegaron incompletas. '
      + '¿Alguna vista manda una prop llamada `urls`? Debe llamarse `urlsPagina`.',
      urls,
    );
  }

  return (
    <aside className="sticky top-0 hidden h-dvh w-[var(--w-sidebar)] shrink-0 flex-col bg-shell text-white lg:flex">
      <div className="flex h-[var(--h-topbar)] items-center border-b border-white/10 px-3">
        <Marca />
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        {grupos.map((grupo) => (
          <div key={grupo.nombre}>
            <p className="nav-section">{grupo.nombre}</p>
            {grupo.items.map((item) => (
              <ItemMenu key={item.clave} item={item} activo={estaActivo(item, componente)} avisos={avisos} />
            ))}
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 p-2">
        <div className="flex items-center gap-2.5 px-1.5 py-2">
          <span className="grid size-8 place-items-center rounded-full bg-white/10 text-xs font-bold">
            {usuario?.iniciales}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold">{usuario?.nombre}</p>
            <p className="truncate text-[11px] text-ink-500">{usuario?.esAdmin ? 'Administrador' : 'Operador'}</p>
          </div>
          <Link
            href={urls.salir}
            method="post"
            as="button"
            title="Salir"
            aria-label="Salir"
            className="grid size-8 place-items-center rounded-md text-ink-400 transition hover:bg-bad-500/20 hover:text-white active:scale-96"
          >
            <LogOut className="size-4" />
          </Link>
        </div>
      </div>
    </aside>
  );
}

function BarraInferior({ urls, componente, avisos }) {
  const [hoja, setHoja] = useState(false);
  const tabs = rutasTabs(urls);
  const resto = construirRutas(urls).filter((i) => !tabs.includes(i));

  return (
    <>
      {/* El alto SUMA el área segura en vez de comérsela: con `h-16` a secas el
          padding inferior del iPhone se descontaba de los 4rem y dejaba los
          iconos y sus etiquetas apretados contra el borde. */}
      <nav className="fixed inset-x-0 bottom-0 grid h-[calc(4rem+env(safe-area-inset-bottom))] grid-cols-5 border-t border-line glass layer-bar pb-[env(safe-area-inset-bottom)] lg:hidden">
        {tabs.map((item) => {
          const activo = estaActivo(item, componente);
          const Icono = item.icon;
          // "Subir" es la acción principal en campo: va destacada en el centro.
          const destacado = item.clave === 'subir';
          return (
            <Link key={item.clave} href={item.url} className={cn('navtab', activo && !destacado && 'active', destacado && 'relative')}>
              {destacado ? (
                <>
                  <span className="absolute -top-5 grid size-12 place-items-center rounded-full bg-brand-600 text-white shadow-md ring-4 ring-surface transition active:scale-96">
                    <Icono className="size-[22px]" />
                  </span>
                  <span className="mt-8 font-semibold text-brand-600 dark:text-brand-400">{item.label}</span>
                </>
              ) : (
                <>
                  <span className="icon-wrapper"><Icono /></span>
                  <span>{item.label}</span>
                </>
              )}
            </Link>
          );
        })}

        <button type="button" onClick={() => setHoja(true)} className="navtab">
          <span className="icon-wrapper"><Menu /></span>
          <span>Más</span>
        </button>
      </nav>

      {/* Hoja "Más": translate en lugar de height, para que la anime la GPU. */}
      <div className={cn('fixed inset-0 layer-sheet lg:hidden', hoja ? 'pointer-events-auto' : 'pointer-events-none')}>
        <div
          onClick={() => setHoja(false)}
          className={cn('absolute inset-0 bg-ink-950/50 transition-opacity duration-200 ease-out', hoja ? 'opacity-100' : 'opacity-0')}
        />
        <div
          className={cn(
            'absolute inset-x-0 bottom-0 rounded-t-2xl border-t border-line bg-surface-raised p-2.5',
            'pb-[calc(0.625rem+env(safe-area-inset-bottom))] transition-transform duration-200',
            hoja ? 'translate-y-0 ease-out' : 'translate-y-full ease-in',
          )}
        >
          <div className="mx-auto mb-2.5 h-1 w-9 rounded-full bg-line-strong" />
          <div className="grid grid-cols-2 gap-0.5">
            {resto.map((item) => {
              const Icono = item.icon;
              const cuerpo = (
                <>
                  <Icono />
                  {item.label}
                  {item.avisos && avisos > 0 && <span className="badge-bad ml-auto">{avisos}</span>}
                </>
              );
              return item.externo ? (
                <a key={item.clave} href={item.url} className="sheet-link">{cuerpo}</a>
              ) : (
                <Link key={item.clave} href={item.url} onClick={() => setHoja(false)} className="sheet-link">
                  {cuerpo}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}

/* ============================================================================
   Layout
   ========================================================================== */
export default function Layout({ children }) {
  const { props, component } = usePage();
  const { urls = {}, auth = {}, avisos = 0, flash = [] } = props;
  const [oscuro, alternarTema] = useTema();
  const [paleta, setPaleta] = useState(false);

  // Los mensajes de Django llegan como props y salen como toasts.
  useEffect(() => {
    flash.forEach((m) => {
      const fn = toast[m.tono] || toast;
      fn(m.texto);
    });
  }, [flash]);

  // Sin sesión (login, registro) no hay armazón: solo la tarjeta centrada.
  if (!auth.usuario) {
    return (
      <>
        <main className="grid min-h-full place-items-center p-4">
          <div className="w-full max-w-sm">{children}</div>
        </main>
        <Toaster position="top-right" theme={oscuro ? 'dark' : 'light'} closeButton richColors />
      </>
    );
  }

  return (
    <div className="flex min-h-full">
      <BarraLateral urls={urls} componente={component} avisos={avisos} usuario={auth.usuario} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 flex h-[var(--h-topbar)] items-center gap-2 border-b border-line glass layer-header px-3 md:px-4">
          <span className="lg:hidden"><Marca compacta /></span>

          <button
            type="button"
            onClick={() => setPaleta(true)}
            className="flex h-8 items-center gap-2 rounded-[var(--radius-field)] border border-line bg-surface pl-2.5 pr-2 text-subtle transition-colors hover:border-line-strong hover:text-content"
          >
            <Search className="size-4" />
            <span className="hidden text-[13px] sm:inline">Buscar</span>
            <kbd className="ml-1 hidden rounded border border-line bg-surface-inset px-1 py-px font-mono text-[10px] font-semibold sm:inline">
              Ctrl K
            </kbd>
          </button>

          <div className="ml-auto flex items-center gap-0.5">
            <button
              type="button"
              onClick={alternarTema}
              title="Cambiar tema"
              aria-label="Cambiar tema"
              className="grid size-9 place-items-center rounded-[var(--radius-field)] text-muted transition hover:bg-surface-hover hover:text-content active:scale-96"
            >
              {oscuro ? <Moon className="size-[18px]" /> : <Sun className="size-[18px]" />}
            </button>

            <Link
              href={urls.notificaciones}
              title="Notificaciones"
              aria-label={`Notificaciones${avisos ? `: ${avisos} sin leer` : ''}`}
              className="relative grid size-9 place-items-center rounded-[var(--radius-field)] text-muted transition hover:bg-surface-hover hover:text-content active:scale-96"
            >
              <Bell className="size-[18px]" />
              {avisos > 0 && (
                <span className="absolute right-0.5 top-0.5 grid h-3.5 min-w-3.5 place-items-center rounded-full bg-bad-500 px-1 text-[9px] font-bold text-white ring-2 ring-surface">
                  {avisos}
                </span>
              )}
            </Link>

            <span className="ml-1.5 hidden text-[13px] text-subtle lg:block">{auth.usuario.nombre}</span>
          </div>
        </header>

        <main className="flex-1 p-3 pb-28 md:p-4 lg:pb-6">
          {/* `key` fuerza el remontaje al cambiar de página: sin él la animación
              solo correría la primera vez, porque el nodo se reutiliza. */}
          <div key={component} className="rise mx-auto w-full max-w-[100rem]">{children}</div>
        </main>
      </div>

      <BarraInferior urls={urls} componente={component} avisos={avisos} />
      <Paleta abierta={paleta} onOpenChange={setPaleta} urls={urls} />
      <VisorImagen />
      <Toaster position="top-right" theme={oscuro ? 'dark' : 'light'} closeButton richColors />
    </div>
  );
}

/** Cabecera de página: un solo título por pantalla, con acciones a la derecha. */
export function Cabecera({ titulo, subtitulo, children }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
      <div className="min-w-0">
        <h1 className="page-title truncate">{titulo}</h1>
        {subtitulo && <p className="page-sub">{subtitulo}</p>}
      </div>
      {children && <div className="ml-auto flex items-center gap-1.5">{children}</div>}
    </div>
  );
}

export { X };
