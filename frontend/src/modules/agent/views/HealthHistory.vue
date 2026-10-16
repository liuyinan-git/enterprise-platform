<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>监控历史</span>
        <div class="header-actions">
          <span v-if="total" class="hint">共 {{ total }} 条</span>
          <el-button size="small" @click="load()">刷新</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="端点">
        <el-select
          v-model="filters.endpoint_code"
          clearable
          filterable
          placeholder="全部"
          style="width: 240px"
        >
          <el-option
            v-for="item in endpointOptions"
            :key="item.endpoint_code"
            :label="`${item.name}（${item.endpoint_code}）`"
            :value="item.endpoint_code"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width: 130px">
          <el-option v-for="s in HEALTH_STATUSES" :key="s" :label="healthLabel(s)" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item label="时间范围">
        <el-date-picker
          v-model="range"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 360px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <template #empty>
        <el-empty description="没有符合条件的记录" :image-size="80" />
      </template>
      <el-table-column prop="checked_at" label="检查时间" width="190" />
      <el-table-column prop="endpoint_code" label="端点编码" min-width="140" show-overflow-tooltip />
      <el-table-column prop="endpoint_name" label="端点名称" min-width="150" show-overflow-tooltip />
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.service_type" :type="serviceTypeTagType(row.service_type)" size="small">
            {{ serviceTypeLabel(row.service_type) }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="healthTagType(row.status)" size="small">{{ healthLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="http_status" label="HTTP" width="80" />
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">{{ row.latency_ms == null ? '—' : `${row.latency_ms}ms` }}</template>
      </el-table-column>
      <el-table-column label="来源" width="100">
        <template #default="{ row }">{{ checkTypeLabel(row.check_type) }}</template>
      </el-table-column>
      <el-table-column prop="error" label="错误" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ row.error || '—' }}</template>
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

    <div class="hint">
      历史记录不随监控配置删除而删除 —— 端点被删掉后，这里仍能查到它过去的状态。
      保留期由 <code>AGENT_HISTORY_RETENTION_DAYS</code> 决定，由周期任务清理。
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  fetchEndpointOptions,
  listHealthHistory,
  type HealthHistoryItem,
} from '@/modules/agent/api'
import {
  HEALTH_STATUSES,
  checkTypeLabel,
  healthLabel,
  healthTagType,
  serviceTypeLabel,
  serviceTypeTagType,
} from '@/modules/agent/display'

const route = useRoute()

const items = ref<HealthHistoryItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const endpointOptions = ref<{ endpoint_code: string; name: string; service_type: string }[]>([])
const range = ref<[string, string] | null>(null)

const filters = reactive({ endpoint_code: '', status: '' })

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

async function load() {
  loading.value = true
  try {
    const result = await listHealthHistory({
      page: page.value,
      page_size: pageSize.value,
      endpoint_code: filters.endpoint_code || undefined,
      status: filters.status || undefined,
      checked_from: range.value?.[0] || undefined,
      checked_to: range.value?.[1] || undefined,
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
    endpointOptions.value = result.items
  } catch {
    // 下拉项拿不到不影响主表
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.endpoint_code = ''
  filters.status = ''
  range.value = null
  search()
}

onMounted(() => {
  // 从「接口监控」页点「历史」跳过来时带着 endpoint_code
  const code = route.query.endpoint_code
  if (typeof code === 'string' && code) filters.endpoint_code = code
  loadOptions()
  load()
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
  margin-top: 12px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
