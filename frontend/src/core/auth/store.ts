import { defineStore } from 'pinia'
import client from '@/core/api/client'

interface AuthUser {
  user_id: string
  username: string
  roles: string[]
  permissions: string[]
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
    permissions: (state) => state.user?.permissions ?? [],
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

    /** 当前用户是否拥有指定权限。authEnabled=false 时全放行；permission 缺省表示无需权限。 */
    canAccess(permission?: string): boolean {
      if (!this.authEnabled) return true
      if (this.roles.includes('admin')) return true
      if (!permission) return true
      return this.permissions.includes(permission)
    },
  },
})
