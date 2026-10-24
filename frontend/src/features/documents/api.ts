/** Typed hooks for client documents. Uploads are multipart (see uploadDocument). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import { clientsKeys } from '@/features/clients/api';
import { onboardingKeys } from '@/features/onboarding/api';
import {
  api,
  ApiError,
  CSRF_COOKIE,
  CSRF_HEADER,
  readCookie,
  unwrap,
  type ApiErrorBody,
} from '@/lib/api-client';

export type ClientDocuments = components['schemas']['ClientDocuments'];
export type DocumentItem = components['schemas']['DocumentOut'];
export type Folder = components['schemas']['FolderOut'];

export const documentsKeys = {
  client: (clientId: string) => ['documents', 'client', clientId] as const,
};

export function useClientDocuments(clientId: string) {
  return useQuery({
    queryKey: documentsKeys.client(clientId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/documents/clients/{client_id}', {
          params: { path: { client_id: clientId } },
        }),
      ),
  });
}

/** multipart/form-data upload: openapi-fetch does not build it, so this posts directly. */
export async function uploadDocument(
  clientId: string,
  file: File,
  folder: { id?: string; name?: string },
  description?: string,
): Promise<DocumentItem> {
  const form = new FormData();
  form.append('file', file);
  if (folder.id) form.append('folder_id', folder.id);
  if (folder.name) form.append('folder', folder.name);
  if (description) form.append('description', description);
  const token = readCookie(CSRF_COOKIE);
  // eslint-disable-next-line no-restricted-globals -- multipart upload (see doc comment)
  const response = await fetch(`/api/v1/documents/clients/${clientId}`, {
    method: 'POST',
    body: form,
    credentials: 'same-origin',
    headers: token ? { [CSRF_HEADER]: decodeURIComponent(token) } : {},
  });
  const body = (await response.json().catch(() => null)) as unknown;
  if (!response.ok) {
    const envelope = body as { error?: ApiErrorBody } | null;
    throw new ApiError(
      response.status,
      envelope?.error ?? {
        code: 'upload_failed',
        message: 'The upload failed. Try again.',
        details: {},
        request_id: null,
      },
    );
  }
  return body as DocumentItem;
}

export function useDocumentAction(clientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (run: () => Promise<unknown>) => run(),
    onSuccess: () => {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: documentsKeys.client(clientId) }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.detail(clientId) }),
        queryClient.invalidateQueries({ queryKey: clientsKeys.activity(clientId) }),
      ]);
    },
  });
}

export const documentsApi = {
  move: async (id: string, folderId: string) =>
    unwrap(
      await api.PATCH('/api/v1/documents/{document_id}', {
        params: { path: { document_id: id } },
        body: { folder_id: folderId },
      }),
    ),
  remove: async (id: string) => {
    const { response, error } = await api.DELETE('/api/v1/documents/{document_id}', {
      params: { path: { document_id: id } },
    });
    if (!response.ok) unwrap({ error, response });
  },
  createFolder: async (clientId: string, name: string) =>
    unwrap(
      await api.POST('/api/v1/documents/clients/{client_id}/folders', {
        params: { path: { client_id: clientId } },
        body: { name },
      }),
    ),
  deleteFolder: async (folderId: string) =>
    unwrap(
      await api.DELETE('/api/v1/documents/folders/{folder_id}', {
        params: { path: { folder_id: folderId } },
      }),
    ),
};
