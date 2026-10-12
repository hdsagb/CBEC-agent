import { http } from '@/api/http'

export interface MarkTemplate {
  id: number
  name: string
  layout_json: string
  thumbnail_url: string
}

export interface MarkJob {
  id: number
  template_id: number
  order_no: string
  total_boxes: number
  start_no: number
  fields_json: string
}

export interface MarkJobPayload {
  template_id: number
  order_no: string
  total_boxes: number
  start_no: number
  fields_json: string
}

export interface MarkExportResult {
  job_id: number
  format: string
  url: string
  message: string
}

export type MarkBlockKind = 'text' | 'image' | 'qrcode' | 'barcode'

/** 画布元素：绝对定位，按 kind 区分文字 / Logo 图片 / 二维码 / 条形码。 */
export interface MarkBlock {
  kind: MarkBlockKind
  text?: string
  src?: string
  x_mm?: number
  y_mm?: number
  w_mm?: number
  h_mm?: number
  /** 文字字号（pt） */
  size?: number
  /** 二维码边长（mm） */
  size_mm?: number
  align?: 'left' | 'center' | 'right'
  bold?: boolean
}

export interface MarkRow {
  label?: string
  value?: string
}

export type MarkRowItem = string | MarkRow

/** 模板版式：行式（title/rows/footer）+ 画布式（尺寸 + 绝对定位 blocks） */
export interface MarkLayout {
  width_mm: number
  height_mm: number
  dpi?: number
  margin_mm?: number
  border?: boolean
  title?: string
  title_size?: number
  row_size?: number
  footer?: string
  footer_size?: number
  separator?: string
  rows?: MarkRowItem[]
  blocks?: MarkBlock[]
}

export interface MarkAsset {
  id: number
  type: string
  file_url: string
  created_at: string
}

export interface MarkPreviewResult {
  url: string
  width_px: number
  height_px: number
  message: string
}

export interface MarkPreviewPayload {
  layout_json: string
  fields_json: string
  order_no: string
  total_boxes: number
  start_no: number
  box_no: number
}

export function fetchMarkTemplates() {
  return http.get<MarkTemplate[]>('/marks/templates')
}

export function createMarkTemplate(name: string, layoutJson = '{}') {
  return http.post<MarkTemplate>('/marks/templates', { name, layout_json: layoutJson })
}

export function updateMarkTemplate(id: number, payload: { name?: string; layout_json?: string }) {
  return http.put<MarkTemplate>(`/marks/templates/${id}`, payload)
}

export function fetchMarkJobs() {
  return http.get<MarkJob[]>('/marks/jobs')
}

export function createMarkJob(payload: MarkJobPayload) {
  return http.post<MarkJob>('/marks/jobs', payload)
}

export function exportMarkJob(jobId: number, format: 'pdf' | 'png') {
  return http.post<MarkExportResult>(`/marks/jobs/${jobId}/export`, { job_id: jobId, format })
}

export function fetchMarkAssets() {
  return http.get<MarkAsset[]>('/marks/assets')
}

export function uploadMarkAsset(file: File, type: MarkBlockKind | 'logo' = 'logo') {
  const form = new FormData()
  form.append('file', file)
  form.append('type', type)
  return http.post<MarkAsset>('/marks/assets', form)
}

export function deleteMarkAsset(id: number) {
  return http.delete<{ deleted: number }>(`/marks/assets/${id}`)
}

export function previewMarkLayout(payload: MarkPreviewPayload) {
  return http.post<MarkPreviewResult>('/marks/preview', payload)
}