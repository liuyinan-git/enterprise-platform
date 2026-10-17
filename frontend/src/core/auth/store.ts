import { defineStore } from 'pinia'
import client from '@/core/api/client'

interface AuthUser {
  user_id: string
  username: string
  roles: string[]
}

interface AuthConfig {
  enabled: boolean
}

interface AuthState {
  config: AuthConfig | null
  user: AuthUser | null
  initialized: boolean
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
        const { data } = await client.get<{ code: number; data: AuthConfig }>('/api/v1/auth/config')
        this.config = data.data
      } catch {
        this.config = { enabled: false }
      }
      this.initialized = true
      if (this.authEnabled) {
        await this.fetchMe().catch(() => {
          this.user = null
        })
      }
    },

    async fetchMe() {
      const { data } = await client.get<{ code: number; data: AuthUser }>('/api/v1/auth/me')
      this.user = data.data
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
