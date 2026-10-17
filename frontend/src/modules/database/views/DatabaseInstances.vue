<template>
  <el-alert
    v-if="degraded"
    class="degraded"
    type="warning"
    :closable="false"
    show-icon
    title="Docker 服务不可达，容器实况暂不可用"
    :description="degradeError || '台账本身不受影响，可继续登记与检测。'"
  />

  <el-card>
    <template #header>
      <div class="card-header">
        <span>数据库实例</span>
        <div class="header-actions">
          <span v-if="updatedAt" class="hint">实况更新于 {{ updatedAt.slice(11, 19) }}</span>
          <el-button size="small" @click="load()">刷新</el-button>
          <el-button size="small" @click="openAudits">操作记录</el-button>
          <el-button type="primary" @click="openCreate">登记实例</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="类型">
        <el-input v-model="filters.db_type" placeholder="按类型筛选" clearable style="width: 150px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="instance_code" label="实例编码" min-width="130" show-overflow-tooltip />
      <el-table-column prop="instance_name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="db_type" label="类型" width="110" />
      <el-table-column label="地址" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.host }}:{{ row.port }}</template>
      </el-table-column>
      <el-table-column prop="database_name" label="库名" width="120" show-overflow-tooltip />
      <el-table-column prop="environment" label="环境" width="100" />
      <el-table-column label="健康状态" width="100">
        <template #default="{ row }">
          <el-tag :type="healthType(row.health_status)" size="small">{{ row.health_status }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column label="容器实况" min-width="220">
        <template #default="{ row }">
          <template v-if="row.container">
            <el-tag :type="stateTagType(row.container.state)" size="small">
              {{ stateLabel(row.container.state) }}
            </el-tag>
            <div class="container-name">{{ row.container.name }}</div>
            <div class="container-image" :title="row.container.image">{{ row.container.image }}</div>
          </template>
          <el-tooltip
            v-else
            placement="top"
            content="未找到对应容器。可在「编辑」的实例上填写 attributes.docker_container（容器名或 ID）来显式关联。"
          >
            <el-tag type="info" size="small">未纳管容器</el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="受管类型" width="110">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.container"
            placement="top"
            :content="`${typeSourceLabel(row.container.managed_type_source)}${
              row.refusal_reason ? ` · ${row.refusal_reason}` : ''
            }`"
          >
            <el-tag :type="typeTagType(row.container.managed_type)" size="small" effect="plain">
              {{ typeLabel(row.container.managed_type) }}
            </el-tag>
          </el-tooltip>
          <span v-else>—</span>
        </template>
      </el-table-column>

      <el-table-column label="台账操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="check(row)">检测</el-button>
          <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
      <el-table-column label="容器操作" width="250" fixed="right">
        <template #default="{ row }">
          <ContainerActions
            :container="row.container"
            :operable="canControl && isOperable(row.container)"
            @log="openLog"
            @action="runAction"
          />
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
      @current-change="load()"
      @size-change="load()"
    />
  </el-card>

  <UnregisteredContainers
    :items="unregistered"
    :total="unregisteredTotal"
    :loading="loading"
    :include-protected="includeProtected"
    :can-control="canControl"
    :filter="unregisteredFilter"
    :hidden-unknown="hiddenUnknown"
    :count-by-type="countByType"
    @update:include-protected="onToggleProtected"
    @update:filter="onChangeFilter"
    @log="openLog"
    @action="runAction"
  />

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑实例' : '登记实例'" width="540px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="实例编码" required>
        <el-input v-model="form.instance_code" :disabled="editing" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.instance_name" />
      </el-form-item>
      <el-form-item label="类型" required>
        <el-select v-model="form.db_type" style="width: 100%">
          <el-option v-for="t in dbTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="主机" required>
        <el-input v-model="form.host" placeholder="IP 或域名" />
      </el-form-item>
      <el-form-item label="端口" required>
        <el-input-number v-model="form.port" :min="1" :max="65535" style="width: 100%" />
      </el-form-item>
      <el-form-item label="库名">
        <el-input v-model="form.database_name" />
      </el-form-item>
      <el-form-item label="用户名">
        <el-input v-model="form.username" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" show-password :placeholder="editing ? '留空或 **** 开头则不修改' : ''" />
      </el-form-item>
      <el-form-item label="环境">
        <el-select v-model="form.environment" clearable style="width: 100%">
          <el-option v-for="e in environments" :key="e" :label="e" :value="e" />
        </el-select>
      </el-form-item>
      <el-form-item label="容器关联">
        <el-input v-model="form.docker_container" placeholder="容器名或 ID，留空则按实例编码同名匹配" />
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

  <ContainerLogDialog v-model:visible="logVisible" :container-id="logTarget?.container_id || ''" :container-name="logTarget?.name" />

  <el-drawer v-model="auditVisible" title="容器操作记录" size="62%" @open="loadAudits">
    <el-table v-loading="auditLoading" :data="auditItems" border stripe style="width: 100%">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column prop="container_name" label="容器" min-width="150" show-overflow-tooltip />
      <el-table-column prop="managed_type" label="类型" width="100" />
      <el-table-column label="动作" width="90">
        <template #default="{ row }">{{ actionLabel(row.action) }}</template>
      </el-table-column>
      <el-table-column label="结果" width="100">
        <template #default="{ row }">
          <el-tag :type="auditResultType(row.result)" size="small">{{ auditResultLabel(row.result) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="operator" label="操作人" width="120" />
      <el-table-column label="说明" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.detail ? JSON.stringify(row.detail) : '—' }}</template>
      </el-table-column>
    </el-table>
    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="auditTotal"
      v-model:current-page="auditPage"
      v-model:page-size="auditPageSize"
      @current-change="loadAudits"
    />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  checkInstance,
  createInstance,
  deleteInstance,
  fetchOverview,
  listContainerAudits,
  runContainerAction,
  updateInstance,
  type ContainerAction,
  type ContainerAuditItem,
  type ContainerItem,
  type InstanceItem,
  type OverviewItem,
} from '@/modules/database/api'
import { useAuthStore } from '@/core/auth/store'
import {
  MANAGED_TYPES,
  UNREGISTERED_ALL,
  UNREGISTERED_MANAGED,
  isOperable,
  stateLabel,
  stateTagType,
  typeLabel,
  typeSourceLabel,
  typeTagType,
} from '@/modules/database/container-display'
import ContainerActions from '@/modules/database/components/ContainerActions.vue'
import ContainerLogDialog from '@/modules/database/components/ContainerLogDialog.vue'
import UnregisteredContainers from '@/modules/database/components/UnregisteredContainers.vue'

const auth = useAuthStore()
/** 前端按钮门禁；服务端会独立再校验一次，前端隐藏只是 UX */
const canControl = computed(() => auth.canAccess('database:container'))

const items = ref<OverviewItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const degraded = ref(false)
const degradeError = ref<string | null>(null)
const updatedAt = ref('')
const unregistered = ref<ContainerItem[]>([])
const unregisteredTotal = ref(0)
const includeProtected = ref(false)
/** 「未登记容器」筛选：哨兵值或受管类型名 */
const unregisteredFilter = ref<string>(UNREGISTERED_MANAGED)
/** 被「只列受管类型」滤掉的未分类容器数 */
const hiddenUnknown = ref(0)
/** 各类型的未登记数量（后端在类型过滤前统计） */
const countByType = ref<Record<string, number>>({})

const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const logVisible = ref(false)
const logTarget = ref<ContainerItem | null>(null)

const auditVisible = ref(false)
const auditLoading = ref(false)
const auditItems = ref<ContainerAuditItem[]>([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditPageSize = ref(20)

// 台账的 db_type 与容器受管类型对齐（同一份清单），另留一个 other 兜底
const dbTypes = [...MANAGED_TYPES, 'other']
const environments = ['production', 'staging', 'development', 'internal', 'external']

const filters = reactive({ db_type: '' })
const form = reactive({
  instance_code: '',
  instance_name: '',
  db_type: 'mysql',
  host: '',
  port: 3306,
  database_name: '',
  username: '',
  password: '',
  environment: '',
  docker_container: '',
  enabled: true,
})

function healthType(s: string) {
  if (s === 'healthy') return 'success'
  if (s === 'unhealthy') return 'danger'
  return 'info'
}

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

/**
 * 拉取合并视图（台账 + 容器实况）。
 * silent=true 用于 30s 轮询：不翻 v-loading（不闪屏）、不弹错误提示。
 */
async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    // 一个下拉同时表达「作用域」和「类型」：两个哨兵值走 scope，其余取值当类型名。
    const isAll = unregisteredFilter.value === UNREGISTERED_ALL
    const result = await fetchOverview({
      page: page.value,
      page_size: pageSize.value,
      db_type: filters.db_type || undefined,
      include_protected: includeProtected.value,
      unregistered_scope: isAll ? 'all' : 'managed',
      unregistered_type:
        unregisteredFilter.value.startsWith('__') ? undefined : unregisteredFilter.value,
    })
    items.value = result.items
    total.value = result.total
    unregistered.value = result.unregistered
    unregisteredTotal.value = result.unregistered_total
    hiddenUnknown.value = result.unregistered_hidden_unknown
    countByType.value = result.unregistered_by_type
    degraded.value = result.degraded
    degradeError.value = result.error
    updatedAt.value = result.generated_at
  } catch (e: unknown) {
    if (!silent) ElMessage.error(errDetail(e) || '加载失败')
  } finally {
    if (!silent) loading.value = false
  }
}

function onToggleProtected(value: boolean) {
  includeProtected.value = value
  // include_protected 是后端查询参数，切换后必须重新拉
  load()
}

function onChangeFilter(value: string) {
  unregisteredFilter.value = value
  load()
}

function openCreate() {
  editing.value = false
  Object.assign(form, { instance_code: '', instance_name: '', db_type: 'mysql', host: '', port: 3306, database_name: '', username: '', password: '', environment: '', docker_container: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(row: InstanceItem) {
  editing.value = true
  const attributes = (row.attributes || {}) as Record<string, unknown>
  Object.assign(form, {
    instance_code: row.instance_code,
    instance_name: row.instance_name,
    db_type: row.db_type,
    host: row.host,
    port: row.port,
    database_name: row.database_name || '',
    username: row.username || '',
    password: '',
    environment: row.environment || '',
    docker_container: typeof attributes.docker_container === 'string' ? attributes.docker_container : '',
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.instance_code || !form.instance_name || !form.host || !form.port) {
    ElMessage.warning('请填写实例编码、名称、主机和端口')
    return
  }
  saving.value = true
  try {
    const attributes = { ...((items.value.find((i) => i.instance_code === form.instance_code)?.attributes as Record<string, unknown>) || {}) }
    if (form.docker_container) {
      attributes.docker_container = form.docker_container
    } else {
      delete attributes.docker_container
    }
    const payload = {
      instance_name: form.instance_name,
      db_type: form.db_type,
      host: form.host,
      port: form.port,
      database_name: form.database_name || undefined,
      username: form.username || undefined,
      password: form.password || undefined,
      environment: form.environment || undefined,
      attributes,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateInstance(form.instance_code, payload)
    } else {
      await createInstance({ instance_code: form.instance_code, ...payload })
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '保存失败')
  } finally {
    saving.value = false
  }
}

async function check(row: InstanceItem) {
  try {
    const result = await checkInstance(row.instance_code)
    ElMessage.success(`检测完成：${result.health_status}${result.latency_ms != null ? `（${result.latency_ms}ms）` : ''}`)
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '检测失败')
  }
}

async function remove(row: InstanceItem) {
  try {
    await ElMessageBox.confirm(`确定删除实例「${row.instance_name || row.instance_code}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteInstance(row.instance_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '删除失败')
  }
}

function openLog(container: ContainerItem) {
  logTarget.value = container
  logVisible.value = true
}

async function runAction(container: ContainerItem, action: ContainerAction) {
  const verb = { start: '启动', stop: '停止', restart: '重启' }[action]
  try {
    await ElMessageBox.confirm(
      `即将【${verb}】容器「${container.name}」(${container.image})，该操作会中断其服务，确认继续？`,
      '危险操作',
      { type: 'warning', confirmButtonText: verb, cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await runContainerAction(container.container_id, action)
    ElMessage.success(`已${verb}`)
    load(true)
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || `${verb}失败`)
  }
}

function openAudits() {
  auditVisible.value = true
}

async function loadAudits() {
  auditLoading.value = true
  try {
    const result = await listContainerAudits({ page: auditPage.value, page_size: auditPageSize.value })
    auditItems.value = result.items
    auditTotal.value = result.total
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '加载操作记录失败')
  } finally {
    auditLoading.value = false
  }
}

function actionLabel(action: string) {
  return { start: '启动', stop: '停止', restart: '重启' }[action] || action
}

function auditResultLabel(result: string) {
  return { success: '成功', failed: '失败', refused: '已拒绝' }[result] || result
}

function auditResultType(result: string) {
  if (result === 'success') return 'success'
  if (result === 'refused') return 'warning'
  return 'danger'
}

function search() {
  page.value = 1
  load()
}
function reset() {
  filters.db_type = ''
  search()
}

// 30s 静默轮询：仅在页面可见且没有在途请求时刷新。
// 组件卸载必须清掉定时器（全站此前没有任何轮询，这是第一处）。
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  load()
  timer = setInterval(() => {
    if (document.visibilityState === 'visible' && !loading.value) load(true)
  }, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
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
  align-items: center;
  gap: 8px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.search-bar {
  margin-bottom: 8px;
}
.container-name {
  margin-top: 4px;
  font-size: 12px;
}
.container-image {
  overflow: hidden;
  color: #909399;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
