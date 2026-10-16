import client from '@/core/api/client'
import type { ListResult } from '@/core/api/client'

export interface AgentItem {
  id: number
  agent_id: string
  agent_name: string
  agent_type: string
  version: string | null
  owner: string | null
  environment: string | null
  enabled: boolean
  attributes: Record<string, unknown> | null
  last_seen_at: string | null
  status: 'online' | 'offline' | 'disabled'
}

export interface AgentInput {
  agent_id: string
  agent_name: string
  agent_type: string
  version?: string
  owner?: string
  environment?: string
  enabled?: boolean
  attributes?: Record<string, unknown>
}

export interface AgentListParams {
  page?: number
  page_size?: number
  agent_type?: string
  enabled?: boolean
}

export async function listAgents(params: AgentListParams = {}): Promise<ListResult<AgentItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<AgentItem> }>(
    '/api/v1/agents',
    { params },
  )
  return data.data
}

export async function registerAgent(payload: AgentInput): Promise<AgentItem> {
  const { data } = await client.post<{ code: number; message: string; data: AgentItem }>('/api/v1/agents', payload)
  return data.data
}

export async function updateAgent(agentId: string, payload: Partial<AgentInput>): Promise<AgentItem> {
  const { data } = await client.patch<{ code: number; message: string; data: AgentItem }>(
    `/api/v1/agents/${encodeURIComponent(agentId)}`,
    payload,
  )
  return data.data
}

export async function deleteAgent(agentId: string): Promise<void> {
  await client.delete(`/api/v1/agents/${encodeURIComponent(agentId)}`)
}

export interface AgentAuditItem {
  id: number
  agent_id: string
  action: string
  operator: string | null
  detail: Record<string, unknown> | null
  created_at: string | null
}

export async function listAgentAudits(
  params: { page?: number; page_size?: number; agent_id?: string } = {},
): Promise<ListResult<AgentAuditItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<AgentAuditItem> }>(
    '/api/v1/agent-audits',
    { params },
  )
  return data.data
}

// ===== AI Agent 平台：概览与系统设置 =====

export interface OverviewData {
  project_count: number
  rule_count: number
  rule_enabled_count: number
  container_count: number
  running_count: number
  stopped_count: number
  unclassified_count: number
  api_total: number
  api_healthy: number
  api_unhealthy: number
  api_by_status: Record<string, number>
  api_by_type: Record<string, number>
  failing_endpoints: FailingEndpoint[]
  history_total: number
  /** Docker 不可达时为 true；此时容器类数字全为 0 */
  degraded: boolean
  error: string | null
  generated_at: string
}

export interface FailingEndpoint {
  endpoint_code: string
  name: string
  service_type: string
  health_status: string
  last_http_status: number | null
  last_error: string | null
  consecutive_failures: number
  last_check_at: string | null
}

export async function fetchAgentOverview(): Promise<OverviewData> {
  const { data } = await client.get<{ code: number; message: string; data: OverviewData }>('/api/v1/agent/overview')
  return data.data
}

export interface ScheduleItem {
  name: string
  task: string
  interval_seconds: number | null
}

export interface StatusValue {
  value: number | string | boolean
  env?: string
}

export interface ConnectionStatus {
  ok: boolean
  latency_ms: number
  error: string | null
  detail?: string
}

export interface SystemStatusData {
  schedule: { source: string; note: string; items: ScheduleItem[] }
  timeouts: Record<string, StatusValue>
  storage: Record<string, StatusValue | number | string | null>
  docker: ConnectionStatus & {
    proxy_url_masked: string
    protected_project: string
    log_tail_default: number
    log_tail_max: number
    log_timestamps: boolean
  }
  probe: { verify_tls: boolean; max_excerpt_chars: number }
  connections: { mysql: ConnectionStatus; redis: ConnectionStatus }
  auth: {
    oidc_enabled: boolean
    anonymous_admin: boolean
    roles: Record<string, string[]>
  }
  generated_at: string
}

export async function fetchSystemStatus(): Promise<SystemStatusData> {
  const { data } = await client.get<{ code: number; message: string; data: SystemStatusData }>(
    '/api/v1/agent/system-status',
  )
  return data.data
}

// ===== AI Agent 平台：Docker 容器 =====

export interface AgentContainerItem {
  container_id: string
  full_id: string
  name: string
  image: string
  image_id: string
  state: string
  status: string
  protected: boolean
  protected_reason: string | null
  compose_project: string | null
  compose_service: string | null
  ports: string[]
  created_at: string | null
  /** 已分类到的项目；null 表示未分类 */
  project_key: string | null
  project_name: string | null
  /** compose / name / none / conflict */
  matched_by: string
  /** 同时命中多条规则，此时不给操作 */
  conflict: boolean
  candidates: string[]
}

export interface ProjectBucket {
  project_key: string
  project_name: string
  enabled: boolean
  rule_id: number | null
  total: number
  running: number
  stopped: number
}

export interface ProjectSummary {
  projects: ProjectBucket[]
  unclassified: { key: string; name: string; total: number; running: number; stopped: number }
  conflict: { key: string; name: string; total: number; running: number; stopped: number }
}

export interface ContainerListResult {
  items: AgentContainerItem[]
  total: number
  summary: ProjectSummary | null
  /** Docker 不可达时为 true，此时 items 为空 */
  degraded: boolean
  error: string | null
  generated_at: string
}

export async function listContainers(
  params: {
    project_key?: string
    state?: string
    q?: string
    include_protected?: boolean
    include_stopped?: boolean
  } = {},
): Promise<ContainerListResult> {
  const { data } = await client.get<{ code: number; message: string; data: ContainerListResult }>(
    '/api/v1/agent/containers',
    { params },
  )
  return data.data
}

export async function discoverContainers(): Promise<{
  discovered: number
  classified: number
  unclassified: number
  conflict: number
  project_count: number
  generated_at: string
}> {
  const { data } = await client.post<{
    code: number
    message: string
    data: { discovered: number; classified: number; unclassified: number; conflict: number; project_count: number; generated_at: string }
  }>('/api/v1/agent/containers/discover')
  return data.data
}

export interface ContainerDetail {
  command: string | null
  args: string[] | null
  started_at: string | null
  finished_at: string | null
  exit_code: number | null
  restart_count: number | null
  health: string | null
  networks: string[]
  mount_count: number
  restart_policy: string | null
  refusal_reason: string | null
}

export interface ExecCommandInfo {
  container_id: string
  full_id: string
  shell: string
  command: string
  fallback_command: string
  host_note: string
}

export async function fetchContainer(
  containerId: string,
): Promise<{ container: AgentContainerItem; detail: ContainerDetail | null; exec_command: ExecCommandInfo | null }> {
  const { data } = await client.get<{
    code: number
    message: string
    data: { container: AgentContainerItem; detail: ContainerDetail | null; exec_command: ExecCommandInfo | null }
  }>(`/api/v1/agent/containers/${encodeURIComponent(containerId)}`)
  return data.data
}

export interface ContainerLogResult {
  container_id: string
  name: string
  text: string
  truncated: boolean
  timestamps: boolean
  generated_at: string
}

export async function fetchContainerLogs(
  containerId: string,
  params: { tail?: number; since?: number; timestamps?: boolean } = {},
): Promise<ContainerLogResult> {
  const { data } = await client.get<{ code: number; message: string; data: ContainerLogResult }>(
    `/api/v1/agent/containers/${encodeURIComponent(containerId)}/logs`,
    // 拉日志比普通请求慢，单独放宽默认的 10s
    { params, timeout: 20000 },
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
    `/api/v1/agent/containers/${encodeURIComponent(containerId)}/${action}`,
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
  project_key: string | null
  action: string
  result: string
  operator: string | null
  detail: Record<string, unknown> | null
  created_at: string | null
}

export async function listContainerAudits(
  params: { page?: number; page_size?: number; container_id?: string; project_key?: string; result?: string } = {},
): Promise<ListResult<ContainerAuditItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<ContainerAuditItem> }>(
    '/api/v1/agent/container-audits',
    { params },
  )
  return data.data
}

// ===== AI Agent 平台：项目与分类规则 =====

export interface ProjectRule {
  id: number
  project_key: string
  project_name: string
  enabled: boolean
  compose_project_names: string[]
  container_name_patterns: string[]
  description: string | null
  priority: number
  created_at: string | null
  updated_at: string | null
}

export interface RuleConflict {
  field: string
  value: string
  project_keys: string[]
}

export interface ProjectRuleInput {
  project_key: string
  project_name: string
  enabled?: boolean
  compose_project_names?: string[]
  container_name_patterns?: string[]
  description?: string
  priority?: number
}

export async function listProjectRules(
  params: { enabled?: boolean } = {},
): Promise<{ items: ProjectRule[]; total: number; conflicts: RuleConflict[] }> {
  const { data } = await client.get<{ code: number; message: string; data: { items: ProjectRule[]; total: number; conflicts: RuleConflict[] } }>(
    '/api/v1/agent/project-rules',
    { params },
  )
  return data.data
}

export async function createProjectRule(payload: ProjectRuleInput): Promise<ProjectRule> {
  const { data } = await client.post<{ code: number; message: string; data: ProjectRule }>(
    '/api/v1/agent/project-rules',
    payload,
  )
  return data.data
}

export async function updateProjectRule(key: string, payload: Partial<ProjectRuleInput>): Promise<ProjectRule> {
  const { data } = await client.put<{ code: number; message: string; data: ProjectRule }>(
    `/api/v1/agent/project-rules/${encodeURIComponent(key)}`,
    payload,
  )
  return data.data
}

export async function setProjectRuleEnabled(key: string, enabled: boolean): Promise<ProjectRule> {
  const { data } = await client.patch<{ code: number; message: string; data: ProjectRule }>(
    `/api/v1/agent/project-rules/${encodeURIComponent(key)}/enabled`,
    { enabled },
  )
  return data.data
}

export async function deleteProjectRule(key: string): Promise<void> {
  await client.delete(`/api/v1/agent/project-rules/${encodeURIComponent(key)}`)
}

export interface ProjectsResult extends ProjectSummary {
  degraded: boolean
  error: string | null
  conflicts: RuleConflict[]
}

export async function fetchProjects(): Promise<ProjectsResult> {
  const { data } = await client.get<{ code: number; message: string; data: ProjectsResult }>(
    '/api/v1/agent/projects',
  )
  return data.data
}

// ===== AI Agent 平台：接口监控 / LangGraph =====

export interface EndpointItem {
  id: number
  endpoint_code: string
  name: string
  service_type: string
  /** 列名是 group_name（group 是 SQL 保留字），接口对外叫 group */
  group: string | null
  url: string
  method: string
  headers: Record<string, unknown> | null
  request_body: Record<string, unknown> | unknown[] | null
  expected_status: number[]
  timeout_seconds: number
  enabled: boolean
  description: string | null
  attributes: Record<string, unknown> | null
  health_status: string
  last_check_at: string | null
  last_http_status: number | null
  last_latency_ms: number | null
  last_error: string | null
  last_ok_at: string | null
  consecutive_failures: number
  created_at: string | null
  updated_at: string | null
}

export interface EndpointInput {
  endpoint_code: string
  name: string
  service_type: string
  group?: string
  url: string
  method?: string
  headers?: Record<string, unknown>
  request_body?: Record<string, unknown> | unknown[]
  expected_status?: number[]
  timeout_seconds?: number
  enabled?: boolean
  description?: string
  attributes?: Record<string, unknown>
}

export interface EndpointListParams {
  page?: number
  page_size?: number
  service_type?: string
  group?: string
  health_status?: string
  enabled?: boolean
  q?: string
}

export async function listEndpoints(params: EndpointListParams = {}): Promise<ListResult<EndpointItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<EndpointItem> }>(
    '/api/v1/agent/endpoints',
    { params },
  )
  return data.data
}

export async function fetchEndpointOptions(): Promise<{
  service_types: string[]
  groups: string[]
  items: { endpoint_code: string; name: string; service_type: string }[]
}> {
  const { data } = await client.get<{
    code: number
    message: string
    data: { service_types: string[]; groups: string[]; items: { endpoint_code: string; name: string; service_type: string }[] }
  }>('/api/v1/agent/endpoints/options')
  return data.data
}

export async function createEndpoint(payload: EndpointInput): Promise<EndpointItem> {
  const { data } = await client.post<{ code: number; message: string; data: EndpointItem }>(
    '/api/v1/agent/endpoints',
    payload,
  )
  return data.data
}

export async function updateEndpoint(code: string, payload: Partial<EndpointInput>): Promise<EndpointItem> {
  const { data } = await client.put<{ code: number; message: string; data: EndpointItem }>(
    `/api/v1/agent/endpoints/${encodeURIComponent(code)}`,
    payload,
  )
  return data.data
}

export async function deleteEndpoint(code: string): Promise<void> {
  await client.delete(`/api/v1/agent/endpoints/${encodeURIComponent(code)}`)
}

export interface CheckResultItem {
  endpoint_code: string
  name: string
  status: string
  http_status: number | null
  latency_ms: number | null
  error: string | null
  body_excerpt: string | null
  consecutive_failures: number
  checked_at: string
}

export async function checkEndpoint(code: string): Promise<CheckResultItem> {
  const { data } = await client.post<{ code: number; message: string; data: CheckResultItem }>(
    `/api/v1/agent/endpoints/${encodeURIComponent(code)}/check`,
  )
  return data.data
}

export async function checkEndpointsBatch(codes?: string[]): Promise<{
  items: CheckResultItem[]
  total: number
  summary: Record<string, number>
}> {
  const { data } = await client.post<{
    code: number
    message: string
    data: { items: CheckResultItem[]; total: number; summary: Record<string, number> }
  }>(
    '/api/v1/agent/endpoints/check-batch',
    codes?.length ? { codes } : {},
    // 串行探测多个端点，最坏情况会顶到默认的 10s，单独放宽
    { timeout: 60000 },
  )
  return data.data
}

export interface HealthHistoryItem {
  id: number
  endpoint_id: number | null
  endpoint_code: string
  endpoint_name: string | null
  service_type: string | null
  status: string
  http_status: number | null
  latency_ms: number | null
  error: string | null
  check_type: string
  checked_at: string | null
}

export interface HealthHistoryParams {
  page?: number
  page_size?: number
  endpoint_code?: string
  service_type?: string
  status?: string
  checked_from?: string
  checked_to?: string
}

export async function listHealthHistory(params: HealthHistoryParams = {}): Promise<ListResult<HealthHistoryItem>> {
  const { data } = await client.get<{ code: number; message: string; data: ListResult<HealthHistoryItem> }>(
    '/api/v1/agent/health-history',
    { params },
  )
  return data.data
}
