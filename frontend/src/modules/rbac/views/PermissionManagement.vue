<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>权限管理</span>
        <el-button type="primary" @click="openCreate">新增角色</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="roles" border stripe style="width: 100%">
      <el-table-column prop="role_code" label="角色编码" min-width="160" show-overflow-tooltip />
      <el-table-column prop="role_name" label="角色名称" min-width="140" show-overflow-tooltip />
      <el-table-column label="外部角色ID（MaxKey）" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.external_role_id || '未映射' }}</template>
      </el-table-column>
      <el-table-column label="权限数" width="90">
        <template #default="{ row }">{{ row.permission_codes.length }}</template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openGrant(row)">授权</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 新增/编辑角色 -->
  <el-dialog v-model="dialogVisible" :title="editing ? '编辑角色' : '新增角色'" width="520px">
    <el-form :model="form" label-width="140px">
      <el-form-item label="角色编码" required>
        <el-input v-model="form.role_code" :disabled="editing" placeholder="如 log_admin" />
      </el-form-item>
      <el-form-item label="角色名称" required>
        <el-input v-model="form.role_name" placeholder="如 日志管理员" />
      </el-form-item>
      <el-form-item label="外部角色ID(MaxKey)">
        <el-input v-model="form.external_role_id" placeholder="MaxKey 里的 19 位角色 ID" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>

  <!-- 角色授权 -->
  <el-dialog v-model="grantVisible" :title="`角色授权：${grantRole?.role_name || ''}`" width="620px">
    <div v-loading="grantLoading">
      <el-checkbox-group v-model="grantedPerms">
        <div v-for="group in permissionGroups" :key="group.module" class="perm-group">
          <div class="perm-group-title">{{ moduleName(group.module) }}</div>
          <el-checkbox
            v-for="p in group.permissions"
            :key="p.permission_code"
            :label="p.permission_code"
            class="perm-item"
          >
            {{ p.permission_name }}
          </el-checkbox>
        </div>
      </el-checkbox-group>
    </div>
    <template #footer>
      <el-button @click="grantVisible = false">取消</el-button>
      <el-button type="primary" :loading="grantSaving" @click="saveGrant">保存授权</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createRole,
  deleteRole,
  listPermissions,
  listRoles,
  setRolePermissions,
  updateRole,
  type PermissionGroup,
  type RoleItem,
} from '@/modules/rbac/api'

const roles = ref<RoleItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const permissionGroups = ref<PermissionGroup[]>([])
const grantVisible = ref(false)
const grantRole = ref<RoleItem | null>(null)
const grantedPerms = ref<string[]>([])
const grantLoading = ref(false)
const grantSaving = ref(false)

const form = reactive({
  role_code: '',
  role_name: '',
  external_role_id: '',
  description: '',
  enabled: true,
})

function moduleName(m: string): string {
  const map: Record<string, string> = {
    log: '日志管控',
    agent: '智能体管控',
    model: '模型管控',
    database: '数据库管控',
    gateway: '网关管控',
    platform: '平台管理',
  }
  return map[m] || m
}

async function load() {
  loading.value = true
  try {
    roles.value = await listRoles()
  } finally {
    loading.value = false
  }
}

async function loadPermissions() {
  permissionGroups.value = await listPermissions()
}

function openCreate() {
  editing.value = false
  Object.assign(form, { role_code: '', role_name: '', external_role_id: '', description: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(row: RoleItem) {
  editing.value = true
  Object.assign(form, {
    role_code: row.role_code,
    role_name: row.role_name,
    external_role_id: row.external_role_id || '',
    description: row.description || '',
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.role_code || !form.role_name) {
    ElMessage.warning('请填写角色编码和名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      role_name: form.role_name,
      external_role_id: form.external_role_id || null,
      description: form.description || null,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateRole(form.role_code, payload)
    } else {
      await createRole({ role_code: form.role_code, ...payload })
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: RoleItem) {
  await ElMessageBox.confirm(`确定删除角色「${row.role_name || row.role_code}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteRole(row.role_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

async function openGrant(row: RoleItem) {
  grantRole.value = row
  grantedPerms.value = [...row.permission_codes]
  grantVisible.value = true
  if (permissionGroups.value.length === 0) {
    grantLoading.value = true
    try {
      await loadPermissions()
    } finally {
      grantLoading.value = false
    }
  }
}

async function saveGrant() {
  if (!grantRole.value) return
  grantSaving.value = true
  try {
    await setRolePermissions(grantRole.value.role_code, grantedPerms.value)
    ElMessage.success('授权已保存')
    grantVisible.value = false
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '授权失败')
  } finally {
    grantSaving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.perm-group {
  margin-bottom: 12px;
}
.perm-group-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: #303133;
}
.perm-item {
  margin-right: 16px;
  margin-bottom: 6px;
}
</style>
