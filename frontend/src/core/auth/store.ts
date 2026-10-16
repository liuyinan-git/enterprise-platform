import { defineStore } from 'pinia'
import client from '@/core/api/client'
import {
  buildAuthorizeUrl,
  clearAccessToken,
  clearPkce,
  exchangeCode,
  generatePkce,
  getAccessToken,
  loadPkce,
  savePkce,
  setAccessToken,
  type OidcConfig,
} from '@/core/auth/oidc'

interface AuthUser {
  user_id: string
  username: string
  roles: string[]
}

interface AuthState {
  config: OidcConfig | null
  user: AuthUser | null
  initialized: boolean
}

const FALLBACK_CONFIG: OidcConfig = {
  enabled: false,
  issuer: '',
  authorize_url: '',
  token_url: '',
  client_id: '',
  redirect_uri: '',
  scopes: '',
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    config: null,
    user: null,
    initialized: false,
  }),
  getters: {
    authEnabled: (state) => state.config?.enabled ?? false,
    roles: (state) => state.user?.roles ?? [],
  },
  actions: {
    async initAuth() {
      try {
        const { data } = await client.get<{ code: number; data: OidcConfig }>('/api/v1/auth/config')
        this.config = data.data
      } catch {
        this.config = FALLBACK_CONFIG
      }
      this.initialized = true
      if (this.authEnabled && getAccessToken()) {
        await this.fetchMe().catch(() => this.logout())
      }
    },

    async startLogin() {
      if (!this.config?.enabled) return
      const { verifier, challenge } = await generatePkce()
      const state =
        typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : Math.random().toString(36).slice(2)
      savePkce(verifier, state)
      window.location.href = buildAuthorizeUrl(this.config, challenge, state)
    },

    async finishLogin(code: string) {
      if (!this.config) throw new Error('OIDC 配置缺失')
      const pkce = loadPkce()
      if (!pkce) throw new Error('PKCE 状态缺失，请重新登录')
      clearPkce()
      const tokens = await exchangeCode(this.config, code, pkce.verifier)
      const accessToken = tokens.access_token as string | undefined
      if (!accessToken) throw new Error('token 响应缺少 access_token')
      setAccessToken(accessToken)
      await this.fetchMe()
    },

    async fetchMe() {
      const { data } = await client.get<{ code: number; data: AuthUser }>('/api/v1/auth/me')
      this.user = data.data
    },

    logout() {
      this.user = null
      clearAccessToken()
    },

    /** 当前用户是否可访问声明了 requiredRoles 的菜单。authEnabled=false 时全放行。 */
    canAccess(requiredRoles: string[]): boolean {
      if (!this.authEnabled) return true
      if (this.roles.includes('admin')) return true
      if (requiredRoles.length === 0) return true
      return requiredRoles.some((r) => this.roles.includes(r))
    },
  },
})
