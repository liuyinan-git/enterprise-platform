/**
 * 复制文本到剪贴板。
 *
 * 前端跑在 `http://host:5170`（非安全上下文），`navigator.clipboard` 可能是
 * `undefined`，所以必须保留 `textarea + execCommand` 的回退路径。
 *
 * 平台通用设施（database 与 agent 两个模块都用），因此放在 core/util 下。
 */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 落到下面的回退路径
    }
  }
  try {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.top = '-1000px'
    document.body.appendChild(area)
    area.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(area)
    return copied
  } catch {
    return false
  }
}
