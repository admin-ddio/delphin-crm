/**
 * Top bar (PROVISIONAL look from the product owner's mockups, 2026-10-19): "Menu"
 * toggle below the shell breakpoint; on the right the notification bell slot and
 * the user menu (avatar, name, role; My account, Sign out). Dev builds also show
 * the API status. Replace with the pilot's top bar.
 */
import { ChevronDown, LogOut, UserRound } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';

import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Link } from '@/components/ui/Link';
import { useToast } from '@/components/ui/Toast';
import { useApiConnection } from '@/lib/api-status';
import { useAuth } from '@/lib/auth-context';
import { ROLE_LABELS, type RoleKey } from '@/lib/permissions';
import { cn } from '@/lib/utils';

/** Connection dot, after the demo's sync indicator. */
function ApiStatus() {
  const { isPending, isError } = useApiConnection();
  const label = isPending ? 'Connecting to API…' : isError ? 'API unreachable' : 'API connected';
  return (
    <span data-testid="api-status" className="flex items-center gap-1.5 text-xs text-muted">
      <span
        aria-hidden
        className={cn(
          'size-[7px] rounded-full',
          isPending ? 'bg-faint' : isError ? 'bg-bad' : 'bg-ok',
        )}
      />
      {label}
    </span>
  );
}

export interface TopbarProps {
  mobileOpen: boolean;
  onToggleMenu(): void;
  /** Notification bell (rendered by the layout once notifications exist). */
  bell?: ReactNode;
}

export function Topbar({ mobileOpen, onToggleMenu, bell }: TopbarProps) {
  const { actor, signOut } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const role = actor?.roles[0] as RoleKey | undefined;
  const roleLabel = role ? (ROLE_LABELS[role] ?? role) : null;

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (
        event instanceof KeyboardEvent
          ? event.key === 'Escape'
          : !menuRef.current?.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  async function onSignOut() {
    setOpen(false);
    try {
      await signOut();
      navigate('/login', { replace: true });
    } catch {
      toast({ title: "Couldn't sign out. Try again.", tone: 'error' });
    }
  }

  return (
    <header
      data-testid="app-topbar"
      className="sticky top-0 z-[5] flex flex-wrap items-center gap-3 bg-bg/85 px-4 py-3 backdrop-blur shell:px-8"
    >
      <Button
        size="sm"
        className="shell:hidden"
        aria-controls="app-sidebar"
        aria-expanded={mobileOpen}
        onClick={onToggleMenu}
      >
        Menu
      </Button>

      {import.meta.env.DEV ? <ApiStatus /> : null}

      <div className="ml-auto flex items-center gap-4">
        {bell}
        <div ref={menuRef} className="relative">
          <button
            type="button"
            data-testid="current-user"
            aria-haspopup="menu"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
            className="flex cursor-pointer items-center gap-3 rounded-xl py-1 pr-1 pl-1 text-left hover:bg-surface"
          >
            <Avatar name={actor?.fullName ?? '?'} size="sm" />
            <span className="max-shell:hidden">
              <b className="block text-sm leading-tight font-semibold text-fg">{actor?.fullName}</b>
              {roleLabel ? <span className="block text-xs text-muted">{roleLabel}</span> : null}
            </span>
            <ChevronDown aria-hidden className="size-4 text-muted" />
          </button>
          {open ? (
            <div
              role="menu"
              className="absolute right-0 z-20 mt-2 w-52 overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-lg"
            >
              <Link
                role="menuitem"
                to="/account"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-sunk"
              >
                <UserRound aria-hidden className="size-4 text-muted" />
                My account
              </Link>
              <button
                type="button"
                role="menuitem"
                onClick={() => void onSignOut()}
                className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-sm text-bad hover:bg-bad-soft"
              >
                <LogOut aria-hidden className="size-4" />
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
