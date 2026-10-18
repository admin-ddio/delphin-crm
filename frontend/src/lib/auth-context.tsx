/**
 * Who is signed in (ADR-0009).
 *
 * Sign-in: Firebase checks the password → the e-mail must be verified → the
 * Firebase ID token is exchanged for our HttpOnly session cookie
 * (POST /api/v1/auth/session). From then on GET /api/v1/auth/me is the source of
 * truth, cached by TanStack Query; Firebase's in-memory state is discarded.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  sendEmailVerification,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
} from 'firebase/auth';
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';

import type { components } from '@/api/schema';
import { api, unwrap } from '@/lib/api-client';
import { firebaseAuth, signInUrl } from '@/lib/firebase';
import type { Permission } from '@/lib/permissions';

export interface Actor {
  id: string;
  email: string;
  fullName: string;
  roles: readonly string[];
  permissions: readonly Permission[];
}

export type AuthStatus = 'unknown' | 'anonymous' | 'authenticated';

/** Thrown by signIn when the password is right but the e-mail isn't verified yet. */
export class EmailNotVerifiedError extends Error {
  constructor() {
    super('Verify your e-mail address before signing in. Check your inbox for the link.');
    this.name = 'EmailNotVerifiedError';
  }
}

export interface AuthState {
  status: AuthStatus;
  actor: Actor | null;
  signIn(email: string, password: string): Promise<Actor>;
  signOut(): Promise<void>;
  /** Re-send the verification e-mail after signIn threw EmailNotVerifiedError. */
  resendVerification(): Promise<void>;
}

export type CurrentUserDto = components['schemas']['CurrentUser'];

export const ME_QUERY_KEY = ['auth', 'me'] as const;

export function toActor(user: CurrentUserDto): Actor {
  return {
    id: user.id,
    email: user.email,
    fullName: user.full_name,
    roles: user.roles,
    permissions: user.permissions,
  };
}

async function fetchCurrentUser(): Promise<Actor | null> {
  const result = await api.GET('/api/v1/auth/me');
  if (result.response.status === 401) return null;
  return toActor(unwrap(result));
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({
  children,
  initialActor,
}: {
  children: ReactNode;
  /** Tests only: skip the /auth/me request and use this actor (or null = signed out). */
  initialActor?: Actor | null;
}) {
  const queryClient = useQueryClient();
  const preset = initialActor !== undefined;
  const me = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: fetchCurrentUser,
    enabled: !preset,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const signIn = useCallback(
    async (email: string, password: string) => {
      const auth = firebaseAuth();
      const credential = await signInWithEmailAndPassword(auth, email, password);
      if (!credential.user.emailVerified) {
        // Keep the Firebase user in memory so resendVerification() can use it.
        throw new EmailNotVerifiedError();
      }
      try {
        const idToken = await credential.user.getIdToken();
        const actor = toActor(
          unwrap(await api.POST('/api/v1/auth/session', { body: { id_token: idToken } })),
        );
        queryClient.setQueryData(ME_QUERY_KEY, actor);
        return actor;
      } finally {
        // Our cookie is the session now; drop Firebase's copy.
        await firebaseSignOut(auth);
      }
    },
    [queryClient],
  );

  const resendVerification = useCallback(async () => {
    const auth = firebaseAuth();
    if (!auth.currentUser) throw new Error('Sign in again to re-send the verification e-mail.');
    await sendEmailVerification(auth.currentUser, { url: signInUrl() });
  }, []);

  const signOut = useCallback(async () => {
    const { response } = await api.POST('/api/v1/auth/logout');
    // 401 = the session had already ended; either way we're signed out now.
    if (!response.ok && response.status !== 401) {
      throw new Error(`Sign-out failed (${response.status})`);
    }
    await firebaseSignOut(firebaseAuth());
    // Update the live `me` query in place (clear() would detach its observer and leave
    // the old user on screen), then drop every other cached response of that user.
    queryClient.setQueryData(ME_QUERY_KEY, null);
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_QUERY_KEY[0] });
  }, [queryClient]);

  const value = useMemo<AuthState>(() => {
    const actor = preset ? initialActor : (me.data ?? null);
    let status: AuthStatus;
    if (preset) status = actor ? 'authenticated' : 'anonymous';
    else if (me.isPending) status = 'unknown';
    else status = actor ? 'authenticated' : 'anonymous';
    return { status, actor, signIn, signOut, resendVerification };
  }, [preset, initialActor, me.data, me.isPending, signIn, signOut, resendVerification]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error('useAuth() must be used inside <AuthProvider>');
  return state;
}
