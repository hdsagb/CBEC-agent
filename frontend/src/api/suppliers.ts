import { http } from '@/api/http'

export type SupplierStatus = 'active' | 'paused' | 'blacklisted'

export interface SupplierItem {
  id: number
  name: string
  region: string
  main_category: string
  contact_name: string
  contact_phone: string
  contact_email: string
  rating: number
  status: SupplierStatus
  remarks: string
  created_by: number
  created_at: string
  updated_at: string
}

export interface SupplierPage {
  items: SupplierItem[]
  total: number
  page: number
  page_size: number
}

/** 新建/编辑提交的字段集合 */
export interface SupplierPayload {
  name: string
  region: string
  main_category: string
  contact_name: string
  contact_phone: string
  contact_email: string
  rating: number
  status: SupplierStatus
  remarks: string
}

export interface SupplierQuery {
  keyword?: string
  status?: string
  page?: number
  page_size?: number
}

export interface CurrencyPriceStat {
  currency: string
  item_count: number
  avg_price: number
  min_price: number
  max_price: number
}

/** 按供应商名称聚合的历史报价概览 */
export interface SupplierQuoteStat {
  supplier_name: string
  item_count: number
  priced_count: number
  batch_count: number
  product_count: number
  currencies: string[]
  last_quote_at: string | null
  price_stats: CurrencyPriceStat[]
  supplier_id: number | null
  status: string
  rating: number
  region: string
}

export interface SupplierQuoteStatPage {
  items: SupplierQuoteStat[]
  total: number
  page: number
  page_size: number
}

export interface SupplierQuoteRow {
  id: number
  supplier_name: string
  batch_id: number
  batch_name: string
  product_name: string
  spec: string
  unit_price: number | null
  currency: string
  moq: number | null
  lead_time_days: number | null
  confirmed: boolean
  quote_time: string
}

export interface SupplierQuotePage {
  items: SupplierQuoteRow[]
  total: number
  page: number
  page_size: number
}

export interface QuoteSearchQuery {
  keyword?: string
  supplier_name?: string
  currency?: string
  page?: number
  page_size?: number
}

export function fetchSuppliers(params: SupplierQuery) {
  return http.get<SupplierPage>('/suppliers', { params })
}

export function createSupplier(payload: SupplierPayload) {
  return http.post<SupplierItem>('/suppliers', payload)
}

export function updateSupplier(id: number, payload: Partial<SupplierPayload>) {
  return http.put<SupplierItem>(`/suppliers/${id}`, payload)
}

export function deleteSupplier(id: number) {
  return http.delete<{ ok: boolean }>(`/suppliers/${id}`)
}

/** 历史报价库概览：按供应商聚合报价次数、覆盖品类、最近报价时间 */
export function fetchQuoteStats(params: { keyword?: string; page?: number; page_size?: number }) {
  return http.get<SupplierQuoteStatPage>('/suppliers/quote-stats', { params })
}

/** 全局历史报价检索 */
export function fetchQuotes(params: QuoteSearchQuery) {
  return http.get<SupplierQuotePage>('/suppliers/quotes', { params })
}

/** 某供应商档案下的历史报价明细 */
export function fetchSupplierQuotes(
  id: number,
  params: { keyword?: string; currency?: string; page?: number; page_size?: number },
) {
  return http.get<SupplierQuotePage>(`/suppliers/${id}/quotes`, { params })
}

/** 历史报价中出现过的币种 */
export function fetchQuoteCurrencies() {
  return http.get<string[]>('/suppliers/currencies')
}