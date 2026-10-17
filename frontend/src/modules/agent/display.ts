/**
 * AI Agent 平台的纯展示映射：服务类型 / 健康状态 / 容器状态 / 匹配来源。
 *
 * 容器状态那部分是 `@/modules/database/container-display` 的**本地副本**，不是 import ——
 * 平台约定前端模块之间不互相依赖。这份重复是有意的，两边各自演化。
 */

import type { AgentContainerItem } from '@/modules/agent/api'

type TagType = 'primary' | 'success' | 'warning' | 'danger' | 'info'

/** 服务类型清单，顺序与后端一致。筛选项直接用它渲染。 */
export const SERVICE_TYPES = ['openclaw', 'hermes', 'codex', 'dify', 'langgraph', 'custom']

const SERVICE_LABELS: Record<string, string> = {
  openclaw: 'OpenClaw',
  hermes: 'Hermes',
  codex: 'Codex',
  dify: 'Dify',
  langgraph: 'LangGraph',
  custom: '自定义',
}

export function serviceTypeLabel(value: string): string {
  return SERVICE_LABELS[value] || value || '—'
}

export function serviceTypeTagType(value: string): TagType {
  switch (value) {
    case 'langgraph':
      return 'warning'
    case 'openclaw':
      return 'primary'
    case 'hermes':
      return 'success'
    case 'codex':
      return 'danger'
    case 'dify':
      return 'info'
    default:
      return 'info'
  }
}

/** 健康状态四态。后端只产出这四个（外加未检查过的 unknown）。 */
export const HEALTH_STATUSES = ['healthy', 'unhealthy', 'timeout', 'error', 'unknown']

const HEALTH_LABELS: Record<string, string> = {
  healthy: '正常',
  unhealthy: '异常',
  timeout: '超时',
  error: '不可达',
  unknown: '未检查',
}

export function healthLabel(status: string): string {
  return HEALTH_LABELS[status] || status || '未知'
}

export function healthTagType(status: string): TagType {
  switch (status) {
    case 'healthy':
      return 'success'
    case 'unhealthy':
      return 'danger'
    case 'timeout':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
}

// ===== 容器状态（database 模块 container-display 的本地副本）=====

export function stateLabel(state: string): string {
  switch (state) {
    case 'running':
      return '运行中'
    case 'exited':
      return '已停止'
    case 'created':
      return '已创建'
    case 'paused':
      return '已暂停'
    case 'restarting':
      return '重启中'
    case 'dead':
      return '异常退出'
    default:
      return state || '未知'
  }
}

export function stateTagType(state: string): TagType {
  switch (state) {
    case 'running':
      return 'success'
    case 'paused':
    case 'restarting':
      return 'warning'
    case 'dead':
      return 'danger'
    default:
      return 'info'
  }
}

export function matchedByLabel(matchedBy: string): string {
  switch (matchedBy) {
    case 'compose':
      return '按 compose 项目名匹配'
    case 'name':
      return '按容器名正则匹配'
    case 'conflict':
      return '多条规则同时命中'
    default:
      return '未匹配任何规则'
  }
}

/** 项目列的显示文案：冲突 / 未分类 / 项目名。 */
export function projectLabel(container: AgentContainerItem): string {
  if (container.conflict) return '规则冲突'
  return container.project_name || '未分类'
}

export function projectTagType(container: AgentContainerItem): TagType {
  if (container.conflict) return 'warning'
  return container.project_key ? 'success' : 'info'
}

/** 操作门禁：分类未落到唯一项目、或受保护 → 不给启停（权限由调用方叠加）。 */
export function isOperable(container: AgentContainerItem | null | undefined): boolean {
  if (!container) return false
  if (container.protected) return false
  if (container.conflict) return false
  if (!container.project_key) return false
  return true
}

export function canStart(container: AgentContainerItem): boolean {
  return container.state === 'exited' || container.state === 'created'
}

export function canStop(container: AgentContainerItem): boolean {
  return container.state === 'running' || container.state === 'paused'
}

export function actionLabel(action: string): string {
  return { start: '启动', stop: '停止', restart: '重启' }[action] || action
}

export function auditResultLabel(result: string): string {
  return { success: '成功', failed: '失败', refused: '已拒绝' }[result] || result
}

export function auditResultType(result: string): TagType {
  if (result === 'success') return 'success'
  if (result === 'refused') return 'warning'
  return 'danger'
}

export function checkTypeLabel(checkType: string): string {
  return { scheduled: '周期检查', manual: '手动检查', http: '检查' }[checkType] || checkType
}

/**
 * 统计卡片的契约。定义在这里而不是 StatCards.vue 里 ——
 * `<script setup>` 不允许出现 ES 模块导出，类型只能放外部模块。
 */
export interface StatCard {
  label: string
  value: number | string
  /** 可选的着色语义 */
  tone?: 'ok' | 'warn' | 'bad'
}
