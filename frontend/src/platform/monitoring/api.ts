import client from '@/core/api/client'

export interface SystemOverview {
  raw_total: number
  raw_pending: number
  raw_failed: number
  event_total: number
  batch_total: number
  device_total: number
  security_event_total: number
  alert_total: number
  task_pending: number
  task_running: number
  task_failed: number
}

export async function getSystemOverview(): Promise<SystemOverview> {
  const { data } = await client.get<{ code: number; message: string; data: SystemOverview }>(
    '/api/v1/system/overview',
  )
  return data.data
}

export interface ResetResult {
  security_event_log: number
  alert_record: number
  security_event: number
  log_event: number
  log_raw: number
  log_batch: number
  processing_task: number
}

export async function resetSystem(): Promise<ResetResult> {
  const { data } = await client.post<{ code: number; message: string; data: ResetResult }>(
    '/api/v1/system/reset',
  )
  return data.data
}

export interface DashboardOverview {
  device_total: number
  log_total: number
  event_today: number
  security_event_total: number
  open_events: number
  alert_total: number
  pending_alerts: number
  trend: { date: string; count: number }[]
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await client.get<{ code: number; message: string; data: DashboardOverview }>(
    '/api/v1/dashboard/overview',
  )
  return data.data
}
