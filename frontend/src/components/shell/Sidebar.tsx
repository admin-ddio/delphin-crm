/**
 * Left rail. PROVISIONAL markup modelled on the clickable demo (228 px, brand
 * block, uppercase group labels, badge counts, aria-current on the active item;
 * an off-canvas drawer below the 861 px `shell` breakpoint).
 * Replace with a verbatim port of the pilot's sidebar.
 */
import { NavLink } from 'react-router';

import { visibleNav, type NavBadgeCounts } from '@/components/shell/nav';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';

export interface SidebarProps {
  mobileOpen: boolean;
  onNavigate(): void;
  /** Wired to live counts when tasks and approvals are ported. */
  badgeCounts?: NavBadgeCounts;
}

export function Sidebar({ mobileOpen, onNavigate, badgeCounts = {} }: SidebarProps) {
  const { actor } = useAuth();
  const groups = visibleNav(actor?.permissions ?? []);

  return (
    <aside
      id="app-sidebar"
      data-testid="app-sidebar"
      aria-label="Modules"
      className={cn(
        'flex flex-col gap-3.5 overflow-y-auto border-r border-line bg-surface px-3 py-3.5',
        'fixed inset-y-0 left-0 z-[35] w-[250px] transition-transform',
        mobileOpen ? 'translate-x-0 shadow-[0_0_40px_rgb(0_0_0/.3)]' : '-translate-x-full',
        'shell:sticky shell:top-0 shell:z-auto shell:h-screen shell:w-auto shell:translate-x-0 shell:shadow-none',
      )}
    >
      <div className="flex items-center gap-2.5 px-1.5">
        <span
          aria-hidden
          className="grid size-[30px] place-items-center rounded-[7px] bg-accent font-bold text-on-accent"
        >
          D
        </span>
        <div>
          <b className="block text-sm leading-[1.1]">Delphin Digital</b>
          <small className="block text-[11px] text-muted">Agency console</small>
        </div>
      </div>

      <nav aria-label="Main" className="flex flex-col gap-3.5">
        {groups.map((group) => (
          <div key={group.label} className="flex flex-col gap-0.5">
            <p className="mb-1 px-2 text-[10.5px] font-semibold tracking-[.08em] text-faint uppercase">
              {group.label}
            </p>
            {group.items.map((item) => {
              const count = item.badge ? badgeCounts[item.badge] : undefined;
              return (
                <NavLink
                  key={item.href}
                  to={item.href}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center justify-between gap-2 rounded-md px-2 py-[7px] text-muted hover:bg-sunk hover:text-fg',
                      isActive && 'bg-accent-soft font-semibold text-accent-strong hover:bg-accent-soft hover:text-accent-strong',
                    )
                  }
                >
                  <span>{item.label}</span>
                  {count ? (
                    <span className="rounded-[10px] bg-accent px-1.5 font-mono text-[11px] font-medium text-on-accent">
                      {count}
                    </span>
                  ) : null}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
