import client from '@/core/api/client'
import type { ListResult } from '@/core/api/client'

export interface InstanceItem {
  id: number
  instance_code: string
  instance_name: string
  db_type: string
  host: string
  port: number
  database_name: string | null
  username: string | null
  password_masked: string
  environment: string | null
  enabled: boolean
  attributes: Record<string, unknown> | null
  health_status: string
  last_check_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface InstanceInput {
  instance_code: string
  instance_name: string
  db_type: string
  host: string
  port: number
  database_name?: string
  username?: string
  password?: string
  environment?: string
  enabled?: boolean
  attributes?: Record<string, unknown>
}

export async function listInstances(
  params: { page?: number; page_size?: number; db_type?: string; enabled?: boolean } = {},
): Promise<ListResult<InstanceItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<InstanceItem> }>(
    '/api/v1/database-instances',
    { params },
  )
  return data.data
}

export async function createInstance(payload: InstanceInput): Promise<InstanceItem> {
  const { data } = await client.post<{ code: number; message: string; data: InstanceItem }>(
    '/api/v1/database-instances',
    payload,
  )
  return data.data
}

export async function updateInstance(code: string, payload: Partial<InstanceInput>): Promise<InstanceItem> {
  const { data } = await client.put<{ code: number; message: string; data: InstanceItem }>(
    `/api/v1/database-instances/${encodeURIComponent(code)}`,
    payload,
  )
  return data.data
}

export async function deleteInstance(code: string): Promise<void> {
  await client.delete(`/api/v1/database-instances/${encodeURIComponent(code)}`)
}

export async function checkInstance(code: string): Promise<{ instance_code: string; health_status: string; latency_ms: number | null; detail: string }> {
  const { data } = await client.post<{ code: number; message: string; data: { instance_code: string; health_status: string; latency_ms: number | null; detail: string } }>(
    `/api/v1/database-instances/${encodeURIComponent(code)}/check`,
  )
  return data.data
}

export interface HealthItem {
  id: number
  instance_id: number
  instance_code: string | null
  check_type: string
  status: string
  latency_ms: number | null
  detail: Record<string, unknown> | null
  checked_at: string | null
}

export async function listHealth(
  params: { page?: number; page_size?: number; instance_code?: string } = {},
): Promise<ListResult<HealthItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<HealthItem> }>(
    '/api/v1/database-health',
    { params },
  )
  return data.data
}

export interface BackupItem {
  id: number
  instance_id: number
  instance_code: string | null
  backup_type: string
  status: string
  size: number
  started_at: string | null
  finished_at: string | null
  result: string | null
}

export interface BackupInput {
  instance_code: string
  backup_type?: string
  status?: string
  size?: number
  started_at?: string
  finished_at?: string
  result?: string
}

export async function listBackups(
  params: { page?: number; page_size?: number; instance_code?: string } = {},
): Promise<ListResult<BackupItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<BackupItem> }>(
    '/api/v1/database-backups',
    { params },
  )
  return data.data
}

export async function registerBackup(payload: BackupInput): Promise<{ id: number; instance_code: string; status: string }> {
  const { data } = await client.post<{ code: number; message: string; data: { id: number; instance_code: string; status: string } }>(
    '/api/v1/database-backups',
    payload,
  )
  return data.data
}
