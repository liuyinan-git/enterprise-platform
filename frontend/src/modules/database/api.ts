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

// ===== 容器实况（与数据库台账合并展示）=====

export interface ContainerItem {
  container_id: string
  full_id: string
  name: string
  image: string
  image_id: string
  managed_type: string
  /** 类型是怎么识别出来的：label / image / name / app（认出品牌但属应用层）/ none */
  managed_type_source: string
  state: string
  status: string
  protected: boolean
  protected_reason: string | null
  compose_project: string | null
  compose_service: string | null
  ports: string[]
  created_at: string | null
}

/** 台账行 + 其对应容器的实况 */
export interface OverviewItem extends InstanceItem {
  container: ContainerItem | null
  /** 关联来源：attributes.docker_container_id / attributes.docker_container / instance_code / none */
  container_link: string
  /** 不可操作的原因；null 表示可操作 */
  refusal_reason: string | null
}

export interface OverviewResult extends ListResult<OverviewItem> {
  /** 既不在台账里、也未被任何台账行关联的容器 */
  unregistered: ContainerItem[]
  unregistered_total: number
  /** 被「只列受管类型」滤掉的未分类容器数（scope=all 时恒为 0） */
  unregistered_hidden_unknown: number
  /** 各类型的未登记数量（后端在类型过滤前统计，供筛选下拉显示计数） */
  unregistered_by_type: Record<string, number>
  containers_total: number
  /** Docker 不可达时为 true，此时 items 里的 container 全为 null */
  degraded: boolean
  error: string | null
  generated_at: string
}

export type UnregisteredScope = 'managed' | 'all'

export async function fetchOverview(
  params: {
    page?: number
    page_size?: number
    db_type?: string
    enabled?: boolean
    include_protected?: boolean
    /** managed（默认）只列受管类型；all 连未分类的一起列 */
    unregistered_scope?: UnregisteredScope
    /** 进一步按类型筛选未登记容器 */
    unregistered_type?: string
  } = {},
): Promise<OverviewResult> {
  const { data } = await client.get<{ code: number; message: string; data: OverviewResult }>(
    '/api/v1/database-overview',
    { params },
  )
  return data.data
}

export interface ContainerLogResult {
  container_id: string
  name: string
  text: string
  truncated: boolean
  generated_at: string
}

export async function fetchContainerLogs(containerId: string, tail = 200): Promise<ContainerLogResult> {
  const { data } = await client.get<{ code: number; message: string; data: ContainerLogResult }>(
    `/api/v1/database-containers/${encodeURIComponent(containerId)}/logs`,
    // 拉日志比普通请求慢，单独放宽默认的 10s
    { params: { tail }, timeout: 20000 },
  )
  return data.data
}

export interface ExecCommandInfo {
  container_id: string
  full_id: string
  shell: string
  command: string
  fallback_command: string
  host_note: string
}

export async function fetchExecCommand(containerId: string): Promise<ExecCommandInfo> {
  const { data } = await client.get<{ code: number; message: string; data: ExecCommandInfo }>(
    `/api/v1/database-containers/${encodeURIComponent(containerId)}/exec-command`,
  )
  return data.data
}

export type ContainerAction = 'start' | 'stop' | 'restart'

export async function runContainerAction(
  containerId: string,
  action: ContainerAction,
  timeout?: number,
): Promise<{ container_id: string; name: string; action: string; result: string }> {
  const { data } = await client.post<{
    code: number
    message: string
    data: { container_id: string; name: string; action: string; result: string }
  }>(
    `/api/v1/database-containers/${encodeURIComponent(containerId)}/${action}`,
    timeout == null ? {} : { timeout },
    // 启停要等容器真正停下，比默认 10s 放宽
    { timeout: 20000 },
  )
  return data.data
}

export interface ContainerAuditItem {
  id: number
  container_id: string
  container_name: string
  managed_type: string
  action: string
  result: string
  operator: string | null
  detail: Record<string, unknown> | null
  created_at: string | null
}

export async function listContainerAudits(
  params: { page?: number; page_size?: number; container_id?: string; result?: string } = {},
): Promise<ListResult<ContainerAuditItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<ContainerAuditItem> }>(
    '/api/v1/database-container-audits',
    { params },
  )
  return data.data
}
