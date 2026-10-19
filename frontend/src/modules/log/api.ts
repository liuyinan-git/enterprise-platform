import client from '@/core/api/client'
import type { ListResult } from '@/core/api/client'

export interface LogEventItem {
  id: number
  device_type: string
  device_id: string | null
  hostname: string | null
  event_category: string
  event_type: string
  severity: string
  security_label: string
  source_ip: string | null
  dest_ip: string | null
  username: string | null
  process_name: string | null
  event_time: string | null
}

export interface LogListParams {
  page?: number
  page_size?: number
  device_type?: string
  event_category?: string
  event_type?: string
  severity?: string
  source_ip?: string
  keyword?: string
  start?: string
  end?: string
}

export async function listLogs(params: LogListParams = {}): Promise<ListResult<LogEventItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<LogEventItem> }>(
    '/api/v1/logs',
    { params },
  )
  return data.data
}

export interface LogDetail {
  id: number
  device_type: string
  device_id: string | null
  hostname: string | null
  event_category: string
  event_type: string
  severity: string
  security_label: string
  source_ip: string | null
  dest_ip: string | null
  source_port: number | null
  dest_port: number | null
  username: string | null
  process_name: string | null
  event_time: string | null
  normalized_data: Record<string, unknown> | null
  raw: {
    raw_message: string | null
    raw_payload: Record<string, unknown> | null
    format_type: string | null
    source_id: string | null
    batch_id: string | null
    received_at: string | null
  } | null
}

export async function getLogDetail(id: number): Promise<LogDetail> {
  const { data } = await client.get<{ code: number; message: string; data: LogDetail }>(`/api/v1/logs/${id}`)
  return data.data
}

export interface CollectorItem {
  source_id: string
  batch_count: number
  log_count: number
  device_count: number
  received: number
  accepted: number
  rejected: number
  last_seen_at: string | null
  status: 'online' | 'offline'
}

export async function listCollectors(): Promise<CollectorItem[]> {
  const { data } = await client.get<{ code: number; message: string; data: { items: CollectorItem[] } }>(
    '/api/v1/collectors',
  )
  return data.data.items
}

export interface SecurityEventItem {
  id: number
  event_no: string
  rule_code: string | null
  event_title: string
  severity: string
  status: string
  source_ip: string | null
  device_id: string | null
  occurrence_count: number
  first_seen_at: string | null
  last_seen_at: string | null
  assigned_to: string | null
  resolution_note: string | null
  resolved_at: string | null
  summary: string | null
}

export interface EventListParams {
  page?: number
  page_size?: number
  status?: string
  severity?: string
}

export async function listEvents(params: EventListParams = {}): Promise<ListResult<SecurityEventItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<SecurityEventItem> }>(
    '/api/v1/events',
    { params },
  )
  return data.data
}

export interface AlertItem {
  alert_no: string
  channel: string
  receiver_key: string | null
  status: string
  attempt_count: number
  last_error: string | null
  sent_at: string | null
  created_at: string | null
}

export interface AiAnalysis {
  summary?: string
  risk_assessment?: string
  confidence?: number
  evidence?: string[]
  limitations?: string[]
  recommendations?: string[]
  needs_human_review?: boolean
  model?: string
  analyzed_at?: string
  status?: string
  error?: string
}

export interface EventDetail extends SecurityEventItem {
  evidence: LogEventItem[]
  alerts: AlertItem[]
  ai_analysis: AiAnalysis | null
}

export async function getEvent(eventNo: string): Promise<EventDetail> {
  const { data } = await client.get<{ code: number; message: string; data: EventDetail }>(
    `/api/v1/events/${eventNo}`,
  )
  return data.data
}

export async function patchEvent(
  eventNo: string,
  payload: { status?: string; assigned_to?: string; resolution_note?: string },
): Promise<SecurityEventItem> {
  const { data } = await client.patch<{ code: number; message: string; data: SecurityEventItem }>(
    `/api/v1/events/${eventNo}`,
    payload,
  )
  return data.data
}

export async function triggerAiAnalysis(eventNo: string): Promise<{ status: string; ai_analysis: AiAnalysis | null }> {
  const { data } = await client.post<{ code: number; message: string; data: { status: string; ai_analysis: AiAnalysis | null } }>(
    `/api/v1/events/${eventNo}/ai-analyze`,
  )
  return data.data
}

export interface AlertListParams {
  page?: number
  page_size?: number
  status?: string
  channel?: string
}

export async function listAlerts(params: AlertListParams = {}): Promise<ListResult<AlertItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<AlertItem> }>(
    '/api/v1/alerts',
    { params },
  )
  return data.data
}

export async function retryAlert(alertNo: string): Promise<AlertItem> {
  const { data } = await client.post<{ code: number; message: string; data: AlertItem }>(
    `/api/v1/alerts/${alertNo}/retry`,
  )
  return data.data
}

export interface RuleItem {
  id: number
  rule_code: string
  rule_name: string
  description: string | null
  rule_type: string
  severity: string
  enabled: boolean
  cooldown_seconds: number
  touser: string | null
  rule_config: Record<string, unknown>
  version: number
  updated_at: string | null
}

export interface RuleInput {
  rule_code: string
  rule_name: string
  description?: string
  rule_type?: string
  severity?: string
  enabled?: boolean
  cooldown_seconds?: number
  touser?: string
  rule_config?: Record<string, unknown>
}

export async function listRules(): Promise<RuleItem[]> {
  const { data } = await client.get<{ code: number; message: string; data: { items: RuleItem[] } }>(
    '/api/v1/rules',
  )
  return data.data.items
}

export async function createRule(payload: RuleInput): Promise<RuleItem> {
  const { data } = await client.post<{ code: number; message: string; data: RuleItem }>('/api/v1/rules', payload)
  return data.data
}

export async function updateRule(ruleCode: string, payload: Partial<RuleInput>): Promise<RuleItem> {
  const { data } = await client.put<{ code: number; message: string; data: RuleItem }>(
    `/api/v1/rules/${ruleCode}`,
    payload,
  )
  return data.data
}

export interface RuleSuggestionItem {
  id: number
  event_type: string
  rule_name: string
  severity: string
  threshold: number
  window_seconds: number
  group_by: string[] | null
  baseline_stats: Record<string, unknown> | null
  reason: string | null
  status: 'pending' | 'accepted' | 'ignored'
  created_at: string | null
}

export async function listRuleSuggestions(status?: string): Promise<RuleSuggestionItem[]> {
  const { data } = await client.get<{ code: number; message: string; data: { items: RuleSuggestionItem[]; total: number } }>(
    '/api/v1/rule-suggestions',
    { params: status ? { status } : {} },
  )
  return data.data.items
}

export async function acceptRuleSuggestion(id: number): Promise<{ rule_code: string }> {
  const { data } = await client.post<{ code: number; message: string; data: { rule_code: string } }>(
    `/api/v1/rule-suggestions/${id}/accept`,
  )
  return data.data
}

export async function ignoreRuleSuggestion(id: number): Promise<void> {
  await client.post(`/api/v1/rule-suggestions/${id}/ignore`)
}

export interface DeviceItem {
  id: number
  device_id: string
  device_name: string
  device_type: string
  hostname: string | null
  ip_address: string | null
  environment: string | null
  criticality: string
  expected_interval_seconds: number
  touser: string | null
  last_seen_at: string | null
  status: 'online' | 'offline'
  enabled: boolean
  attributes: Record<string, unknown> | null
}

export interface DeviceInput {
  device_id: string
  device_name: string
  device_type: string
  hostname?: string
  ip_address?: string
  environment?: string
  criticality?: string
  expected_interval_seconds?: number
  touser?: string
  enabled?: boolean
}

export interface DeviceListParams {
  page?: number
  page_size?: number
  device_type?: string
  enabled?: boolean
}

export async function listDevices(params: DeviceListParams = {}): Promise<ListResult<DeviceItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<DeviceItem> }>(
    '/api/v1/devices',
    { params },
  )
  return data.data
}

export async function registerDevice(payload: DeviceInput): Promise<DeviceItem> {
  const { data } = await client.post<{ code: number; message: string; data: DeviceItem }>(
    '/api/v1/devices',
    payload,
  )
  return data.data
}

export async function deleteDevice(deviceId: string): Promise<void> {
  await client.delete(`/api/v1/devices/${encodeURIComponent(deviceId)}`)
}
