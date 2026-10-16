<template>
  <el-row :gutter="16" class="stat-row">
    <el-col v-for="card in cards" :key="card.label" :xs="12" :sm="8" :md="6" :lg="3">
      <el-card shadow="never" class="stat-card">
        <div class="stat-value" :class="card.tone">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import type { StatCard } from '@/modules/agent/display'

defineProps<{ cards: StatCard[] }>()
</script>

<style scoped>
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  margin-bottom: 16px;
  text-align: center;
}
.stat-value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.3;
}
.stat-value.ok {
  color: #67c23a;
}
.stat-value.warn {
  color: #e6a23c;
}
.stat-value.bad {
  color: #f56c6c;
}
.stat-label {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}
</style>
