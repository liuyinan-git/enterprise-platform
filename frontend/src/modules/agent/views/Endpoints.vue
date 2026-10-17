<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>{{ fixedServiceType ? `${serviceTypeLabel(fixedServiceType)} 管理` : 'AI 服务接口监控' }}</span>
        <div class="header-actions">
          <span v-if="lastBatch" class="hint">{{ lastBatch }}</span>
          <el-button size="small" @click="load()">刷新</el-button>
          <el-button size="small" :loading="checking" :disabled="!canEdit" @click="checkBatch">批量检查</el-button>
          <el-button type="primary" :disabled="!canEdit" @click="openCreate">新增端点</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="关键词">
        <el-input v-model="filters.q" placeholder="编码 / 名称 / URL" clearable style="width: 180px" />
      </el-form-item>
      <el-form-item v-if="!fixedServiceType" label="服务类型">
        <el-select v-model="filters.service_type" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="t in SERVICE_TYPES" :key="t" :label="serviceTypeLabel(t)" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="分组">
        <el-select v-model="filters.group" clearable filterable placeholder="全部" style="width: 150px">
          <el-option v-for="g in groups" :key="g" :label="g" :value="g" />
        </el-select>
      </el-form-item>
      <el-form-item label="健康状态">
        <el-select v-model="filters.health_status" clearable placeholder="全部" style="width: 130px">
          <el-option v-for="s in HEALTH_STATUSES" :key="s" :label="healthLabel(s)" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <template #empty>
        <el-empty :description="fixedServiceType ? '还没有登记 LangGraph 端点' : '还没有登记端点'" :image-size="80" />
      </template>
      <el-table-column prop="endpoint_code" label="端点编码" min-width="140" show-overflow-tooltip />
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column v-if="!fixedServiceType" label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="serviceTypeTagType(row.service_type)" size="small">{{ serviceTypeLabel(row.service_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="group" label="分组" width="110" show-overflow-tooltip />
      <el-table-column v-if="fixedServiceType" label="图名" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">{{ graphName(row) }}</template>
      </el-table-column>
      <el-table-column label="请求" min-width="280">
        <template #default="{ row }">
          <div class="url-cell">
            <el-tag size="small" effect="plain">{{ row.method }}</el-tag>
            <span class="url-text" :title="row.url">{{ row.url }}</span>
            <el-button link size="small" @click="copy(row.url)">复制</el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="健康" width="100">
        <template #default="{ row }">
          <el-tooltip
            placement="top"
            :content="row.last_error || (row.expected_status.length ? `期望状态码 ${row.expected_status.join('/')}` : '按 2xx 判定')"
          >
            <el-tag :type="healthTagType(row.health_status)" size="small">{{ healthLabel(row.health_status) }}</el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="last_http_status" label="HTTP" width="80" />
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">{{ row.last_latency_ms == null ? '—' : `${row.last_latency_ms}ms` }}</template>
      </el-table-column>
      <el-table-column label="连续失败" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.consecutive_failures" type="danger" size="small" effect="plain">{{ row.consecutive_failures }}</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="最近检查" width="180">
        <template #default="{ row }">{{ row.last_check_at || '未检查' }}</template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="290" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :disabled="!canEdit" :loading="checkingCode === row.endpoint_code" @click="check(row)">
            检测
          </el-button>
          <el-button size="small" @click="openHistory(row)">历史</el-button>
          <el-button size="small" :disabled="!canEdit" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" :disabled="!canEdit" @click="remove(row)">删除</el-button>
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
      @size-change="search"
    />
  </el-card>

  <EndpointFormDialog
    v-model:visible="dialogVisible"
    :endpoint="editingEndpoint"
    :fixed-service-type="fixedServiceType"
    @saved="load()"
  />

  <!-- 检测结果弹窗：把响应摘要露出来，否则用户只知道「失败了」不知道为什么 -->
  <el-dialog v-model="resultVisible" title="检测结果" width="560px">
    <el-descriptions v-if="lastResult" :column="1" border>
      <el-descriptions-item label="端点">{{ lastResult.endpoint_code }}</el-descriptions-item>
      <el-descriptions-item label="结果">
        <el-tag :type="healthTagType(lastResult.status)" size="small">{{ healthLabel(lastResult.status) }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="HTTP 状态码">{{ lastResult.http_status ?? '—' }}</el-descriptions-item>
      <el-descriptions-item label="耗时">{{ lastResult.latency_ms == null ? '—' : `${lastResult.latency_ms}ms` }}</el-descriptions-item>
      <el-descriptions-item label="连续失败">{{ lastResult.consecutive_failures }}</el-descriptions-item>
      <el-descriptions-item label="错误">{{ lastResult.error || '—' }}</el-descriptions-item>
      <el-descriptions-item v-if="lastResult.body_excerpt" label="响应摘要">
        <pre class="excerpt">{{ lastResult.body_excerpt }}</pre>
      </el-descriptions-item>
    </el-descriptions>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  checkEndpoint,
  checkEndpointsBatch,
  deleteEndpoint,
  fetchEndpointOptions,
  listEndpoints,
  type CheckResultItem,
  type EndpointItem,
} from '@/modules/agent/api'
import { useAuthStore } from '@/core/auth/store'
import { copyText } from '@/core/util/clipboard'
import {
  HEALTH_STATUSES,
  SERVICE_TYPES,
  healthLabel,
  healthTagType,
  serviceTypeLabel,
  serviceTypeTagType,
} from '@/modules/agent/display'
import EndpointFormDialog from '@/modules/agent/components/EndpointFormDialog.vue'

/**
 * 传入则锁定服务类型（LangGraph 页传 'langgraph'）：
 * 隐藏类型筛选与类型列、多显示「图名」列、表单里类型不可改。
 */
const props = defineProps<{ fixedServiceType?: string }>()

const auth = useAuthStore()
const router = useRouter()
/** 端点写操作与检测的门禁；服务端会独立再校验一次 */
const canEdit = computed(() => auth.canAccess('agent:manage'))

const items = ref<EndpointItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const checking = ref(false)
const checkingCode = ref('')
const groups = ref<string[]>([])
const lastBatch = ref('')

const dialogVisible = ref(false)
const editingEndpoint = ref<EndpointItem | null>(null)

const resultVisible = ref(false)
const lastResult = ref<CheckResultItem | null>(null)

const filters = reactive({ q: '', service_type: '', group: '', health_status: '' })

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

function graphName(row: EndpointItem): string {
  const value = (row.attributes || {})['graph_name']
  return typeof value === 'string' && value ? value : '—'
}

async function load() {
  loading.value = true
  try {
    const result = await listEndpoints({
      page: page.value,
      page_size: pageSize.value,
      q: filters.q || undefined,
      service_type: props.fixedServiceType || filters.service_type || undefined,
      group: filters.group || undefined,
      health_status: filters.health_status || undefined,
    })
    items.value = result.items
    total.value = result.total
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  try {
    const result = await fetchEndpointOptions()
    groups.value = result.groups
  } catch {
    // 下拉项拿不到不影响主表
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.q = ''
  filters.service_type = ''
  filters.group = ''
  filters.health_status = ''
  search()
}

function openCreate() {
  editingEndpoint.value = null
  dialogVisible.value = true
}

function openEdit(row: EndpointItem) {
  editingEndpoint.value = row
  dialogVisible.value = true
}

async function copy(text: string) {
  const okFlag = await copyText(text)
  if (okFlag) ElMessage.success('已复制')
  else ElMessage.warning('复制失败，请手动选中')
}

async function check(row: EndpointItem) {
  checkingCode.value = row.endpoint_code
  try {
    lastResult.value = await checkEndpoint(row.endpoint_code)
    resultVisible.value = true
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '检测失败')
  } finally {
    checkingCode.value = ''
  }
}

async function checkBatch() {
  const scope = props.fixedServiceType
    ? serviceTypeLabel(props.fixedServiceType)
    : '全部启用中的端点'
  try {
    await ElMessageBox.confirm(`即将批量检查${scope}，耗时取决于端点数量与超时设置，确认继续？`, '批量检查', {
      type: 'info',
      confirmButtonText: '开始',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  checking.value = true
  try {
    const codes = props.fixedServiceType ? items.value.map((i) => i.endpoint_code) : undefined
    const result = await checkEndpointsBatch(codes?.length ? codes : undefined)
    const s = result.summary
    lastBatch.value = `刚检查 ${result.total} 个：正常 ${s.healthy || 0} / 异常 ${s.unhealthy || 0} / 超时 ${s.timeout || 0} / 不可达 ${s.error || 0}`
    ElMessage.success(lastBatch.value)
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '批量检查失败')
  } finally {
    checking.value = false
  }
}

async function remove(row: EndpointItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除监控配置「${row.name}」？删除的只是监控配置，不会删除任何实际容器或服务；历史记录会保留。`,
      '提示',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteEndpoint(row.endpoint_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '删除失败')
  }
}

function openHistory(row: EndpointItem) {
  router.push({ path: '/agent/history', query: { endpoint_code: row.endpoint_code } })
}

// 切换固定类型（同一个组件被两个路由复用）时重新拉数
watch(() => props.fixedServiceType, () => search())

onMounted(() => {
  load()
  loadOptions()
})
</script>

<style scoped>
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
.url-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.url-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.excerpt {
  max-height: 200px;
  margin: 0;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
}
</style>
