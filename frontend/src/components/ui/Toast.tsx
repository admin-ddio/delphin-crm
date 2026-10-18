/**
 * Toast system. Visuals PROVISIONAL (clickable demo: dark pill bottom-right; errors red and
 * shown 6 s, others 3 s). The provider/hook API is scaffold infra; keep it when porting.
 */
import { X } from 'lucide-react';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

import { cn } from '@/lib/utils';

export type ToastTone = 'info' | 'error';

export interface ToastInput {
  title: string;
  description?: string;
  tone?: ToastTone;
  /** Defaults: 3000 ms, or 6000 ms for errors. 0 keeps it until dismissed. */
  durationMs?: number;
}

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastApi {
  toast(input: ToastInput): void;
  dismiss(id: number): void;
}

const ToastContext = createContext<ToastApi | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback(
    ({ title, description, tone = 'info', durationMs }: ToastInput) => {
      const id = nextId++;
      setItems((current) => [...current, { id, title, description, tone }]);
      const ms = durationMs ?? (tone === 'error' ? 6000 : 3000);
      if (ms > 0) window.setTimeout(() => dismiss(id), ms);
    },
    [dismiss],
  );

  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 bottom-4 z-40 flex max-w-[380px] flex-col gap-2"
      >
        {items.map((item) => (
          <div
            key={item.id}
            role={item.tone === 'error' ? 'alert' : 'status'}
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg px-3.5 py-2.5 text-[13px] shadow-[0_6px_20px_rgb(0_0_0/.2)]',
              item.tone === 'error' ? 'bg-bad text-white' : 'bg-fg text-bg',
            )}
          >
            <div className="flex-1">
              <p>{item.title}</p>
              {item.description ? <p className="mt-0.5 opacity-80">{item.description}</p> : null}
            </div>
            <button type="button" onClick={() => dismiss(item.id)} className="opacity-70 hover:opacity-100">
              <X aria-hidden className="size-4" />
              <span className="sr-only">Dismiss</span>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error('useToast() must be used inside <ToastProvider>');
  return api;
}
