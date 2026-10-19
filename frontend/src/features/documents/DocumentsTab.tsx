/**
 * Screen 9 – Documents (product spec): folders (Contracts, SEO Files, Brand Assets,
 * Reports, Other + custom), drag & drop upload (10 MB), access-checked downloads,
 * move and delete. Files are private: downloads go through the API with the session.
 */
import {
  Download,
  File as FileIcon,
  FileImage,
  FileSpreadsheet,
  FileText,
  Folder as FolderIcon,
  FolderPlus,
  Trash2,
  Upload,
} from 'lucide-react';
import { useRef, useState } from 'react';

import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { TextField } from '@/components/ui/Field';
import { Menu } from '@/components/ui/Menu';
import { useToast } from '@/components/ui/Toast';
import {
  documentsApi,
  uploadDocument,
  useClientDocuments,
  useDocumentAction,
  type DocumentItem,
} from '@/features/documents/api';
import { ApiError } from '@/lib/api-client';
import { formatBytes, formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function iconFor(doc: DocumentItem) {
  if (doc.content_type.startsWith('image/')) return FileImage;
  if (/sheet|excel|csv/.test(doc.content_type)) return FileSpreadsheet;
  if (/pdf|word|text/.test(doc.content_type)) return FileText;
  return FileIcon;
}

export function DocumentsTab({ clientId }: { clientId: string }) {
  const documents = useClientDocuments(clientId);
  const action = useDocumentAction(clientId);
  const { toast } = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [folderId, setFolderId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(0);
  const [newFolder, setNewFolder] = useState<string | null>(null);
  const data = documents.data;
  if (documents.isPending) return <EmptyState title="Loading documents…" />;
  if (!data)
    return (
      <EmptyState title="Couldn't load documents" description="Reload the page to try again." />
    );

  const folder = data.folders.find((f) => f.id === folderId) ?? null;
  const shown = folder ? data.documents.filter((d) => d.folder_id === folder.id) : data.documents;
  const target = folder ?? data.folders.find((f) => f.name === 'Other') ?? data.folders[0];
  const maxMb = Math.round(data.max_upload_bytes / (1024 * 1024));

  const upload = async (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      setUploading((n) => n + 1);
      try {
        await action.mutateAsync(() => uploadDocument(clientId, file, { id: target?.id }));
        toast({ title: `${file.name} uploaded to ${target?.name}.` });
      } catch (error) {
        toast({ title: `${file.name}: ${errorMessage(error)}`, tone: 'error' });
      } finally {
        setUploading((n) => n - 1);
      }
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Documents</h2>
          <p className="mt-1 text-muted">
            Contracts, SEO files and brand assets for this client. Files are private.
          </p>
        </div>
        {data.permissions.upload ? (
          <Button variant="primary" onClick={() => input.current?.click()}>
            <Upload aria-hidden className="size-4" />
            Upload
          </Button>
        ) : null}
      </div>
      <div className="grid items-start gap-5 lg:grid-cols-[240px_1fr]">
        <Card className="p-3">
          <nav aria-label="Folders">
            <ul className="flex flex-col gap-0.5">
              <li>
                <button
                  type="button"
                  aria-current={folderId === null ? 'true' : undefined}
                  onClick={() => setFolderId(null)}
                  className={cn(
                    'flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm',
                    folderId === null
                      ? 'bg-accent-soft font-semibold text-accent'
                      : 'hover:bg-sunk',
                  )}
                >
                  <FolderIcon aria-hidden className="size-4" />
                  <span className="flex-1">All documents</span>
                  <span className="text-xs text-muted">{data.documents.length}</span>
                </button>
              </li>
              {data.folders.map((f) => (
                <li key={f.id} className="group flex items-center">
                  <button
                    type="button"
                    aria-current={folderId === f.id ? 'true' : undefined}
                    onClick={() => setFolderId(f.id)}
                    className={cn(
                      'flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm',
                      folderId === f.id
                        ? 'bg-accent-soft font-semibold text-accent'
                        : 'hover:bg-sunk',
                    )}
                  >
                    <FolderIcon aria-hidden className="size-4" />
                    <span className="flex-1">{f.name}</span>
                    <span className="text-xs text-muted">{f.count}</span>
                  </button>
                  {!f.is_system && data.permissions.manage_folders && !f.count ? (
                    <button
                      type="button"
                      aria-label={`Delete folder ${f.name}`}
                      className="ml-1 cursor-pointer text-faint hover:text-bad"
                      onClick={async () => {
                        try {
                          await action.mutateAsync(() => documentsApi.deleteFolder(f.id));
                          if (folderId === f.id) setFolderId(null);
                        } catch (error) {
                          toast({ title: errorMessage(error), tone: 'error' });
                        }
                      }}
                    >
                      <Trash2 aria-hidden className="size-3.5" />
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </nav>
          {data.permissions.manage_folders ? (
            <Button size="sm" className="mt-3 w-full" onClick={() => setNewFolder('')}>
              <FolderPlus aria-hidden className="size-3.5" />
              New folder
            </Button>
          ) : null}
        </Card>

        <div className="flex min-w-0 flex-col gap-4">
          {data.permissions.upload ? (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                void upload(e.dataTransfer.files);
              }}
              className={cn(
                'flex flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-7 text-center',
                dragging ? 'border-accent bg-accent-soft' : 'border-accent/40 bg-accent-soft/30',
              )}
            >
              <Upload aria-hidden className="size-6 text-accent" />
              <span className="text-sm">
                {uploading ? `Uploading ${uploading} file(s)…` : 'Drag & drop files here or '}
                {!uploading ? (
                  <button
                    type="button"
                    className="link underline"
                    onClick={() => input.current?.click()}
                  >
                    browse
                  </button>
                ) : null}
              </span>
              <span className="text-xs text-muted">
                Into “{target?.name}” · PDF, Office, images, CSV, ZIP (Max. {maxMb}MB)
              </span>
              <input
                ref={input}
                type="file"
                multiple
                aria-label="Upload documents"
                className="sr-only"
                accept={data.allowed_extensions.map((e) => `.${e}`).join(',')}
                onChange={(e) => {
                  if (e.target.files) void upload(e.target.files);
                  e.target.value = '';
                }}
              />
            </div>
          ) : null}
          <Card className="overflow-hidden">
            {shown.length ? (
              <div className="overflow-x-auto">
                <table className="table" data-testid="documents-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Folder</th>
                      <th>Size</th>
                      <th>Uploaded by</th>
                      <th>Date</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((doc) => {
                      const Icon = iconFor(doc);
                      return (
                        <tr key={doc.id}>
                          <td>
                            <a
                              className="flex items-center gap-3 font-medium hover:text-accent"
                              href={doc.download_url}
                            >
                              <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent">
                                <Icon aria-hidden className="size-4" />
                              </span>
                              <span className="min-w-0">
                                <span className="block truncate">{doc.filename}</span>
                                {doc.description ? (
                                  <span className="block text-xs text-muted">
                                    {doc.description}
                                  </span>
                                ) : null}
                              </span>
                            </a>
                          </td>
                          <td>{data.folders.find((f) => f.id === doc.folder_id)?.name}</td>
                          <td className="whitespace-nowrap text-muted">{formatBytes(doc.size)}</td>
                          <td>
                            {doc.uploaded_by ? (
                              <span className="flex items-center gap-2">
                                <Avatar name={doc.uploaded_by.full_name} size="xs" />
                                {doc.uploaded_by.full_name}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="whitespace-nowrap text-muted">
                            {formatDate(doc.uploaded_at)}
                          </td>
                          <td className="text-right">
                            <span className="inline-flex items-center gap-2">
                              <a
                                href={doc.download_url}
                                aria-label={`Download ${doc.filename}`}
                                className="grid size-9 place-items-center rounded-lg border border-line bg-surface text-muted hover:text-fg"
                              >
                                <Download aria-hidden className="size-4" />
                              </a>
                              <Menu
                                label={`Actions for ${doc.filename}`}
                                items={[
                                  ...data.folders
                                    .filter((f) => f.id !== doc.folder_id)
                                    .map((f) => ({
                                      label: `Move to ${f.name}`,
                                      hidden: !doc.can_delete,
                                      onSelect: async () => {
                                        try {
                                          await action.mutateAsync(() =>
                                            documentsApi.move(doc.id, f.id),
                                          );
                                        } catch (error) {
                                          toast({ title: errorMessage(error), tone: 'error' });
                                        }
                                      },
                                    })),
                                  {
                                    label: 'Delete',
                                    danger: true,
                                    hidden: !doc.can_delete,
                                    onSelect: async () => {
                                      if (
                                        !window.confirm(
                                          `Delete ${doc.filename}? This can't be undone.`,
                                        )
                                      )
                                        return;
                                      try {
                                        await action.mutateAsync(() => documentsApi.remove(doc.id));
                                        toast({ title: `${doc.filename} deleted.` });
                                      } catch (error) {
                                        toast({ title: errorMessage(error), tone: 'error' });
                                      }
                                    },
                                  },
                                ]}
                              />
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={FileText}
                title={folder ? `No documents in ${folder.name}` : 'No documents yet'}
              />
            )}
          </Card>
        </div>
      </div>
      <Dialog
        open={newFolder !== null}
        onClose={() => setNewFolder(null)}
        title="New folder"
        footer={
          <>
            <Button onClick={() => setNewFolder(null)}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!newFolder?.trim()}
              onClick={async () => {
                try {
                  await action.mutateAsync(() =>
                    documentsApi.createFolder(clientId, newFolder ?? ''),
                  );
                  setNewFolder(null);
                } catch (error) {
                  toast({ title: errorMessage(error), tone: 'error' });
                }
              }}
            >
              Create folder
            </Button>
          </>
        }
      >
        <TextField
          label="Folder name"
          maxLength={60}
          value={newFolder ?? ''}
          onChange={(e) => setNewFolder(e.target.value)}
        />
      </Dialog>
    </div>
  );
}
