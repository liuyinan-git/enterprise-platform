/** 容器实况的展示规则：台账表与「未登记容器」表共用，避免两处各写一份。 */

import type { ContainerItem } from '@/modules/database/api'

type TagType = 'primary' | 'success' | 'warning' | 'danger' | 'info'

/**
 * 受管类型清单，顺序与后端 `containers.MANAGED_TYPES` 一致。
 * 后端加了新类型，这里同步加一项即可（筛选下拉直接用它渲染）。
 */
export const MANAGED_TYPES = [
  // 关系型
  'postgres', 'mysql', 'mariadb', 'oracle', 'sqlserver',
  // 缓存 / 文档 / 图 / 宽列
  'redis', 'memcached', 'mongodb', 'cassandra', 'neo4j',
  // 搜索 / 分析 / 时序
  'elasticsearch', 'clickhouse', 'influxdb',
  // 向量库
  'milvus', 'qdrant', 'weaviate', 'chroma',
  // 知识库
  'weknora', 'cognee',
]

/**
 * 「未登记容器」筛选下拉的两个哨兵值——其余取值就是受管类型名本身。
 * 用一个字符串而不是两个变量，是为了直接绑到一个 el-select 上。
 */
export const UNREGISTERED_MANAGED = '__managed__'
export const UNREGISTERED_ALL = '__all__'

// 分类着色：只有 5 种 tag 颜色，所以按大类分，具体是什么看标签文字。
const RELATIONAL = new Set(['postgres', 'mysql', 'mariadb', 'oracle', 'sqlserver'])
const CACHE = new Set(['redis', 'memcached'])
const ANALYTICS = new Set(['elasticsearch', 'clickhouse', 'influxdb'])
const DOCUMENT = new Set(['mongodb', 'cassandra', 'neo4j'])

export function typeLabel(managedType: string): string {
  return managedType === 'unknown' ? '未分类' : managedType
}

export function typeTagType(managedType: string): TagType {
  if (RELATIONAL.has(managedType)) return 'primary'
  if (CACHE.has(managedType)) return 'danger'
  if (ANALYTICS.has(managedType)) return 'warning'
  if (DOCUMENT.has(managedType)) return 'success'
  if (managedType === 'weknora') return 'success'
  if (managedType === 'cognee') return 'warning'
  return 'info' // 向量库、未分类
}

export function typeSourceLabel(source: string): string {
  switch (source) {
    case 'label':
      return '来自 platform.type 标签'
    case 'image':
      return '按镜像名推断'
    case 'name':
      return '按容器名推断'
    case 'app':
      // 镜像名/容器名认出了某个品牌，但这一层是应用（后端/前端/UI）而非数据存储
      return '应用层容器，不是数据存储'
    default:
      return '未能识别'
  }
}

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

/** 类型 / 保护状态层面的门禁（不含角色，角色由调用方叠加）。 */
export function isOperable(container: ContainerItem | null | undefined): boolean {
  if (!container) return false
  return container.managed_type !== 'unknown' && !container.protected
}

export function canStart(container: ContainerItem): boolean {
  return container.state === 'exited' || container.state === 'created'
}

export function canStop(container: ContainerItem): boolean {
  return container.state === 'running' || container.state === 'paused'
}
