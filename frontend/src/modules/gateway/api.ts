import client from '@/core/api/client'

export interface GatewayHealth {
  status: string
  module: string
}

export async function getGatewayHealth(): Promise<GatewayHealth> {
  const { data } = await client.get<{ code: number; message: string; data: GatewayHealth }>(
    '/api/v1/gateway/health',
  )
  return data.data
}
