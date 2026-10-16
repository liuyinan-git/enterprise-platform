<template>
  <el-card>
    <template #header>
      <span>用量统计</span>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="model_code" label="模型编码" min-width="160" show-overflow-tooltip />
      <el-table-column prop="recorded_day" label="日期" width="120" />
      <el-table-column prop="call_count" label="调用次数" width="120" />
      <el-table-column prop="input_tokens" label="输入 tokens" width="130" />
      <el-table-column prop="output_tokens" label="输出 tokens" width="130" />
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
import { listUsages, type UsageItem } from '@/modules/model/api'

const items = ref<UsageItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const result = await listUsages({ page: page.value, page_size: pageSize.value })
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
