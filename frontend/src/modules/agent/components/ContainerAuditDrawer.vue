<template>
  <el-drawer
    :model-value="modelValue"
    title="容器操作记录"
    size="62%"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="audit-filter">
      <el-input
        v-model="operator"
        placeholder="按操作人筛选"
        clearable
        size="small"
        style="width: 200px"
        @keyup.enter="search"
        @clear="search"
      />
      <el-button size="small" type="primary" @click="search">查询</el-button>
    </div>
    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column prop="container_name" label="容器" min-width="150" show-overflow-tooltip />
      <el-table-column prop="project_key" label="项目" width="120" />
      <el-table-column label="动作" width="90">
        <template #default="{ row }">{{ actionLabel(row.action) }}</template>
      </el-table-column>
      <el-table-column label="结果" width="100">
        <template #default="{ row }">
          <el-tag :type="auditResultType(row.result)" size="small">{{ auditResultLabel(row.result) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="operator" label="操作人" width="120" />
      <el-table-column label="原因" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ operatorReason(row) }}</template>
      </el-table-column>
      <el-table-column label="说明" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.detail ? JSON.stringify(row.detail) : '—' }}</template>
      </el-table-column>
    </el-table>
    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      @current-change="load"
    />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listContainerAudits,
  type ContainerAuditItem,
} from '@/modules/agent/api'
import { actionLabel, auditResultLabel, auditResultType } from '@/modules/agent/display'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const loading = ref(false)
const items = ref<ContainerAuditItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const operator = ref('')

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

async function load() {
  loading.value = true
  try {
    const result = await listContainerAudits({
      page: page.value,
      page_size: pageSize.value,
      operator: operator.value.trim() || undefined,
    })
    items.value = result.items
    total.value = result.total
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '加载操作记录失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function operatorReason(row: ContainerAuditItem) {
  const value = row.detail?.['operator_reason']
  return typeof value === 'string' && value ? value : '—'
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      page.value = 1
      load()
    }
  },
)
</script>

<style scoped>
.audit-filter {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
