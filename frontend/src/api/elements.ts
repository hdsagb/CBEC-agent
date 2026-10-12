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

/** 导出/模板共用的筛选条件（不含分页） */
export interface ElementExportQuery {
  keyword?: string
  hs_code?: string
  customer_name?: string
}

/** Excel 导入结果汇总 */
export interface ElementImportResult {
  total: number
  created: number
  skipped: number
  invalid: number
  errors: string[]
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

/** 按当前筛选条件导出全部匹配记录（xlsx 二进制） */
export function exportElements(params: ElementExportQuery) {
  return http.get<Blob>('/elements/export', { params, responseType: 'blob' })
}

/** 下载空白导入模板（仅表头） */
export function downloadElementTemplate() {
  return http.get<Blob>('/elements/template', { responseType: 'blob' })
}

/** 批量导入要素（xlsx） */
export function importElements(file: File) {
  const data = new FormData()
  data.append('file', file)
  return http.post<ElementImportResult>('/elements/import', data)
}