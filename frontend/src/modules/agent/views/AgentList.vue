<template>
  <el-alert
    v-if="degraded"
    class="degraded"
    type="warning"
    :closable="false"
    show-icon
    title="Docker 服务不可达，智能体容器状态暂无法判定"
    :description="degradeError || '台账与接口监控不受影响；恢复后状态会自动刷新。'"
  />

  <el-card>
    <template #header>
      <div class="card-header">
        <span>智能体管理</span>
        <div class="header-actions">
          <el-button @click="openAudits()">操作记录</el-button>
          <el-button @click="containerAuditVisible = true">容器操作记录</el-button>
          <el-button v-if="canWrite" type="primary" @click="openCreate">登记智能体</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="关键词">
        <el-input
          v-model="filters.q"
          placeholder="智能体 ID / 名称 / 容器名"
          clearable
          style="width: 220px"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item label="类型">
        <el-input v-model="filters.agent_type" placeholder="按类型筛选" clearable style="width: 160px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="agent_id" label="智能体 ID" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_type" label="类型" width="110" />
      <el-table-column label="容器名称" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.container_name">{{ row.container_name }}</span>
          <span v-else class="muted">未绑定</span>
        </template>
      </el-table-column>
      <el-table-column label="容器状态" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.container_found" :type="stateTagType(row.container_state || '')" size="small">
            {{ stateLabel(row.container_state || '') }}
          </el-tag>
          <el-tooltip v-else-if="row.status === 'unknown'" placement="top" content="Docker 不可达，无法判定">
            <el-tag type="info" size="small">未知</el-tag>
          </el-tooltip>
          <el-tag v-else-if="row.container_name" type="danger" size="small">未找到</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="监控状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="项目" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="row.project_name" type="success" size="small">{{ row.project_name }}</el-tag>
          <span v-else class="muted">未分类</span>
        </template>
      </el-table-column>
      <el-table-column prop="owner" label="负责人" width="100" />
      <el-table-column prop="last_seen_at" label="最后心跳" min-width="170" />
      <el-table-column label="操作" width="390" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <ContainerActions
              v-if="row.container_found"
              :container="toContainer(row)"
              :operable="canControl && isRowOperable(row)"
              @log="openLog"
              @action="runAction"
            />
            <el-button size="small" :disabled="!row.container_found" @click="openDetail(row)">详情</el-button>
            <el-button size="small" @click="openAudits(row.agent_id)">审计</el-button>
            <el-button v-if="canWrite" size="small" type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canWrite" size="small" type="danger" @click="remove(row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, sizes, prev, pager, next"
      :total="total"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="load"
      @size-change="load"
    />
  </el-card>

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑智能体' : '登记智能体'" width="560px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="智能体 ID" required>
        <el-input v-model="form.agent_id" :disabled="editing" placeholder="稳定标识，如 support-bot" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.agent_name" />
      </el-form-item>
      <el-form-item label="容器名称" required>
        <el-input v-model="form.container_name" placeholder="如 my-agent-container" />
        <div class="form-hint">状态以 Docker 容器为准；容器重建后保持同名即可自动关联。</div>
      </el-form-item>
      <el-form-item label="类型">
        <el-input v-model="form.agent_type" placeholder="如 chatbot / workflow / rag" />
      </el-form-item>
      <el-form-item label="版本">
        <el-input v-model="form.version" />
      </el-form-item>
      <el-form-item label="负责人">
        <el-input v-model="form.owner" />
      </el-form-item>
      <el-form-item label="环境">
        <el-select v-model="form.environment" clearable style="width: 100%">
          <el-option v-for="e in environments" :key="e" :label="e" :value="e" />
        </el-select>
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

  <el-drawer v-model="auditVisible" title="智能体操作记录" size="720px">
    <el-form :inline="true" class="search-bar">
      <el-form-item label="智能体 ID">
        <el-input v-model="auditFilters.agent_id" placeholder="全部" clearable style="width: 180px" />
      </el-form-item>
      <el-form-item label="操作人">
        <el-input v-model="auditFilters.operator" placeholder="按操作人筛选" clearable style="width: 160px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="searchAudits">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="auditLoading" :data="audits" border stripe size="small" style="width: 100%">
      <el-table-column prop="created_at" label="时间" min-width="170" />
      <el-table-column prop="agent_id" label="智能体 ID" min-width="140" show-overflow-tooltip />
      <el-table-column label="动作" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="auditTagType(row.action)">{{ auditActionText(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="operator" label="操作人" width="110">
        <template #default="{ row }">{{ row.operator || '—' }}</template>
      </el-table-column>
      <el-table-column label="详情" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ detailText(row.detail) }}</template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="auditTotal"
      v-model:current-page="auditPage"
      :page-size="auditPageSize"
      @current-change="loadAudits"
    />
  </el-drawer>

  <ContainerDetailDrawer v-model="detailVisible" :container="detailTarget" />
  <ContainerAuditDrawer v-model="containerAuditVisible" />
  <ContainerLogDialog
    v-model:visible="logVisible"
    :container-id="logTarget?.container_id || ''"
    :container-name="logTarget?.name"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/core/auth/store'
import {
  deleteAgent,
  listAgentAudits,
  listAgents,
  registerAgent,
  runContainerAction,
  updateAgent,
  type AgentAuditItem,
  type AgentContainerItem,
  type AgentItem,
  type ContainerAction,
} from '@/modules/agent/api'
import { actionLabel, stateLabel, stateTagType } from '@/modules/agent/display'
import ContainerActions from '@/modules/agent/components/ContainerActions.vue'
import ContainerLogDialog from '@/modules/agent/components/ContainerLogDialog.vue'
import ContainerDetailDrawer from '@/modules/agent/components/ContainerDetailDrawer.vue'
import ContainerAuditDrawer from '@/modules/agent/components/ContainerAuditDrawer.vue'

const auth = useAuthStore()
/** 前端按钮门禁；服务端会独立再校验一次（台账写 agent:manage，容器启停 agent:container） */
const canWrite = computed(() => auth.canAccess('agent:manage'))
const canControl = computed(() => auth.canAccess('agent:container'))

const items = ref<AgentItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const degraded = ref(false)
const degradeError = ref<string | null>(null)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const environments = ['production', 'staging', 'development', 'internal', 'external']

const filters = reactive({ q: '', agent_type: '' })
const form = reactive({
  agent_id: '',
  agent_name: '',
  agent_type: '',
  container_name: '',
  version: '',
  owner: '',
  environment: '',
  enabled: true,
})

const CONTAINER_NAME_RE = /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/

function statusType(s: string) {
  if (s === 'online') return 'success'
  if (s === 'disabled') return 'warning'
  if (s === 'unknown') return 'info'
  return 'danger'
}
function statusText(s: string) {
  if (s === 'online') return '在线'
  if (s === 'disabled') return '停用'
  if (s === 'unknown') return '未知'
  return '离线'
}

/** 把台账行转成容器组件需要的结构（容器 ID 用短 ID，后端支持按短 ID 定位）。 */
function toContainer(row: AgentItem): AgentContainerItem | null {
  if (!row.container_id) return null
  return {
    container_id: row.container_id,
    full_id: row.container_id,
    name: row.container_name || '',
    image: row.container_image || '',
    image_id: '',
    state: row.container_state || 'unknown',
    status: row.container_status || '',
    protected: row.container_protected,
    protected_reason: row.container_protected_reason,
    compose_project: null,
    compose_service: null,
    ports: row.container_ports,
    created_at: row.container_created_at,
    project_key: row.project_key,
    project_name: row.project_name,
    matched_by: row.project_name ? 'registered' : 'none',
    conflict: false,
    candidates: [],
  }
}

/** 已登记容器只要找到且未受保护就允许启停（不再受项目分类门禁约束） */
function isRowOperable(row: AgentItem): boolean {
  return row.container_found && !row.container_protected
}

async function load() {
  loading.value = true
  try {
    const result = await listAgents({
      page: page.value,
      page_size: pageSize.value,
      q: filters.q || undefined,
      agent_type: filters.agent_type || undefined,
    })
    items.value = result.items
    total.value = result.total
    degraded.value = Boolean(result.degraded)
    degradeError.value = result.error || null
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, {
    agent_id: '',
    agent_name: '',
    agent_type: '',
    container_name: '',
    version: '',
    owner: '',
    environment: '',
    enabled: true,
  })
  dialogVisible.value = true
}

function openEdit(row: AgentItem) {
  editing.value = true
  Object.assign(form, {
    agent_id: row.agent_id,
    agent_name: row.agent_name,
    agent_type: row.agent_type,
    container_name: row.container_name || '',
    version: row.version || '',
    owner: row.owner || '',
    environment: row.environment || '',
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.agent_id || !form.agent_name || !form.container_name.trim()) {
    ElMessage.warning('请填写智能体 ID、名称和容器名称')
    return
  }
  if (!CONTAINER_NAME_RE.test(form.container_name.trim())) {
    ElMessage.warning('容器名只能包含字母、数字、下划线、点和短横线，且必须以字母或数字开头')
    return
  }
  saving.value = true
  try {
    const payload = {
      agent_name: form.agent_name,
      agent_type: form.agent_type,
      container_name: form.container_name.trim(),
      version: form.version || undefined,
      owner: form.owner || undefined,
      environment: form.environment || undefined,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateAgent(form.agent_id, payload)
    } else {
      await registerAgent({ agent_id: form.agent_id, ...payload })
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

async function remove(row: AgentItem) {
  await ElMessageBox.confirm(`确定删除智能体「${row.agent_name || row.agent_id}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteAgent(row.agent_id)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

function search() {
  page.value = 1
  load()
}
function reset() {
  filters.q = ''
  filters.agent_type = ''
  search()
}

// ===== 容器日志 / 详情 / 启停 =====

const logVisible = ref(false)
const logTarget = ref<AgentContainerItem | null>(null)
const detailVisible = ref(false)
const detailTarget = ref<AgentContainerItem | null>(null)
const containerAuditVisible = ref(false)

function openLog(container: AgentContainerItem) {
  logTarget.value = container
  logVisible.value = true
}

function openDetail(row: AgentItem) {
  detailTarget.value = toContainer(row)
  detailVisible.value = true
}

async function runAction(container: AgentContainerItem, action: ContainerAction) {
  const verb = actionLabel(action)
  let reason: string | undefined
  try {
    if (action === 'start') {
      await ElMessageBox.confirm(
        `即将【${verb}】智能体容器「${container.name}」(${container.image})。确认继续？`,
        '危险操作',
        { type: 'warning', confirmButtonText: verb, cancelButtonText: '取消' },
      )
    } else {
      // 停止 / 重启必须填原因，后端同样强制校验并写入审计
      const { value } = await ElMessageBox.prompt(
        `即将【${verb}】智能体容器「${container.name}」(${container.image})。该操作会中断其服务，请填写操作原因，会记入审计。`,
        '危险操作',
        {
          type: 'warning',
          confirmButtonText: verb,
          cancelButtonText: '取消',
          inputType: 'textarea',
          inputPlaceholder: '例如：故障恢复 / 发布窗口 / 资源调整',
          inputValidator: (v: string) => (v && v.trim().length >= 2) || '请填写操作原因（至少 2 个字符）',
        },
      )
      reason = value.trim()
    }
  } catch {
    return
  }
  try {
    await runContainerAction(container.container_id, action, undefined, reason)
    ElMessage.success(`已${verb}`)
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || `${verb}失败`)
  }
}

// ===== 智能体操作记录（审计）=====

const auditVisible = ref(false)
const auditLoading = ref(false)
const audits = ref<AgentAuditItem[]>([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditPageSize = 50
const auditFilters = reactive({ agent_id: '', operator: '' })

function openAudits(agentId = '') {
  auditFilters.agent_id = agentId
  auditFilters.operator = ''
  auditPage.value = 1
  auditVisible.value = true
  loadAudits()
}

function searchAudits() {
  auditPage.value = 1
  loadAudits()
}

async function loadAudits() {
  auditLoading.value = true
  try {
    const result = await listAgentAudits({
      page: auditPage.value,
      page_size: auditPageSize,
      agent_id: auditFilters.agent_id || undefined,
      operator: auditFilters.operator || undefined,
    })
    audits.value = result.items
    auditTotal.value = result.total
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '加载操作记录失败')
  } finally {
    auditLoading.value = false
  }
}

function auditActionText(action: string): string {
  const labels: Record<string, string> = {
    register: '登记',
    upsert: '覆盖登记',
    update: '编辑',
    delete: '删除',
    offline_alert: '离线告警',
    back_online: '恢复在线',
  }
  return labels[action] || action
}

function auditTagType(action: string): 'success' | 'warning' | 'info' | 'danger' {
  if (action === 'delete' || action === 'offline_alert') return 'danger'
  if (action === 'update') return 'info'
  if (action === 'register' || action === 'upsert' || action === 'back_online') return 'success'
  return 'warning'
}

function detailText(detail: Record<string, unknown> | null): string {
  if (!detail) return '—'
  const parts: string[] = []
  if (Array.isArray(detail.changed) && detail.changed.length) parts.push(`变更：${detail.changed.join(', ')}`)
  if (detail.container_name) parts.push(`容器：${detail.container_name}`)
  if (detail.user_id) parts.push(`用户：${detail.user_id}`)
  if (Array.isArray(detail.roles) && detail.roles.length) parts.push(`角色：${detail.roles.join('/')}`)
  if (detail.last_seen_at) parts.push(`最后心跳：${detail.last_seen_at}`)
  if (detail.notify_error) parts.push(`通知失败：${detail.notify_error}`)
  return parts.length ? parts.join('；') : JSON.stringify(detail)
}

onMounted(load)
</script>

<style scoped>
.degraded {
  margin-bottom: 12px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.muted {
  color: #909399;
}
.row-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
.form-hint {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}
</style>
