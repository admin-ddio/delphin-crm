/** Top-bar bell (mockups): unread count badge; the panel lists pending actions. */
import { Bell } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';

import { EmptyState } from '@/components/ui/EmptyState';
import { useMarkRead, useNotifications } from '@/features/notifications/api';
import { timeAgo } from '@/lib/format';
import { cn } from '@/lib/utils';

export function NotificationBell() {
  const notifications = useNotifications();
  const markRead = useMarkRead();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const unread = notifications.data?.unread ?? 0;

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (
        event instanceof KeyboardEvent
          ? event.key === 'Escape'
          : !ref.current?.contains(event.target as Node)
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

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        data-testid="notification-bell"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="relative grid size-10 cursor-pointer place-items-center rounded-full text-fg hover:bg-surface"
      >
        <Bell aria-hidden className="size-5" />
        {unread ? (
          <span className="absolute top-1 right-1 grid min-w-4 place-items-center rounded-full bg-bad px-1 text-[10px] leading-4 font-bold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        ) : null}
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 z-30 mt-2 w-[min(380px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-line bg-surface shadow-lg"
        >
          <div className="flex items-center justify-between border-b border-line-soft px-4 py-3">
            <b className="text-sm">Notifications</b>
            {unread ? (
              <button
                type="button"
                className="cursor-pointer text-xs font-medium text-accent hover:underline"
                onClick={() => markRead.mutate('all')}
              >
                Mark all as read
              </button>
            ) : null}
          </div>
          <ul className="max-h-[420px] overflow-y-auto">
            {notifications.data?.items.length ? (
              notifications.data.items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    className={cn(
                      'flex w-full cursor-pointer gap-3 border-b border-line-soft px-4 py-3 text-left hover:bg-sunk',
                      !n.read && 'bg-accent-soft/40',
                    )}
                    onClick={() => {
                      if (!n.read) markRead.mutate(n.id);
                      setOpen(false);
                      if (n.link) navigate(n.link);
                    }}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        'mt-1.5 size-2 shrink-0 rounded-full',
                        n.read ? 'bg-transparent' : 'bg-accent',
                      )}
                    />
                    <span className="min-w-0">
                      <span className="block text-[13px] font-medium text-fg">{n.title}</span>
                      {n.body ? <span className="block text-xs text-muted">{n.body}</span> : null}
                      <span className="block text-[11.5px] text-faint">
                        {timeAgo(n.created_at)}
                      </span>
                    </span>
                  </button>
                </li>
              ))
            ) : (
              <li>
                <EmptyState
                  title="You're all caught up"
                  description="Pending actions appear here."
                />
              </li>
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
