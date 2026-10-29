/** 统一的接口错误文案：403 一律以「权限不足」开头，避免各页面提示不一致。 */
export function errorMessage(e: unknown, fallback: string): string {
  const resp = (e as { response?: { status?: number; data?: { detail?: unknown } } })?.response
  const detail = resp?.data?.detail

  if (resp?.status === 403) {
    if (typeof detail === 'string' && detail) {
      return detail.startsWith('权限不足') ? detail : `权限不足：${detail}`
    }
    return '权限不足：当前账号无权执行该操作'
  }

  return typeof detail === 'string' && detail ? detail : fallback
}
