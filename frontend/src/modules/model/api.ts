import client from '@/core/api/client'
import type { ListResult } from '@/core/api/client'

export interface ProviderItem {
  id: number
  provider_code: string
  provider_name: string
  provider_type: string
  base_url: string
  api_key_masked: string
  container_proxy_url: string | null
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
  container_proxy_url?: string
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

export interface DiscoveredContainer {
  name: string
  image: string
  state: string
  status: string
  ports: { private: number | null; public: number | null; type: string }[]
  suggested: boolean
}

export interface DiscoverResult {
  degraded: boolean
  total: number
  unregistered: number
  containers: DiscoveredContainer[]
}

export async function discoverModels(code: string): Promise<DiscoverResult> {
  const { data } = await client.post<{ code: number; message: string; data: DiscoverResult }>(
    `/api/v1/model-providers/${encodeURIComponent(code)}/discover`,
  )
  return data.data
}

export interface ModelItem {
  id: number
  model_code: string
  provider_id: number
  provider_code: string | null
  provider_name: string | null
  model_name: string
  service_type: string
  endpoint_url: string
  probe_method: string
  engine: string | null
  version: string | null
  context_window: number | null
  parameters: Record<string, unknown> | null
  enabled: boolean
  health_status: string
  consecutive_failures: number | null
  last_check_at: string | null
  metrics_metric: string | null
  // 容器实况（MODEL_CONTAINER_ENABLED 且代理可达时有值；null = unknown）
  container_status?: string | null
  container_status_text?: string | null
}

export interface ModelInput {
  model_code: string
  provider_code: string
  model_name: string
  service_type?: string
  endpoint_url?: string
  probe_method?: string
  engine?: string
  metrics_metric?: string
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

export interface ModelCheckResult {
  model_code: string
  health_status: string
  latency_ms: number | null
  detail: string
}

export async function checkModel(code: string): Promise<ModelCheckResult> {
  const { data } = await client.post<{ code: number; message: string; data: ModelCheckResult }>(
    `/api/v1/models/${encodeURIComponent(code)}/check`,
  )
  return data.data
}

export interface ModelHealthItem {
  id: number
  model_id: number
  model_code: string | null
  status: string
  latency_ms: number | null
  message: string | null
  checked_at: string | null
}

export async function getModelHealth(
  params: { page?: number; page_size?: number; model_code?: string; status?: string } = {},
): Promise<ListResult<ModelHealthItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<ModelHealthItem> }>(
    '/api/v1/model-health',
    { params },
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

export interface ConsumerItem {
  id: number
  consumer_code: string
  consumer_name: string
  identity_type: string
  identifier: string | null
  contact: string | null
  remark: string | null
  evidence: string | null
  model_codes: string[]
  created_at: string | null
  updated_at: string | null
}

export interface ConsumerInput {
  consumer_code: string
  consumer_name: string
  identity_type?: string
  identifier?: string
  contact?: string
  remark?: string
  evidence?: string
  model_codes?: string[]
}

export async function listModelConsumers(
  params: { page?: number; page_size?: number; model_code?: string; identity_type?: string } = {},
): Promise<ListResult<ConsumerItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<ConsumerItem> }>(
    '/api/v1/model-consumers',
    { params },
  )
  return data.data
}

export async function createModelConsumer(payload: ConsumerInput): Promise<ConsumerItem> {
  const { data } = await client.post<{ code: number; message: string; data: ConsumerItem }>(
    '/api/v1/model-consumers',
    payload,
  )
  return data.data
}

export async function updateModelConsumer(
  code: string,
  payload: Partial<ConsumerInput>,
): Promise<ConsumerItem> {
  const { data } = await client.put<{ code: number; message: string; data: ConsumerItem }>(
    `/api/v1/model-consumers/${encodeURIComponent(code)}`,
    payload,
  )
  return data.data
}

export async function deleteModelConsumer(code: string): Promise<void> {
  await client.delete(`/api/v1/model-consumers/${encodeURIComponent(code)}`)
}

export interface ConsumerUsageSummaryItem {
  consumer_id: number
  consumer_code: string | null
  consumer_name: string | null
  identity_type: string | null
  call_count: number
  error_count: number
  success_rate: number
  last_seen_at: string | null
  model_codes: string[]
}

export async function listConsumerUsageSummary(
  params: { consumer_code?: string; model_code?: string } = {},
): Promise<ConsumerUsageSummaryItem[]> {
  const { data } = await client.get<{ code: number; message: string; data: ConsumerUsageSummaryItem[] }>(
    '/api/v1/model-consumer-usages',
    { params: { ...params, rollup: 'consumer' } },
  )
  return data.data
}

export interface ModelAlertItem {
  id: number
  alert_no: string
  model_id: number
  model_code: string | null
  alert_type: string
  channel: string
  receiver_key: string | null
  message_content: string | null
  status: string
  attempt_count: number
  next_retry_at: string | null
  sent_at: string | null
  resolved_at: string | null
  last_error: string | null
  created_at: string | null
}

export interface ModelAlertRetryResult {
  status: string
  attempt_count: number
  last_error: string | null
}

export async function listModelAlerts(
  params: { page?: number; page_size?: number; model_code?: string; alert_type?: string; alert_status?: string } = {},
): Promise<ListResult<ModelAlertItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<ModelAlertItem> }>(
    '/api/v1/model-alerts',
    { params },
  )
  return data.data
}

export async function retryModelAlert(alertNo: string): Promise<ModelAlertRetryResult> {
  const { data } = await client.post<{ code: number; message: string; data: ModelAlertRetryResult }>(
    `/api/v1/model-alerts/${encodeURIComponent(alertNo)}/retry`,
  )
  return data.data
}
