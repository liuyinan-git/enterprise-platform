import client from '@/core/api/client'

export interface WecomConfigItem {
  corpid: string
  corpsecret_masked: string
  agentid: number
  touser: string
  enabled: boolean
  notify_min_severity: string
  updated_at: string | null
}

export interface WecomConfigInput {
  corpid: string
  corpsecret: string
  agentid: number
  touser: string
  enabled: boolean
  notify_min_severity: string
}

export async function getWecomConfig(): Promise<WecomConfigItem> {
  const { data } = await client.get<{ code: number; message: string; data: WecomConfigItem }>(
    '/api/v1/wecom/config',
  )
  return data.data
}

export async function updateWecomConfig(payload: WecomConfigInput): Promise<WecomConfigItem> {
  const { data } = await client.put<{ code: number; message: string; data: WecomConfigItem }>(
    '/api/v1/wecom/config',
    payload,
  )
  return data.data
}

export async function testWecom(payload: { touser?: string; content?: string }): Promise<{ errcode: number; errmsg: string }> {
  const { data } = await client.post<{ code: number; message: string; data: { errcode: number; errmsg: string } }>(
    '/api/v1/wecom/test',
    payload,
  )
  return data.data
}
