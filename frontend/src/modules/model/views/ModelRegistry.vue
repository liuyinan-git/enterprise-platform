<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>模型注册</span>
        <el-button type="primary" @click="openCreate">新增模型</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="model_code" label="模型编码" min-width="130" show-overflow-tooltip />
      <el-table-column prop="model_name" label="模型名" min-width="150" show-overflow-tooltip />
      <el-table-column label="服务类型" width="100">
        <template #default="{ row }">
          <el-tag :type="serviceTypeTag(row.service_type)" size="small">{{ serviceTypeLabel(row.service_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="endpoint_url" label="服务地址" min-width="180" show-overflow-tooltip />
      <el-table-column label="探测方式" width="100">
        <template #default="{ row }">{{ probeMethodLabel(row.probe_method) }}</template>
      </el-table-column>
      <el-table-column prop="engine" label="引擎" width="120" show-overflow-tooltip />
      <el-table-column prop="provider_name" label="供应商" width="130" show-overflow-tooltip />
      <el-table-column prop="version" label="版本" width="90" show-overflow-tooltip />
      <el-table-column prop="context_window" label="上下文" width="90" />
      <el-table-column label="健康状态" width="100">
        <template #default="{ row }">
          <el-tag :type="healthType(row.health_status)" size="small">{{ row.health_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="连续失败" width="90">
        <template #default="{ row }">
          <span :class="failClass(row.consecutive_failures)">{{ row.consecutive_failures ?? 0 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="容器" width="110">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.container_status"
            :content="row.container_status_text || row.container_status"
            placement="top"
          >
            <el-tag :type="containerType(row.container_status)" size="small">{{ row.container_status }}</el-tag>
          </el-tooltip>
          <span v-else class="fail-zero">unknown</span>
        </template>
      </el-table-column>
      <el-table-column prop="last_check_at" label="最后检测" min-width="170" />
      <el-table-column label="操作" width="265" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="check(row)">探测</el-button>
          <el-button size="small" @click="openHistory(row)">历史</el-button>
          <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑模型' : '新增模型'" width="520px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="模型编码" required>
        <el-input v-model="form.model_code" :disabled="editing" />
      </el-form-item>
      <el-form-item label="模型名" required>
        <el-input v-model="form.model_name" placeholder="如 deepseek-chat" />
      </el-form-item>
      <el-form-item label="供应商" required>
        <el-select v-model="form.provider_code" style="width: 100%" :disabled="editing">
          <el-option v-for="p in providers" :key="p.provider_code" :label="p.provider_name" :value="p.provider_code" />
        </el-select>
      </el-form-item>
      <el-form-item label="服务类型">
        <el-select v-model="form.service_type" style="width: 100%">
          <el-option v-for="t in SERVICE_TYPES" :key="t.value" :label="`${t.label}（${t.value}）`" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="服务地址">
        <el-input v-model="form.endpoint_url" placeholder="服务根地址，不含 /v1，如 http://172.28.110.11:8033" />
      </el-form-item>
      <el-form-item label="探测方式">
        <el-select v-model="form.probe_method" style="width: 100%">
          <el-option v-for="m in PROBE_METHODS" :key="m.value" :label="m.label" :value="m.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="引擎">
        <el-input v-model="form.engine" placeholder="如 vLLM v0.17.1" />
      </el-form-item>
      <el-form-item label="版本">
        <el-input v-model="form.version" />
      </el-form-item>
      <el-form-item label="上下文长度">
        <el-input-number v-model="form.context_window" :min="0" style="width: 100%" />
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

  <el-drawer v-model="historyVisible" :title="`健康历史 · ${historyTitle}`" size="560px">
    <el-table v-loading="historyLoading" :data="historyItems" border stripe style="width: 100%">
      <el-table-column prop="checked_at" label="检查时间" min-width="170" />
      <el-table-column label="状态" width="95">
        <template #default="{ row }">
          <el-tag :type="healthType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="延迟(ms)" width="90">
        <template #default="{ row }">{{ row.latency_ms ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="消息" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.message || '—' }}</template>
      </el-table-column>
    </el-table>
    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="historyTotal"
      v-model:current-page="historyPage"
      :page-size="HISTORY_PAGE_SIZE"
      @current-change="loadHistory"
    />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  checkModel,
  createModel,
  deleteModel,
  getModelHealth,
  listModels,
  listProviders,
  updateModel,
  type ModelHealthItem,
  type ModelItem,
  type ProviderItem,
} from '@/modules/model/api'

const SERVICE_TYPES: Array<{ value: string; label: string }> = [
  { value: 'chat', label: '对话' },
  { value: 'embedding', label: '向量化' },
  { value: 'rerank', label: '重排序' },
  { value: 'ocr', label: '文字识别' },
  { value: 'asr', label: '语音识别' },
  { value: 'vision', label: '视觉理解' },
  { value: 'tts', label: '语音合成' },
  { value: 'image', label: '图像生成' },
  { value: 'other', label: '其他' },
]

const SERVICE_TAG: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
  chat: 'primary',
  embedding: 'success',
  rerank: 'warning',
  ocr: 'danger',
  asr: 'info',
  vision: 'primary',
  tts: 'success',
  image: 'warning',
  other: 'info',
}

const PROBE_METHODS: Array<{ value: string; label: string }> = [
  { value: 'openai', label: 'OpenAI 兼容' },
  { value: 'tcp', label: '端口探活' },
  { value: 'http', label: 'HTTP 探活' },
  { value: 'none', label: '不探测' },
]

function serviceTypeLabel(v: string) {
  return SERVICE_TYPES.find((t) => t.value === v)?.label ?? v
}

function serviceTypeTag(v: string) {
  return SERVICE_TAG[v] ?? 'info'
}

function probeMethodLabel(v: string) {
  return PROBE_METHODS.find((m) => m.value === v)?.label ?? v
}

const items = ref<ModelItem[]>([])
const providers = ref<ProviderItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const form = reactive({
  model_code: '',
  model_name: '',
  provider_code: '',
  service_type: 'chat',
  endpoint_url: '',
  probe_method: 'openai',
  engine: '',
  version: '',
  context_window: 4096,
  enabled: true,
})

const historyVisible = ref(false)
const historyLoading = ref(false)
const historyItems = ref<ModelHealthItem[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const HISTORY_PAGE_SIZE = 20
const historyModel = ref<ModelItem | null>(null)
const historyTitle = computed(() => historyModel.value?.model_name || historyModel.value?.model_code || '')

function healthType(s: string) {
  if (s === 'healthy') return 'success'
  if (s === 'unhealthy') return 'danger'
  return 'info'
}

function containerType(s: string) {
  if (s === 'running') return 'success'
  if (s === 'exited' || s === 'dead') return 'danger'
  if (s === 'paused' || s === 'restarting' || s === 'created') return 'warning'
  return 'info'
}

function failClass(v: number | null | undefined) {
  const n = v ?? 0
  if (n >= 3) return 'fail-high'
  if (n > 0) return 'fail-mid'
  return 'fail-zero'
}

async function load() {
  loading.value = true
  try {
    const result = await listModels({ page: page.value, page_size: pageSize.value })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadProviders() {
  const result = await listProviders({ page_size: 200 })
  providers.value = result.items
}

function openCreate() {
  editing.value = false
  Object.assign(form, {
    model_code: '',
    model_name: '',
    provider_code: providers.value[0]?.provider_code || '',
    service_type: 'chat',
    endpoint_url: '',
    probe_method: 'openai',
    engine: '',
    version: '',
    context_window: 4096,
    enabled: true,
  })
  dialogVisible.value = true
}

function openEdit(row: ModelItem) {
  editing.value = true
  Object.assign(form, {
    model_code: row.model_code,
    model_name: row.model_name,
    provider_code: row.provider_code || '',
    service_type: row.service_type || 'chat',
    endpoint_url: row.endpoint_url || '',
    probe_method: row.probe_method || 'openai',
    engine: row.engine || '',
    version: row.version || '',
    context_window: row.context_window ?? 4096,
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.model_code || !form.model_name || !form.provider_code) {
    ElMessage.warning('请填写模型编码、模型名和供应商')
    return
  }
  saving.value = true
  try {
    const payload = {
      model_name: form.model_name,
      service_type: form.service_type,
      endpoint_url: form.endpoint_url,
      probe_method: form.probe_method,
      engine: form.engine || undefined,
      version: form.version || undefined,
      context_window: form.context_window,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateModel(form.model_code, payload)
    } else {
      await createModel({ model_code: form.model_code, provider_code: form.provider_code, ...payload })
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

async function check(row: ModelItem) {
  try {
    const result = await checkModel(row.model_code)
    const info = [result.detail, result.latency_ms != null ? `延迟 ${result.latency_ms}ms` : ''].filter(Boolean).join('，')
    const text = info ? `探测完成：${result.health_status}（${info}）` : `探测完成：${result.health_status}`
    if (result.health_status === 'healthy') ElMessage.success(text)
    else if (result.health_status === 'unhealthy') ElMessage.error(text)
    else ElMessage.info(text)
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '探测失败')
  }
}

function openHistory(row: ModelItem) {
  historyModel.value = row
  historyPage.value = 1
  historyVisible.value = true
  loadHistory()
}

async function loadHistory() {
  if (!historyModel.value) return
  historyLoading.value = true
  try {
    const result = await getModelHealth({
      page: historyPage.value,
      page_size: HISTORY_PAGE_SIZE,
      model_code: historyModel.value.model_code,
    })
    historyItems.value = result.items
    historyTotal.value = result.total
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '加载健康历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function remove(row: ModelItem) {
  await ElMessageBox.confirm(`确定删除模型「${row.model_name || row.model_code}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteModel(row.model_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

onMounted(() => {
  load()
  loadProviders()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.fail-zero {
  color: #c0c4cc;
}
.fail-mid {
  color: #e6a23c;
}
.fail-high {
  color: #f56c6c;
  font-weight: 600;
}
</style>
