<template>
  <el-dialog
    :model-value="visible"
    :title="editing ? '编辑端点' : '新增端点'"
    width="620px"
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form :model="form" label-width="110px">
      <el-form-item label="端点编码" required>
        <el-input v-model="form.endpoint_code" :disabled="editing" placeholder="如 hermes-gateway" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="服务类型" required>
        <!-- LangGraph 页锁死 service_type，避免在错误的页面建出错误类型的端点 -->
        <el-input v-if="fixedServiceType" :model-value="serviceTypeLabel(fixedServiceType)" disabled />
        <el-select v-else v-model="form.service_type" style="width: 100%">
          <el-option v-for="t in SERVICE_TYPES" :key="t" :label="serviceTypeLabel(t)" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="分组">
        <el-input v-model="form.group" placeholder="选填，用于筛选用" />
      </el-form-item>
      <el-form-item v-if="isLangGraph" label="图名">
        <el-input v-model="form.graph_name" placeholder="选填，写入 attributes.graph_name" />
      </el-form-item>
      <el-form-item label="请求方法">
        <el-select v-model="form.method" style="width: 120px">
          <el-option v-for="m in METHODS" :key="m" :label="m" :value="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="URL" required>
        <el-input v-model="form.url" placeholder="http://host:port/path" />
      </el-form-item>
      <el-form-item label="请求头">
        <el-input
          v-model="form.headersText"
          type="textarea"
          :rows="3"
          placeholder='JSON，如 {"Authorization": "Bearer xxx"}，留空表示无'
        />
      </el-form-item>
      <el-form-item label="请求体">
        <el-input
          v-model="form.bodyText"
          type="textarea"
          :rows="3"
          placeholder='JSON，仅 POST/PUT/PATCH/DELETE 时发送，留空表示无'
        />
      </el-form-item>
      <el-form-item label="期望状态码">
        <el-input
          v-model="form.expectedText"
          placeholder="逗号分隔，如 200,401；留空则按 2xx 为健康"
        />
        <div class="hint">把 401/403 填进来可表达「需要鉴权但服务可达」。</div>
      </el-form-item>
      <el-form-item label="超时（秒）">
        <el-input-number v-model="form.timeout_seconds" :min="1" :max="60" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createEndpoint,
  updateEndpoint,
  type EndpointInput,
  type EndpointItem,
} from '@/modules/agent/api'
import { SERVICE_TYPES, serviceTypeLabel } from '@/modules/agent/display'

const METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']

const props = defineProps<{
  visible: boolean
  /** 传入表示编辑，null 表示新增 */
  endpoint: EndpointItem | null
  /** 锁死服务类型（LangGraph 页传 'langgraph'），新增时不显示类型下拉 */
  fixedServiceType?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'saved'): void
}>()

const saving = ref(false)
const editing = computed(() => Boolean(props.endpoint))

const form = reactive({
  endpoint_code: '',
  name: '',
  service_type: props.fixedServiceType || 'custom',
  group: '',
  graph_name: '',
  method: 'GET',
  url: '',
  headersText: '',
  bodyText: '',
  expectedText: '',
  timeout_seconds: 5,
  enabled: true,
  description: '',
})

const isLangGraph = computed(() => (props.fixedServiceType || form.service_type) === 'langgraph')

watch(
  () => [props.visible, props.endpoint] as const,
  ([visible, endpoint]) => {
    if (!visible) return
    if (endpoint) {
      const attributes = (endpoint.attributes || {}) as Record<string, unknown>
      Object.assign(form, {
        endpoint_code: endpoint.endpoint_code,
        name: endpoint.name,
        service_type: endpoint.service_type,
        group: endpoint.group || '',
        graph_name: typeof attributes.graph_name === 'string' ? attributes.graph_name : '',
        method: endpoint.method || 'GET',
        url: endpoint.url,
        headersText: endpoint.headers ? JSON.stringify(endpoint.headers, null, 2) : '',
        bodyText: endpoint.request_body ? JSON.stringify(endpoint.request_body, null, 2) : '',
        expectedText: (endpoint.expected_status || []).join(','),
        timeout_seconds: endpoint.timeout_seconds || 5,
        enabled: endpoint.enabled,
        description: endpoint.description || '',
      })
    } else {
      Object.assign(form, {
        endpoint_code: '',
        name: '',
        service_type: props.fixedServiceType || 'custom',
        group: '',
        graph_name: '',
        method: 'GET',
        url: '',
        headersText: '',
        bodyText: '',
        expectedText: '',
        timeout_seconds: 5,
        enabled: true,
        description: '',
      })
    }
  },
  { immediate: true },
)

/** 解析一个「留空即无」的 JSON 文本域。返回 undefined 表示留空，抛错表示格式非法。 */
function parseJson(text: string, label: string): Record<string, unknown> | unknown[] | undefined {
  const trimmed = text.trim()
  if (!trimmed) return undefined
  try {
    return JSON.parse(trimmed) as Record<string, unknown> | unknown[]
  } catch {
    throw new Error(`${label} 不是合法 JSON`)
  }
}

function parseExpected(text: string): number[] {
  return text
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item >= 100 && item <= 599)
}

async function save() {
  if (!form.endpoint_code || !form.name || !form.url) {
    ElMessage.warning('请填写端点编码、名称和 URL')
    return
  }
  let payload: EndpointInput
  try {
    const attributes: Record<string, unknown> = isLangGraph.value && form.graph_name ? { graph_name: form.graph_name } : {}
    payload = {
      endpoint_code: form.endpoint_code,
      name: form.name,
      service_type: props.fixedServiceType || form.service_type,
      group: form.group || undefined,
      url: form.url,
      method: form.method,
      headers: parseJson(form.headersText, '请求头') as Record<string, unknown> | undefined,
      request_body: parseJson(form.bodyText, '请求体'),
      expected_status: parseExpected(form.expectedText),
      timeout_seconds: form.timeout_seconds,
      enabled: form.enabled,
      description: form.description || undefined,
      attributes,
    }
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '表单内容有误')
    return
  }

  saving.value = true
  try {
    if (editing.value) {
      await updateEndpoint(form.endpoint_code, payload)
    } else {
      await createEndpoint(payload)
    }
    ElMessage.success('已保存')
    emit('update:visible', false)
    emit('saved')
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.hint {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}
</style>
