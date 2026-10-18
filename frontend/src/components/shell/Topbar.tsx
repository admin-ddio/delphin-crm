/**
 * Top bar. PROVISIONAL markup modelled on the clickable demo: "Menu" toggle
 * (below the shell breakpoint) on the left; on the right, the signed-in user
 * (links to /account) and Sign out. Dev builds also show the API status.
 * Replace with the pilot's top bar.
 */
import { useNavigate } from 'react-router';

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
        className={cn('size-[7px] rounded-full', isPending ? 'bg-faint' : isError ? 'bg-bad' : 'bg-ok')}
      />
      {label}
    </span>
  );
}

export interface TopbarProps {
  mobileOpen: boolean;
  onToggleMenu(): void;
}

export function Topbar({ mobileOpen, onToggleMenu }: TopbarProps) {
  const { actor, signOut } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const role = actor?.roles[0] as RoleKey | undefined;

  async function onSignOut() {
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
      className="sticky top-0 z-[5] flex flex-wrap items-center gap-2.5 border-b border-line bg-surface px-4 py-2.5"
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

      <div className="ml-auto flex items-center gap-2.5 text-xs text-muted">
        <Link to="/account" className="hover:text-fg" data-testid="current-user">
          <b className="font-medium text-fg">{actor?.fullName}</b>
          {role ? <span className="max-shell:hidden"> · {ROLE_LABELS[role] ?? role}</span> : null}
        </Link>
        <Button size="sm" onClick={onSignOut}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
