/**
 * Paleta de comandos (Ctrl/⌘ + K, o «/»).
 *
 * En una app de operación diaria el mouse cuesta tiempo: quien concilia todo el
 * día llega más rápido escribiendo "conc" + Enter que buscando en el menú.
 *
 * cmdk se encarga del filtrado difuso, el recorrido con flechas y la semántica
 * de listbox para lectores de pantalla.
 */
import { useEffect, useState } from 'react';
import { router } from '@inertiajs/react';
import { Command } from 'cmdk';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { CornerDownLeft, Search } from 'lucide-react';
import { construirRutas } from '../lib/rutas.js';
import { cn } from '../ui/cn.js';

export function Paleta({ abierta, onOpenChange, urls }) {
  const [consulta, setConsulta] = useState('');

  useEffect(() => {
    const alPulsar = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onOpenChange(!abierta);
        return;
      }
      // «/» abre la paleta, salvo que se esté escribiendo en un campo.
      const escribiendo = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '')
        || document.activeElement?.isContentEditable;
      if (e.key === '/' && !escribiendo && !abierta) {
        e.preventDefault();
        onOpenChange(true);
      }
    };
    window.addEventListener('keydown', alPulsar);
    return () => window.removeEventListener('keydown', alPulsar);
  }, [abierta, onOpenChange]);

  const ir = (item) => {
    onOpenChange(false);
    // El admin de Django no es parte de esta app: carga completa.
    if (item.externo) window.location.href = item.url;
    else router.visit(item.url);
  };

  const grupos = construirRutas(urls).reduce((acc, r) => {
    (acc[r.grupo] ||= []).push(r);
    return acc;
  }, {});

  return (
    <DialogPrimitive.Root open={abierta} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 layer-modal bg-ink-950/50 data-[state=open]:animate-[aparecer_150ms_ease-out]" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-[12vh] layer-modal w-[min(34rem,calc(100vw-1.5rem))] -translate-x-1/2
                     card overflow-hidden shadow-lg
                     data-[state=open]:animate-[entrar-modal_180ms_var(--ease-out-soft)]"
          aria-label="Ir a"
        >
          <DialogPrimitive.Title className="sr-only">Ir a</DialogPrimitive.Title>

          <Command loop shouldFilter>
            <div className="flex h-11 items-center gap-2 border-b border-line px-3">
              <Search className="size-4 shrink-0 text-subtle" />
              <Command.Input
                value={consulta}
                onValueChange={setConsulta}
                placeholder="Ir a…"
                className="flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-subtle"
              />
              <kbd className="rounded border border-line bg-surface-inset px-1 py-px font-mono text-[10px]">ESC</kbd>
            </div>

            <Command.List className="max-h-72 overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-5 text-center text-[13px] text-subtle">
                Sin resultados
              </Command.Empty>

              {Object.entries(grupos).map(([grupo, items]) => (
                <Command.Group
                  key={grupo}
                  heading={grupo}
                  className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1
                             [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-bold
                             [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide
                             [&_[cmdk-group-heading]]:text-subtle"
                >
                  {items.map((r) => (
                    <Command.Item
                      key={r.url}
                      value={`${r.label} ${grupo}`}
                      onSelect={() => ir(r)}
                      className={cn(
                        'flex cursor-pointer items-center gap-2.5 rounded-[var(--radius-field)] px-2.5 py-2',
                        'text-[13px] font-medium transition-colors duration-100',
                        'data-[selected=true]:bg-brand-600 data-[selected=true]:text-white',
                      )}
                    >
                      <r.icon className="size-3.5 shrink-0 opacity-70" />
                      {r.label}
                      <CornerDownLeft className="ml-auto size-3 opacity-0 data-[selected=true]:opacity-60" />
                    </Command.Item>
                  ))}
                </Command.Group>
              ))}
            </Command.List>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
