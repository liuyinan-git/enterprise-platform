import client from '@/core/api/client'
import type { ListResult } from '@/core/api/client'

export interface ProviderItem {
  id: number
  provider_code: string
  provider_name: string
  provider_type: string
  base_url: string
  api_key_masked: string
  enabled: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ProviderInput {
  provider_code: string
  provider_name: string
  provider_type?: string
  base_url?: string
  api_key?: string
  enabled?: boolean
}

export async function listProviders(
  params: { page?: number; page_size?: number; provider_type?: string } = {},
): Promise<ListResult<ProviderItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<ProviderItem> }>(
    '/api/v1/model-providers',
    { params },
  )
  return data.data
}

export async function createProvider(payload: ProviderInput): Promise<ProviderItem> {
  const { data } = await client.post<{ code: number; message: string; data: ProviderItem }>(
    '/api/v1/model-providers',
    payload,
  )
  return data.data
}

export async function updateProvider(code: string, payload: Partial<ProviderInput>): Promise<ProviderItem> {
  const { data } = await client.put<{ code: number; message: string; data: ProviderItem }>(
    `/api/v1/model-providers/${encodeURIComponent(code)}`,
    payload,
  )
  return data.data
}

export async function deleteProvider(code: string): Promise<void> {
  await client.delete(`/api/v1/model-providers/${encodeURIComponent(code)}`)
}

export interface ModelItem {
  id: number
  model_code: string
  provider_id: number
  provider_code: string | null
  provider_name: string | null
  model_name: string
  version: string | null
  context_window: number | null
  parameters: Record<string, unknown> | null
  enabled: boolean
  health_status: string
  last_check_at: string | null
}

export interface ModelInput {
  model_code: string
  provider_code: string
  model_name: string
  version?: string
  context_window?: number
  parameters?: Record<string, unknown>
  enabled?: boolean
}

export async function listModels(
  params: { page?: number; page_size?: number; provider_code?: string; enabled?: boolean } = {},
): Promise<ListResult<ModelItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<ModelItem> }>(
    '/api/v1/models',
    { params },
  )
  return data.data
}

export async function createModel(payload: ModelInput): Promise<ModelItem> {
  const { data } = await client.post<{ code: number; message: string; data: ModelItem }>('/api/v1/models', payload)
  return data.data
}

export async function updateModel(code: string, payload: Partial<ModelInput>): Promise<ModelItem> {
  const { data } = await client.put<{ code: number; message: string; data: ModelItem }>(
    `/api/v1/models/${encodeURIComponent(code)}`,
    payload,
  )
  return data.data
}

export async function deleteModel(code: string): Promise<void> {
  await client.delete(`/api/v1/models/${encodeURIComponent(code)}`)
}

export async function checkModel(code: string): Promise<{ model_code: string; health_status: string; detail: string }> {
  const { data } = await client.post<{ code: number; message: string; data: { model_code: string; health_status: string; detail: string } }>(
    `/api/v1/models/${encodeURIComponent(code)}/check`,
  )
  return data.data
}

export interface UsageItem {
  id: number
  model_id: number
  model_code: string | null
  call_count: number
  input_tokens: number
  output_tokens: number
  recorded_day: string
}

export async function listUsages(
  params: { page?: number; page_size?: number; model_code?: string } = {},
): Promise<ListResult<UsageItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<UsageItem> }>(
    '/api/v1/model-usages',
    { params },
  )
  return data.data
}

export async function recordUsage(payload: {
  model_code: string
  call_count?: number
  input_tokens?: number
  output_tokens?: number
  recorded_day: string
}): Promise<{ id: number; model_code: string; recorded_day: string }> {
  const { data } = await client.post<{ code: number; message: string; data: { id: number; model_code: string; recorded_day: string } }>(
    '/api/v1/model-usages',
    payload,
  )
  return data.data
}
