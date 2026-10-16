/**
 * 已提升到 `@/core/util/clipboard`（database 与 agent 两个模块共用）。
 *
 * 这里保留一行 re-export，让既有引用路径继续可用，行为不变。
 */
export { copyText } from '@/core/util/clipboard'
