/**
 * Dropdown menu (mockups: row "⋮" actions, the profile "Actions" button). Opens
 * below its trigger, closes on outside click / Escape / choosing an item;
 * arrow keys move between items. Items with `hidden` are skipped.
 */
import { MoreVertical } from 'lucide-react';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';

import { cn } from '@/lib/utils';

export interface MenuItem {
  label: string;
  onSelect?(): void;
  /** Navigate instead of calling onSelect. */
  to?: string;
  icon?: ReactNode;
  danger?: boolean;
  disabled?: boolean;
  hidden?: boolean;
}

export interface MenuProps {
  items: MenuItem[];
  /** Accessible name of the trigger, e.g. "Actions for Acme Ltd". */
  label: string;
  /** Custom trigger content; defaults to a "⋮" icon button. */
  trigger?: ReactNode;
  triggerClassName?: string;
  align?: 'left' | 'right';
}

export function Menu({ items, label, trigger, triggerClassName, align = 'right' }: MenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const navigate = useNavigate();
  const visible = items.filter((item) => !item.hidden);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent) {
        if (event.key === 'Escape') setOpen(false);
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          const buttons = [
            ...(ref.current?.querySelectorAll<HTMLButtonElement>(
              '[role="menuitem"]:not([disabled])',
            ) ?? []),
          ];
          const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
          const next = event.key === 'ArrowDown' ? index + 1 : index - 1;
          buttons[(next + buttons.length) % buttons.length]?.focus();
        }
      } else if (!ref.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    ref.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  if (!visible.length) return null;
  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        aria-label={trigger ? undefined : label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          trigger
            ? undefined
            : 'grid size-9 cursor-pointer place-items-center rounded-lg border border-line bg-surface text-muted hover:bg-sunk hover:text-fg',
          triggerClassName,
        )}
      >
        {trigger ?? <MoreVertical aria-hidden className="size-4" />}
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label={label}
          className={cn(
            'absolute z-30 mt-1.5 min-w-48 overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-lg',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {visible.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                if (item.to) navigate(item.to);
                else item.onSelect?.();
              }}
              className={cn(
                'flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-sm whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-45',
                item.danger ? 'text-bad hover:bg-bad-soft' : 'hover:bg-sunk',
              )}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
