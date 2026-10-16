<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>采集端管理</span>
        <el-button @click="load">刷新</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="source_id" label="采集端标识" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'online' ? 'success' : 'info'" size="small">
            {{ row.status === 'online' ? '在线' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_seen_at" label="最近上报时间" min-width="170" />
      <el-table-column prop="batch_count" label="批次" width="90" />
      <el-table-column prop="log_count" label="日志总量" width="100" />
      <el-table-column prop="device_count" label="设备数" width="90" />
      <el-table-column prop="received" label="接收" width="90" />
      <el-table-column prop="accepted" label="接受" width="90" />
      <el-table-column prop="rejected" label="拒绝" width="90" />
    </el-table>

    <el-empty v-if="!loading && items.length === 0" description="暂无采集端上报数据" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listCollectors, type CollectorItem } from '@/api/client'

const items = ref<CollectorItem[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = await listCollectors()
  } finally {
    loading.value = false
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
</style>
