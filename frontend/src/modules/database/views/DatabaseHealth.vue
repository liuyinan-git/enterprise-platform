<template>
  <el-card>
    <template #header>
      <span>健康检查记录</span>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="instance_code" label="实例编码" min-width="150" show-overflow-tooltip />
      <el-table-column prop="check_type" label="检查类型" width="120" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'healthy' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="latency_ms" label="延迟(ms)" width="110" />
      <el-table-column prop="checked_at" label="检查时间" min-width="170" />
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
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listHealth, type HealthItem } from '@/modules/database/api'

const items = ref<HealthItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const result = await listHealth({ page: page.value, page_size: pageSize.value })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
