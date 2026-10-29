import { http } from '@/api/http'

export interface QuoteSource {
  id: number
  batch_id: number
  file_name: string
  file_type: string
  raw_file_url: string
  parse_status: string // pending | parsing | success | failed
  supplier_name: string
}

export interface QuoteBatch {
  id: number
  name: string
  uploader_id: number
  status: string // uploaded | parsing | parsed | confirmed | compared
  created_at: string
  sources: QuoteSource[]
}

export interface QuoteBatchPage {
  items: QuoteBatch[]
  total: number
  page: number
  page_size: number
}

export interface QuoteItem {
  id: number
  source_id: number
  product_name: string
  spec: string
  unit_price: number | null
  currency: string
  moq: number | null
  lead_time_days: number | null
  valid_until: string
  remarks: string
  confidence: number
  confirmed: boolean
}

export interface QuoteItemPayload {
  product_name: string
  spec: string
  unit_price: number | null
  currency: string
  moq: number | null
  lead_time_days: number | null
  valid_until: string
  remarks: string
}

export interface CompareCandidate {
  item_id: number
  source_id: number
  supplier_name: string
  product_name: string
  spec: string
  unit_price: number | null
  currency: string
  moq: number | null
  lead_time_days: number | null
  confidence: number
  scores: Record<string, number>
  total_score: number
  is_best: boolean
}

export interface CompareGroup {
  product_key: string
  product_name: string
  spec: string
  best_supplier: string
  best_item_id: number
  candidates: CompareCandidate[]
}

export interface CompareResult {
  batch_id: number
  weights: Record<string, number>
  recommended_source_id: number | null
  recommended_supplier: string
  result: CompareGroup[]
}

export function createQuoteBatch(name: string) {
  return http.post<QuoteBatch>('/quotes/batches', undefined, { params: { name } })
}

export function fetchQuoteBatches(params: { page?: number; page_size?: number } = {}) {
  return http.get<QuoteBatchPage>('/quotes/batches', { params })
}

export function fetchQuoteBatch(id: number) {
  return http.get<QuoteBatch>(`/quotes/batches/${id}`)
}

export function uploadQuoteSource(batchId: number, file: File, supplierName = '') {
  const data = new FormData()
  data.append('file', file)
  return http.post<QuoteBatch>(`/quotes/batches/${batchId}/sources`, data, {
    params: { supplier_name: supplierName || undefined },
  })
}

export function parseQuoteSource(sourceId: number) {
  return http.post<QuoteItem[]>(`/quotes/sources/${sourceId}/parse`)
}

export function parseQuoteBatch(batchId: number) {
  return http.post<QuoteItem[]>(`/quotes/batches/${batchId}/parse`)
}

export function fetchQuoteItems(batchId: number) {
  return http.get<QuoteItem[]>(`/quotes/batches/${batchId}/items`)
}

export function confirmQuoteItem(itemId: number, payload: QuoteItemPayload) {
  return http.put<QuoteItem>(`/quotes/items/${itemId}/confirm`, payload)
}

export function compareQuoteBatch(batchId: number, weightConfig: Record<string, number>) {
  return http.post<CompareResult>(`/quotes/batches/${batchId}/compare`, { weight_config: weightConfig })
}