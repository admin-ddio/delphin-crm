/**
 * Modal Dialog and right-side Drawer, both on native <dialog> + showModal()
 * (focus trap, Escape closes, inert background), named by aria-labelledby.
 * PROVISIONAL visuals; the Drawer follows the clickable demo's task drawer
 * (≤ 560 px, full height, right edge). Keep the ARIA wiring when porting.
 */
import { useEffect, useId, useRef, type ReactNode } from 'react';

import { cn } from '@/lib/utils';

interface BaseProps {
  open: boolean;
  onClose(): void;
  title: string;
  children?: ReactNode;
  footer?: ReactNode;
}

function useModal(open: boolean) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal?.();
    if (!open && dialog.open) dialog.close?.();
  }, [open]);
  return ref;
}

export function Dialog({ open, onClose, title, children, footer }: BaseProps) {
  const ref = useModal(open);
  const titleId = useId();
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      className="m-auto w-full max-w-lg rounded-lg border border-line bg-surface p-0 text-fg shadow-xl backdrop:bg-[rgb(8_20_26/.45)]"
    >
      <div className="p-5">
        <h2 id={titleId} className="text-base font-semibold">
          {title}
        </h2>
        <div className="mt-3">{children}</div>
      </div>
      {footer ? (
        <div className="flex justify-end gap-2 border-t border-line-soft px-5 py-3">{footer}</div>
      ) : null}
    </dialog>
  );
}

export interface DrawerProps extends BaseProps {
  /** Small line above the title (e.g. "T-12 · Acme Ltd"). */
  eyebrow?: ReactNode;
}

export function Drawer({ open, onClose, title, eyebrow, children, footer }: DrawerProps) {
  const ref = useModal(open);
  const titleId = useId();
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      className={cn(
        'fixed inset-y-0 right-0 left-auto m-0 h-full max-h-none w-[min(560px,100%)] max-w-none',
        'border-l border-line bg-surface p-0 text-fg backdrop:bg-[rgb(8_20_26/.45)]',
      )}
    >
      <div className="flex flex-col gap-3.5 px-[18px] pt-4 pb-6">
        <div className="flex items-center justify-between gap-2">
          <span className="code">{eyebrow}</span>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded-md border border-line bg-surface px-2 py-[3px] text-xs font-medium hover:bg-sunk"
          >
            Close
          </button>
        </div>
        <h2 id={titleId} className="text-[21px] leading-tight font-bold">
          {title}
        </h2>
        {children}
        {footer ? <div className="flex flex-wrap gap-2">{footer}</div> : null}
      </div>
    </dialog>
  );
}
