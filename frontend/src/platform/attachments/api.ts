import client from '@/core/api/client'
import type { ListResult } from '@/core/api/client'

export interface AttachmentItem {
  id: number
  filename: string
  stored_name: string
  uploader: string | null
  category: string
  content_type: string
  size: number
  created_at: string | null
}

export async function listFiles(
  params: { page?: number; page_size?: number; category?: string } = {},
): Promise<ListResult<AttachmentItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<AttachmentItem> }>(
    '/api/v1/files',
    { params },
  )
  return data.data
}

export async function uploadFile(file: File, uploader?: string): Promise<AttachmentItem> {
  const form = new FormData()
  form.append('file', file)
  if (uploader) form.append('uploader', uploader)
  const { data } = await client.post<{ code: number; message: string; data: AttachmentItem }>('/api/v1/files', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.data
}

export async function deleteFile(id: number): Promise<void> {
  await client.delete(`/api/v1/files/${id}`)
}

export function fileDownloadUrl(id: number): string {
  return `/api/v1/files/${id}/download`
}

export function filePreviewUrl(id: number): string {
  return `/api/v1/files/${id}/preview`
}
