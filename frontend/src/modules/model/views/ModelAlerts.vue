<template>
  <el-card>
    <template #header>模型告警</template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="模型">
        <el-select v-model="filters.model_code" placeholder="全部" clearable filterable style="width: 200px">
          <el-option v-for="m in models" :key="m.model_code" :label="m.model_code" :value="m.model_code" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="filters.alert_type" placeholder="全部" clearable style="width: 120px">
          <el-option v-for="t in ALERT_TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.alert_status" placeholder="全部" clearable style="width: 120px">
          <el-option v-for="s in STATUSES" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column label="告警编号" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono">{{ row.alert_no }}</span>
        </template>
      </el-table-column>
      <el-table-column label="模型" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.model_code || '—' }}</template>
      </el-table-column>
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.alert_type === 'failure' ? 'danger' : 'success'" size="small">
            {{ alertTypeLabel(row.alert_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="attempt_count" label="尝试次数" width="90" />
      <el-table-column label="接收人" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.receiver_key || '—' }}</template>
      </el-table-column>
      <el-table-column label="发送时间" min-width="170">
        <template #default="{ row }">{{ row.sent_at || '—' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="170" />
      <el-table-column label="错误信息" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.last_error" class="error-text">{{ row.last_error }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openContent(row)">内容</el-button>
          <el-button
            v-if="row.status !== 'sent'"
            size="small"
            type="primary"
            :loading="row._retrying"
            @click.stop="retry(row)"
          >
            重试
          </el-button>
          <span v-else class="muted">—</span>
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

  <el-drawer v-model="contentVisible" :title="`告警内容 · ${contentRow?.alert_no || ''}`" size="480px">
    <pre class="content-pre">{{ contentRow?.message_content || '（无内容）' }}</pre>
  </el-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listModelAlerts,
  listModels,
  retryModelAlert,
  type ModelAlertItem,
  type ModelItem,
} from '@/modules/model/api'

const ALERT_TYPES = [
  { value: 'failure', label: '故障' },
  { value: 'recovery', label: '恢复' },
]

const STATUSES = [
  { value: 'pending', label: '待发送' },
  { value: 'sent', label: '已送达' },
  { value: 'failed', label: '失败' },
]

const items = ref<(ModelAlertItem & { _retrying?: boolean })[]>([])
const models = ref<ModelItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ model_code: '', alert_type: '', alert_status: '' })

const contentVisible = ref(false)
const contentRow = ref<ModelAlertItem | null>(null)

function alertTypeLabel(v: string) {
  return ALERT_TYPES.find((t) => t.value === v)?.label ?? v
}

function statusType(status: string) {
  if (status === 'sent') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

function statusLabel(status: string) {
  return STATUSES.find((s) => s.value === status)?.label ?? status
}

async function load() {
  loading.value = true
  try {
    const result = await listModelAlerts({
      page: page.value,
      page_size: pageSize.value,
      model_code: filters.model_code || undefined,
      alert_type: filters.alert_type || undefined,
      alert_status: filters.alert_status || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadModels() {
  const result = await listModels({ page_size: 200 })
  models.value = result.items
}

function openContent(row: ModelAlertItem) {
  contentRow.value = row
  contentVisible.value = true
}

async function retry(row: ModelAlertItem & { _retrying?: boolean }) {
  row._retrying = true
  try {
    const result = await retryModelAlert(row.alert_no)
    if (result.status === 'sent') {
      ElMessage.success('重试成功，告警已发送')
    } else {
      ElMessage.error(result.last_error || '重试仍未成功')
    }
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '重试失败')
  } finally {
    row._retrying = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.model_code = ''
  filters.alert_type = ''
  filters.alert_status = ''
  search()
}

onMounted(() => {
  load()
  loadModels()
})
</script>

<style scoped>
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.mono {
  font-family: Consolas, Monaco, 'Courier New', monospace;
}
.muted {
  color: #c0c4cc;
}
.error-text {
  color: #f56c6c;
}
.content-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
