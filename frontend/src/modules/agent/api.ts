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
