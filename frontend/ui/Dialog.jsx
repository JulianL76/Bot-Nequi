/**
 * Diálogo modal (Radix).
 *
 * Radix resuelve lo que antes estaba a medias con Alpine: atrapa el foco, lo
 * devuelve al cerrar, cierra con Escape, marca el resto de la página como
 * inerte para lectores de pantalla y bloquea el scroll del fondo.
 *
 * Entradas ease-out y salidas más cortas: las cosas llegan con calma y se van
 * rápido, nunca al revés.
 */
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from './cn.js';
import { Button } from './index.jsx';

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({ titulo, descripcion, icon: Icon, className, children, ...props }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay
        className={cn(
          'fixed inset-0 layer-modal bg-ink-950/50',
          'data-[state=open]:animate-[aparecer_150ms_ease-out]',
          'data-[state=closed]:animate-[desaparecer_100ms_ease-in]',
        )}
      />
      <DialogPrimitive.Content
        className={cn(
          'fixed left-1/2 top-[8vh] layer-modal w-[min(30rem,calc(100vw-1.5rem))] -translate-x-1/2',
          'card overflow-hidden shadow-lg',
          'data-[state=open]:animate-[entrar-modal_180ms_var(--ease-out-soft)]',
          'data-[state=closed]:animate-[salir-modal_120ms_ease-in]',
          className,
        )}
        {...props}
      >
        <div className="card-header">
          {Icon && <Icon className="size-4 text-muted" />}
          <DialogPrimitive.Title className="card-title">{titulo}</DialogPrimitive.Title>
          <DialogPrimitive.Close asChild>
            <Button variant="ghost" size="sm" icon className="ml-auto" aria-label="Cerrar">
              <X />
            </Button>
          </DialogPrimitive.Close>
        </div>

        {descripcion && (
          <DialogPrimitive.Description className="sr-only">{descripcion}</DialogPrimitive.Description>
        )}

        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

/**
 * Confirmación de una acción destructiva.
 *
 * Sustituye a los `confirm()` del navegador: aquí se puede explicar QUÉ se
 * pierde exactamente, que es lo que el diálogo nativo no permite.
 */
export function ConfirmDialog({
  abierto, onOpenChange, titulo, mensaje, confirmar = 'Eliminar', onConfirm, destructivo = true,
}) {
  return (
    <Dialog open={abierto} onOpenChange={onOpenChange}>
      <DialogContent titulo={titulo} className="w-[min(26rem,calc(100vw-1.5rem))]">
        <div className="card-pad">
          <p className="t-cuerpo text-muted">{mensaje}</p>
          <div className="mt-4 flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="ghost">Cancelar</Button>
            </DialogClose>
            <Button
              variant={destructivo ? 'danger' : 'primary'}
              onClick={() => { onOpenChange(false); onConfirm?.(); }}
            >
              {confirmar}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
