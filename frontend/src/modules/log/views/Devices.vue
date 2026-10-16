<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>设备管理</span>
        <el-button type="primary" @click="openCreate">登记设备</el-button>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="设备类型">
        <el-select v-model="filters.device_type" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="t in deviceTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用状态">
        <el-select v-model="filters.enabled" placeholder="全部" clearable style="width: 120px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="device_id" label="设备 ID" min-width="130" show-overflow-tooltip />
      <el-table-column prop="device_name" label="设备名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="device_type" label="类型" width="100" />
      <el-table-column prop="hostname" label="主机名" min-width="110" show-overflow-tooltip />
      <el-table-column label="容器 ID" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.attributes?.container_id || '—' }}</template>
      </el-table-column>
      <el-table-column prop="ip_address" label="IP 地址" min-width="120" />
      <el-table-column prop="environment" label="环境" width="100" />
      <el-table-column prop="criticality" label="重要性" width="90">
        <template #default="{ row }">
          <el-tag :type="criticalityType(row.criticality)" size="small">{{ row.criticality }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="接收人" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.touser || '—' }}</template>
      </el-table-column>
      <el-table-column prop="expected_interval_seconds" label="上报周期(秒)" width="110" />
      <el-table-column prop="last_seen_at" label="最后上报" min-width="170" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'online' ? 'success' : 'info'" size="small">
            {{ row.status === 'online' ? '在线' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑设备' : '登记设备'" width="520px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="设备 ID" required>
        <el-input v-model="form.device_id" placeholder="如 server-000" :disabled="editing" />
      </el-form-item>
      <el-form-item label="设备名称" required>
        <el-input v-model="form.device_name" placeholder="如 核心服务器" />
      </el-form-item>
      <el-form-item label="设备类型">
        <el-select v-model="form.device_type" style="width: 100%">
          <el-option v-for="t in deviceTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="主机名">
        <el-input v-model="form.hostname" />
      </el-form-item>
      <el-form-item label="IP 地址">
        <el-input v-model="form.ip_address" />
      </el-form-item>
      <el-form-item label="环境">
        <el-select v-model="form.environment" clearable style="width: 100%">
          <el-option v-for="e in environments" :key="e" :label="e" :value="e" />
        </el-select>
      </el-form-item>
      <el-form-item label="重要性">
        <el-select v-model="form.criticality" style="width: 100%">
          <el-option v-for="c in criticalities" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="上报周期(秒)">
        <el-input-number v-model="form.expected_interval_seconds" :min="1" style="width: 100%" />
      </el-form-item>
      <el-form-item label="接收人">
        <el-input v-model="form.touser" placeholder="UserID，留空则用全局；多人用 | 分隔" />
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
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteDevice, listDevices, registerDevice, type DeviceItem } from '@/modules/log/api'

const items = ref<DeviceItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const deviceTypes = ['server', 'firewall', 'router', 'switch', 'pc', 'rpa', 'application', 'database', 'other']
const environments = ['production', 'staging', 'development', 'internal', 'external']
const criticalities = ['critical', 'high', 'normal', 'low']

const filters = reactive({ device_type: '', enabled: undefined as boolean | undefined })

const form = reactive({
  device_id: '',
  device_name: '',
  device_type: 'server',
  hostname: '',
  ip_address: '',
  environment: '',
  criticality: 'normal',
  expected_interval_seconds: 900,
  touser: '',
  enabled: true,
})

function criticalityType(c: string) {
  if (c === 'critical') return 'danger'
  if (c === 'high') return 'warning'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const result = await listDevices({
      page: page.value,
      page_size: pageSize.value,
      device_type: filters.device_type || undefined,
      enabled: filters.enabled,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  form.device_id = ''
  form.device_name = ''
  form.device_type = 'server'
  form.hostname = ''
  form.ip_address = ''
  form.environment = ''
  form.criticality = 'normal'
  form.expected_interval_seconds = 900
  form.touser = ''
  form.enabled = true
  dialogVisible.value = true
}

function openEdit(row: DeviceItem) {
  editing.value = true
  form.device_id = row.device_id
  form.device_name = row.device_name
  form.device_type = row.device_type
  form.hostname = row.hostname || ''
  form.ip_address = row.ip_address || ''
  form.environment = row.environment || ''
  form.criticality = row.criticality
  form.expected_interval_seconds = row.expected_interval_seconds
  form.touser = row.touser || ''
  form.enabled = row.enabled
  dialogVisible.value = true
}

async function save() {
  if (!form.device_id || !form.device_name) {
    ElMessage.warning('请填写设备 ID 和名称')
    return
  }
  saving.value = true
  try {
    await registerDevice({
      device_id: form.device_id,
      device_name: form.device_name,
      device_type: form.device_type,
      hostname: form.hostname || undefined,
      ip_address: form.ip_address || undefined,
      environment: form.environment || undefined,
      criticality: form.criticality,
      expected_interval_seconds: form.expected_interval_seconds,
      touser: form.touser || undefined,
      enabled: form.enabled,
    })
    ElMessage.success('已保存')
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '登记失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: DeviceItem) {
  await ElMessageBox.confirm(`确定删除设备「${row.device_name || row.device_id}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteDevice(row.device_id)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.device_type = ''
  filters.enabled = undefined
  search()
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
