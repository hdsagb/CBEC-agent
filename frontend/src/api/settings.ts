import { http } from '@/api/http'

/** 全局大模型配置视图（后端只返回掩码，不含明文 Key） */
export interface LLMConfig {
  provider: string
  base_url: string
  model: string
  api_key_masked: string
  api_key_configured: boolean
  vision_model: string
  vision_base_url: string
  vision_api_key_masked: string
  vision_api_key_configured: boolean
  /** db=页面保存的配置；env=环境变量兜底 */
  source: 'db' | 'env'
  status: string
  status_message: string
  checked_at: string | null
  updated_at: string | null
  updated_by: number
  can_edit: boolean
}

export interface LLMConfigPayload {
  provider: string
  base_url: string
  model: string
  /** 不传表示保持原 Key，传空字符串表示清除 */
  api_key?: string | null
  vision_model?: string
  vision_base_url?: string
  vision_api_key?: string | null
}

export interface LLMProbeResult {
  status: string
  message: string
  latency_ms: number
  checked_at: string
  config: LLMConfig
}

export const fetchLLMConfig = () => http.get<LLMConfig>('/settings/llm')

export const saveLLMConfig = (payload: LLMConfigPayload) =>
  http.put<LLMConfig>('/settings/llm', payload)

export const testLLMConfig = () => http.post<LLMProbeResult>('/settings/llm/test')

/** 任意登录用户可调用：后台探测一次并刷新状态灯 */
export const refreshLLMStatus = () => http.post<LLMProbeResult>('/settings/llm/refresh')

/** 探测状态中文文案，页面芯片 / 弹窗 / 管理页共用 */
export const LLM_STATUS_LABEL: Record<string, string> = {
  ok: '连接正常',
  unconfigured: '未配置模型',
  unknown: '尚未检测',
  auth_failed: 'API Key 无效',
  rate_limited: '服务限流',
  not_found: '接口或模型不存在',
  timeout: '连接超时',
  unreachable: '无法连接',
  server_error: '模型服务异常',
  bad_request: '测试请求被拒绝',
  bad_response: '响应异常',
}

export function llmStatusLabel(status: string | null | undefined): string {
  return LLM_STATUS_LABEL[status ?? ''] ?? '尚未检测'
}
