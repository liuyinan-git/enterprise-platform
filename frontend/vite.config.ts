import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// ===== 网关路径前缀 =====
// 平台经 APISIX 网关对外访问的路径是 /enterprise/*，前端资源也要挂在这个前缀下，
// 这样浏览器加载的静态资源和发起的 API 请求才会都命中 APISIX 的这条路由（拿到网关注入的用户头）。
// 本地直连时对应地址是 http://localhost:5170/enterprise/
const BASE_PATH = '/enterprise/'

// ===== 本地联调兜底：模拟 APISIX 网关注入的用户头 =====
// 仅当请求没带真实网关头时才注入（走 APISIX 时已有真实头，不会覆盖）。
// 本地直连（不经 APISIX）时用它模拟登录角色，改 x-user-roles 即可切换：
//   admin / viewer / log_admin / agent_admin / model_admin
//   / database_admin / gateway_admin / agent_container_admin / database_container_admin
const MOCK_USER: Record<string, string> = {
  'x-user-id': '1001',
  'x-user-num': 'zhangsan',
  'x-user-roles': 'admin',
}

function addMockHeaders(proxy: any): void {
  proxy.on('proxyReq', (proxyReq: any) => {
    if (!proxyReq.getHeader('x-user-id')) {
      for (const [key, value] of Object.entries(MOCK_USER)) {
        proxyReq.setHeader(key, value)
      }
    }
  })
}

// 后端地址
const BACKEND = 'http://127.0.0.1:7550'
// 去掉 /enterprise 前缀（后端路由本身不带这个前缀）
const stripPrefix = (path: string) => path.replace(/^\/enterprise/, '')

export default defineConfig({
  base: BASE_PATH,
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5170,
    proxy: {
      // 本地直连（请求带 /enterprise 前缀）：去掉前缀再转发给后端
      '/enterprise/api': {
        target: BACKEND,
        changeOrigin: true,
        rewrite: stripPrefix,
        configure: addMockHeaders,
      },
      '/enterprise/health': {
        target: BACKEND,
        changeOrigin: true,
        rewrite: stripPrefix,
        configure: addMockHeaders,
      },
      // 经 APISIX（前缀已被网关 proxy-rewrite 去掉，只剩 /api、/health）
      '/api': { target: BACKEND, changeOrigin: true, configure: addMockHeaders },
      '/health': { target: BACKEND, changeOrigin: true, configure: addMockHeaders },
    },
  },
})
