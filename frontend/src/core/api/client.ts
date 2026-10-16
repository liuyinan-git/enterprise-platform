import axios from 'axios'
import { clearAccessToken, getAccessToken } from '@/core/auth/oidc'

const client = axios.create({
  baseURL: '/',
  timeout: 10000,
})

client.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401) {
      clearAccessToken()
    }
    return Promise.reject(error)
  },
)

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
