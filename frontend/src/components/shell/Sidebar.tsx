/**
 * Left rail (PROVISIONAL look from the product owner's mockups, 2026-10-19):
 * dark navy, brand block, icons, purple active item, badge counts, aria-current on
 * the active item; an off-canvas drawer below the 861 px `shell` breakpoint.
 * Replace with a verbatim port of the pilot's sidebar.
 */
import {
  Activity,
  BadgeCheck,
  Building2,
  ClipboardCheck,
  FolderKanban,
  LayoutDashboard,
  Network,
  Repeat,
  ShieldCheck,
  SquareCheckBig,
  UserRound,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import { NavLink } from 'react-router';

import { visibleNav, type NavBadgeCounts } from '@/components/shell/nav';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';

/** Icons stay out of nav.ts so the nav model remains plain data. */
const ICONS: Record<string, LucideIcon> = {
  '/dashboard': LayoutDashboard,
  '/clients': Users,
  '/onboarding': ClipboardCheck,
  '/projects': FolderKanban,
  '/tasks': SquareCheckBig,
  '/approvals': BadgeCheck,
  '/services': Repeat,
  '/team/employees': UserRound,
  '/team/teams': Network,
  '/finance': Wallet,
  '/team': ShieldCheck,
  '/activity': Activity,
};

export interface SidebarProps {
  mobileOpen: boolean;
  onNavigate(): void;
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
        'flex flex-col gap-5 overflow-y-auto bg-rail px-3 py-5 text-rail-fg',
        'fixed inset-y-0 left-0 z-[35] w-[250px] transition-transform',
        mobileOpen ? 'translate-x-0 shadow-[0_0_40px_rgb(0_0_0/.4)]' : '-translate-x-full',
        'shell:sticky shell:top-0 shell:z-auto shell:h-screen shell:w-auto shell:translate-x-0 shell:shadow-none',
      )}
    >
      <div className="flex items-center gap-2.5 px-2">
        <span
          aria-hidden
          className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#4424cf] text-white shadow-[0_4px_14px_rgb(85_52_232/.45)]"
        >
          <Building2 className="size-5" />
        </span>
        <div>
          <b className="block text-[15px] leading-[1.1] font-bold text-white">Delphin Digital</b>
          <small className="block text-[11px] text-rail-muted">Agency console</small>
        </div>
      </div>

      <nav aria-label="Main" className="flex flex-col gap-4">
        {groups.map((group) => (
          <div key={group.label} className="flex flex-col gap-1">
            <p className="mb-0.5 px-3 text-[10.5px] font-semibold tracking-[.1em] text-rail-muted uppercase">
              {group.label}
            </p>
            {group.items.map((item) => {
              const count = item.badge ? badgeCounts[item.badge] : undefined;
              const Icon = ICONS[item.href];
              return (
                <NavLink
                  key={item.href}
                  to={item.href}
                  end={item.href === '/team'}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13.5px] font-medium transition-colors',
                      isActive
                        ? 'bg-gradient-to-r from-[#5534e8] to-[#6d4cff] text-white shadow-[0_6px_16px_rgb(85_52_232/.35)]'
                        : 'hover:bg-rail-hover hover:text-white',
                    )
                  }
                >
                  {Icon ? <Icon aria-hidden className="size-[18px] shrink-0" /> : null}
                  <span className="flex-1">{item.label}</span>
                  {count ? (
                    <span className="rounded-full bg-white/15 px-2 text-[11px] font-semibold text-white">
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
