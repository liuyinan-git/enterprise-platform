<template>
  <el-card>
    <template #header>消息发送管理</template>

    <el-form :model="form" label-width="120px" class="config-form">
      <el-form-item label="CorpID（企业 ID）">
        <el-input v-model="form.corpid" placeholder="如 wwd5218df9e8f7d060" />
      </el-form-item>
      <el-form-item label="应用密钥">
        <el-input
          v-model="form.corpsecret"
          type="password"
          show-password
          :placeholder="hasSecret ? '已配置（留空则不修改）' : '应用 Secret'"
        />
      </el-form-item>
      <el-form-item label="AgentID">
        <el-input-number v-model="form.agentid" :min="0" style="width: 200px" />
      </el-form-item>
      <el-form-item label="默认接收人">
        <el-input v-model="form.touser" placeholder="成员 UserID，如 YiNan；多人用 | 分隔" />
      </el-form-item>
      <el-form-item label="通知最低级别">
        <el-select v-model="form.notify_min_severity" style="width: 200px">
          <el-option v-for="s in severityOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用告警推送">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
      </el-form-item>
    </el-form>

    <el-divider content-position="left">测试发送</el-divider>

    <el-form :model="testForm" label-width="120px" class="config-form">
      <el-form-item label="接收人">
        <el-input v-model="testForm.touser" placeholder="留空则用上方默认接收人" style="max-width: 400px" />
      </el-form-item>
      <el-form-item label="消息内容">
        <el-input
          v-model="testForm.content"
          type="textarea"
          :rows="5"
          placeholder="支持 Markdown，如：&#10;# 标题&#10;> 引用内容"
        />
      </el-form-item>
      <el-form-item>
        <el-button :loading="testing" @click="sendTest">发送测试消息</el-button>
        <el-tag v-if="testResult" :type="testResult.ok ? 'success' : 'danger'" class="test-result">
          {{ testResult.ok ? `发送成功（errcode=${testResult.errcode}）` : `发送失败：${testResult.errmsg}` }}
        </el-tag>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getWecomConfig,
  testWecom,
  updateWecomConfig,
  type WecomConfigItem,
} from '@/api/client'

const saving = ref(false)
const testing = ref(false)
const config = ref<WecomConfigItem | null>(null)
const testResult = ref<{ ok: boolean; errcode: number; errmsg: string } | null>(null)

const form = reactive({
  corpid: '',
  corpsecret: '',
  agentid: 0,
  touser: '',
  enabled: false,
  notify_min_severity: 'medium',
})
const testForm = reactive({ touser: '', content: '' })

const severityOptions = [
  { value: 'low', label: '低（全部推送）' },
  { value: 'medium', label: '中（中及以上）' },
  { value: 'high', label: '高（高及以上）' },
  { value: 'critical', label: '严重（仅严重）' },
]

const hasSecret = computed(() => !!config.value?.corpsecret_masked)

async function load() {
  config.value = await getWecomConfig()
  form.corpid = config.value.corpid
  form.corpsecret = '' // 密钥不回显，留空表示不修改
  form.agentid = config.value.agentid
  form.touser = config.value.touser
  form.enabled = config.value.enabled
  form.notify_min_severity = config.value.notify_min_severity
}

async function save() {
  if (!form.corpid || !form.agentid) {
    ElMessage.warning('请填写 CorpID 和 AgentID')
    return
  }
  saving.value = true
  try {
    config.value = await updateWecomConfig({
      corpid: form.corpid,
      corpsecret: form.corpsecret,
      agentid: form.agentid,
      touser: form.touser,
      enabled: form.enabled,
      notify_min_severity: form.notify_min_severity,
    })
    form.corpsecret = ''
    ElMessage.success('已保存')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '保存失败')
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  testing.value = true
  testResult.value = null
  try {
    const result = await testWecom({
      touser: testForm.touser || undefined,
      content: testForm.content || undefined,
    })
    testResult.value = { ok: true, errcode: result.errcode, errmsg: result.errmsg }
    ElMessage.success('发送成功')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    testResult.value = { ok: false, errcode: -1, errmsg: msg || '发送失败' }
    ElMessage.error(msg || '发送失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.config-form {
  max-width: 640px;
}
.test-result {
  margin-left: 12px;
}
</style>
