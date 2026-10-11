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

export function fetchMarkTemplates() {
  return http.get<MarkTemplate[]>('/marks/templates')
}

export function createMarkTemplate(name: string, layoutJson = '{}') {
  return http.post<MarkTemplate>('/marks/templates', { name, layout_json: layoutJson })
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