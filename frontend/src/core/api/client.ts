import axios from 'axios'

const client = axios.create({
  baseURL: '/enterprise/',
  timeout: 10000,
})

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    // 会话失效时刷新页面，让 APISIX 网关重定向到登录页
    if (error?.response?.status === 401 && !sessionStorage.getItem('auth_reloading')) {
      sessionStorage.setItem('auth_reloading', '1')
      window.location.reload()
    }
    return Promise.reject(error)
  },
)

export interface ListResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  /** 日志检索专用：true 表示 total 被 1 万封顶，实际更多（避免大表精确 COUNT） */
  total_truncated?: boolean
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
