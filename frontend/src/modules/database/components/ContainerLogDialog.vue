<template>
  <el-dialog
    :model-value="visible"
    :title="`容器日志 · ${containerName || containerId}`"
    width="880px"
    @update:model-value="emit('update:visible', $event)"
    @open="load"
  >
    <div class="toolbar">
      <el-select v-model="tail" size="small" style="width: 150px" @change="load">
        <el-option :value="100" label="最近 100 行" />
        <el-option :value="200" label="最近 200 行" />
        <el-option :value="500" label="最近 500 行" />
        <el-option :value="1000" label="最近 1000 行" />
      </el-select>
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
      <span v-if="truncated" class="hint">日志过长，仅显示末尾部分</span>
    </div>
    <pre v-loading="loading" class="log-body">{{ text || '（暂无日志）' }}</pre>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchContainerLogs } from '@/modules/database/api'

const props = defineProps<{
  visible: boolean
  containerId: string
  containerName?: string
}>()

const emit = defineEmits<{ (e: 'update:visible', value: boolean): void }>()

const loading = ref(false)
const text = ref('')
const truncated = ref(false)
const tail = ref(200)

async function load() {
  if (!props.containerId) return
  loading.value = true
  try {
    const result = await fetchContainerLogs(props.containerId, tail.value)
    text.value = result.text
    truncated.value = result.truncated
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '日志拉取失败')
    text.value = ''
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.log-body {
  max-height: 60vh;
  margin: 0;
  padding: 12px;
  overflow: auto;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre;
}
</style>
