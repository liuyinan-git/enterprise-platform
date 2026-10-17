<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>部署节点（模型服务所在服务器）</span>
        <el-button type="primary" @click="openCreate">新增节点</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="provider_code" label="节点编码" min-width="130" show-overflow-tooltip />
      <el-table-column prop="provider_name" label="节点名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="provider_type" label="接口协议" width="120" />
      <el-table-column prop="base_url" label="服务器地址" min-width="220" show-overflow-tooltip />
      <el-table-column prop="api_key_masked" label="API 密钥" width="120" />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDiscover(row)">发现模型</el-button>
          <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑节点' : '新增节点'" width="520px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="节点编码" required>
        <el-input v-model="form.provider_code" :disabled="editing" />
      </el-form-item>
      <el-form-item label="节点名称" required>
        <el-input v-model="form.provider_name" placeholder="如：内网GPU节点1（8×H20）" />
      </el-form-item>
      <el-form-item label="接口协议">
        <el-select v-model="form.provider_type" style="width: 100%">
          <el-option v-for="t in providerTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="服务器地址">
        <el-input v-model="form.base_url" placeholder="如：http://172.28.110.11" />
      </el-form-item>
      <el-form-item label="容器代理地址">
        <el-input v-model="form.container_proxy_url" placeholder="该节点 docker-proxy 地址，如 http://172.28.110.11:2375；留空用全局默认" />
      </el-form-item>
      <el-form-item label="API 密钥">
        <el-input v-model="form.api_key" type="password" show-password :placeholder="editing ? '留空或 **** 开头则不修改' : ''" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="discoverVisible" :title="`发现模型 · ${discoveringCode}`" width="720px">
    <el-alert
      v-if="discoverDegraded"
      type="warning"
      :closable="false"
      show-icon
      title="容器代理不可达（未启用或该节点 docker-proxy 无法连接），无法扫描"
      style="margin-bottom: 12px"
    />
    <div class="discover-toolbar">
      <span class="discover-count">未登记容器 {{ discoverItems.length }} 个</span>
      <el-switch v-model="discoverOnlySuggested" active-text="只看疑似模型" />
    </div>
    <el-table v-loading="discoverLoading" :data="discoverFiltered" border stripe max-height="420" style="width: 100%">
      <el-table-column label="" width="60">
        <template #default="{ row }">
          <el-tag v-if="row.suggested" type="success" size="small">疑似</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="容器名" min-width="160" show-overflow-tooltip />
      <el-table-column prop="image" label="镜像" min-width="180" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.state === 'running' ? 'success' : 'info'" size="small">{{ row.state }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="端口" width="120">
        <template #default="{ row }">{{ portsText(row) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openOnboard(row)">登记为模型</el-button>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="discoverVisible = false">关闭</el-button>
      <el-button @click="loadDiscover">重新扫描</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="onboardVisible" :title="`登记模型 · ${onboardForm.name}`" width="480px">
    <el-form :model="onboardForm" label-width="100px">
      <el-form-item label="模型编码">
        <el-input :model-value="onboardForm.name" disabled />
      </el-form-item>
      <el-form-item label="模型名" required>
        <el-input v-model="onboardForm.model_name" />
      </el-form-item>
      <el-form-item label="服务类型">
        <el-select v-model="onboardForm.service_type" style="width: 100%">
          <el-option v-for="t in SERVICE_TYPES" :key="t.value" :label="`${t.label}（${t.value}）`" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="服务地址">
        <el-input v-model="onboardForm.endpoint_url" placeholder="服务根地址，不含 /v1，如 http://172.28.110.11:8033" />
      </el-form-item>
      <el-form-item label="探测方式">
        <el-select v-model="onboardForm.probe_method" style="width: 100%">
          <el-option v-for="m in PROBE_METHODS" :key="m.value" :label="m.label" :value="m.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="onboardVisible = false">取消</el-button>
      <el-button type="primary" :loading="onboardSaving" @click="saveOnboard">登记</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createModel,
  createProvider,
  deleteProvider,
  discoverModels,
  listProviders,
  updateProvider,
  type DiscoveredContainer,
  type ProviderItem,
} from '@/modules/model/api'

const items = ref<ProviderItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const providerTypes = ['openai', 'deepseek', 'ollama', 'anthropic', 'other']

const SERVICE_TYPES: Array<{ value: string; label: string }> = [
  { value: 'chat', label: '对话' },
  { value: 'embedding', label: '向量化' },
  { value: 'rerank', label: '重排序' },
  { value: 'ocr', label: '文字识别' },
  { value: 'asr', label: '语音识别' },
  { value: 'vision', label: '视觉理解' },
  { value: 'tts', label: '语音合成' },
  { value: 'image', label: '图像生成' },
  { value: 'other', label: '其他' },
]

const PROBE_METHODS: Array<{ value: string; label: string }> = [
  { value: 'openai', label: 'OpenAI 兼容' },
  { value: 'tcp', label: '端口探活' },
  { value: 'http', label: 'HTTP 探活' },
  { value: 'none', label: '不探测' },
]

const form = reactive({
  provider_code: '',
  provider_name: '',
  provider_type: 'openai',
  base_url: '',
  api_key: '',
  container_proxy_url: '',
  enabled: true,
})

const discoverVisible = ref(false)
const discoverLoading = ref(false)
const discoverDegraded = ref(false)
const discoverOnlySuggested = ref(false)
const discoverItems = ref<DiscoveredContainer[]>([])
const discoveringCode = ref('')
const discoverFiltered = computed(() =>
  discoverOnlySuggested.value ? discoverItems.value.filter((c) => c.suggested) : discoverItems.value,
)
const onboardVisible = ref(false)
const onboardSaving = ref(false)
const onboardForm = reactive({
  name: '',
  model_name: '',
  service_type: 'chat',
  endpoint_url: '',
  probe_method: 'openai',
})

async function load() {
  loading.value = true
  try {
    const result = await listProviders({ page: page.value, page_size: pageSize.value })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, { provider_code: '', provider_name: '', provider_type: 'openai', base_url: '', api_key: '', container_proxy_url: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(row: ProviderItem) {
  editing.value = true
  Object.assign(form, {
    provider_code: row.provider_code,
    provider_name: row.provider_name,
    provider_type: row.provider_type,
    base_url: row.base_url,
    api_key: '',
    container_proxy_url: row.container_proxy_url || '',
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.provider_code || !form.provider_name) {
    ElMessage.warning('请填写节点编码和节点名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      provider_name: form.provider_name,
      provider_type: form.provider_type,
      base_url: form.base_url,
      api_key: form.api_key || undefined,
      container_proxy_url: form.container_proxy_url,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateProvider(form.provider_code, payload)
    } else {
      await createProvider({ provider_code: form.provider_code, ...payload })
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: ProviderItem) {
  await ElMessageBox.confirm(`确定删除节点「${row.provider_name || row.provider_code}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteProvider(row.provider_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

function portsText(c: DiscoveredContainer): string {
  if (!c.ports?.length) return '—'
  return c.ports
    .filter((p) => p.public != null || p.private != null)
    .map((p) => (p.public != null ? `${p.public}:${p.private ?? ''}` : `${p.private}`))
    .join(', ')
}

async function openDiscover(row: ProviderItem) {
  discoveringCode.value = row.provider_code
  discoverOnlySuggested.value = false
  discoverVisible.value = true
  await loadDiscover()
}

async function loadDiscover() {
  discoverLoading.value = true
  try {
    const result = await discoverModels(discoveringCode.value)
    discoverDegraded.value = result.degraded
    discoverItems.value = result.containers
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '扫描失败')
  } finally {
    discoverLoading.value = false
  }
}

function openOnboard(row: DiscoveredContainer) {
  Object.assign(onboardForm, {
    name: row.name,
    model_name: row.name,
    service_type: 'chat',
    endpoint_url: '',
    probe_method: 'openai',
  })
  onboardVisible.value = true
}

async function saveOnboard() {
  if (!onboardForm.model_name) {
    ElMessage.warning('请填写模型名')
    return
  }
  onboardSaving.value = true
  try {
    await createModel({
      model_code: onboardForm.name,
      provider_code: discoveringCode.value,
      model_name: onboardForm.model_name,
      service_type: onboardForm.service_type,
      endpoint_url: onboardForm.endpoint_url,
      probe_method: onboardForm.probe_method,
    })
    ElMessage.success('已登记模型')
    onboardVisible.value = false
    await loadDiscover()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '登记失败')
  } finally {
    onboardSaving.value = false
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
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.discover-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.discover-count {
  color: #909399;
  font-size: 13px;
}
</style>
