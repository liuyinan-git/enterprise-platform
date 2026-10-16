import axios from 'axios'

const client = axios.create({
  baseURL: '/',
  timeout: 10000,
})

export interface ListResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface HealthResp {
  status: string
  database: string
}

export async function getHealth(): Promise<HealthResp> {
  const { data } = await client.get<HealthResp>('/health/ready')
  return data
}

export default client
