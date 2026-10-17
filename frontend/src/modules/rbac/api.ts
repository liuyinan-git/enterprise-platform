import client from '@/core/api/client'

export interface RoleItem {
  id: number
  role_code: string
  role_name: string
  external_role_id: string | null
  description: string | null
  enabled: boolean
  permission_codes: string[]
  created_at: string | null
  updated_at: string | null
}

export interface RoleInput {
  role_code: string
  role_name: string
  external_role_id?: string | null
  description?: string | null
  enabled?: boolean
}

export interface PermissionGroup {
  module: string
  permissions: { permission_code: string; permission_name: string }[]
}

export async function listRoles(): Promise<RoleItem[]> {
  const { data } = await client.get<{ code: number; message: string; data: { items: RoleItem[] } }>(
    '/api/v1/rbac/roles',
  )
  return data.data.items
}

export async function createRole(payload: RoleInput): Promise<RoleItem> {
  const { data } = await client.post<{ code: number; message: string; data: RoleItem }>(
    '/api/v1/rbac/roles',
    payload,
  )
  return data.data
}

export async function updateRole(roleCode: string, payload: Partial<RoleInput>): Promise<RoleItem> {
  const { data } = await client.put<{ code: number; message: string; data: RoleItem }>(
    `/api/v1/rbac/roles/${encodeURIComponent(roleCode)}`,
    payload,
  )
  return data.data
}

export async function deleteRole(roleCode: string): Promise<void> {
  await client.delete(`/api/v1/rbac/roles/${encodeURIComponent(roleCode)}`)
}

export async function listPermissions(): Promise<PermissionGroup[]> {
  const { data } = await client.get<{ code: number; message: string; data: { items: PermissionGroup[] } }>(
    '/api/v1/rbac/permissions',
  )
  return data.data.items
}

export async function setRolePermissions(roleCode: string, permissionCodes: string[]): Promise<void> {
  await client.put(`/api/v1/rbac/roles/${encodeURIComponent(roleCode)}/permissions`, {
    permission_codes: permissionCodes,
  })
}
