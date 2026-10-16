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
      <!-- 与 database 模块的日志弹窗唯一的差别：时间戳开关。
           Docker 原生给 UTC，服务端已逐行转成北京时，所以开着也符合平台约定。 -->
      <el-checkbox v-model="timestamps" size="small" @change="load">显示时间戳</el-checkbox>
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
      <span v-if="truncated" class="hint">日志过长，仅显示末尾部分</span>
    </div>
    <pre v-loading="loading" class="log-body">{{ text || '（暂无日志）' }}</pre>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchContainerLogs } from '@/modules/agent/api'

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
const timestamps = ref(true)

async function load() {
  if (!props.containerId) return
  loading.value = true
  try {
    const result = await fetchContainerLogs(props.containerId, {
      tail: tail.value,
      timestamps: timestamps.value,
    })
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
.hint {
  color: #909399;
  font-size: 12px;
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
