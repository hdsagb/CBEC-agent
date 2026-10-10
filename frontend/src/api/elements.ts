import { http } from '@/api/http'

export interface ElementItem {
  id: number
  version: number
  hs_code: string
  product_name: string
  name_en: string
  customer_name: string
  brand: string
  model: string
  spec: string
  material: string
  usage: string
  elements_json: string
  source_file_url: string
  created_by: number
  updated_by: number
  created_at: string
  updated_at: string
}

export interface ElementPage {
  items: ElementItem[]
  total: number
  page: number
  page_size: number
}

/** 新建/编辑提交的字段集合 */
export interface ElementPayload {
  hs_code: string
  product_name: string
  name_en: string
  customer_name: string
  brand: string
  model: string
  spec: string
  material: string
  usage: string
  elements_json: string
  source_file_url: string
}

export interface ElementQuery {
  keyword?: string
  hs_code?: string
  customer_name?: string
  page?: number
  page_size?: number
}

export function fetchElements(params: ElementQuery) {
  return http.get<ElementPage>('/elements', { params })
}

export function fetchElement(id: number) {
  return http.get<ElementItem>(`/elements/${id}`)
}

export function createElement(payload: ElementPayload) {
  return http.post<ElementItem>('/elements', payload)
}

export function updateElement(id: number, payload: Partial<ElementPayload>) {
  return http.put<ElementItem>(`/elements/${id}`, payload)
}

export function deleteElement(id: number) {
  return http.delete<{ ok: boolean }>(`/elements/${id}`)
}

/** 复制复用：以旧记录为底稿新建一条记录 */
export function copyElement(id: number) {
  return http.post<ElementItem>(`/elements/${id}/copy`)
}

/** 一键复制：获取报关格式文本 */
export function fetchDeclarationText(id: number) {
  return http.get<{ text: string }>(`/elements/${id}/declaration-text`)
}