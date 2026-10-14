import { http } from '@/api/http'

export type PriceMatchBy = 'product' | 'hs_code' | 'none'
export type PriceVerdict = 'low' | 'normal' | 'high' | 'no_reference'

export interface PriceReferenceSample {
  quote_item_id: number
  supplier_name: string
  product_name: string
  spec: string
  unit_price: number | null
  currency: string
  batch_id: number
  batch_name: string
  quote_time: string
}

export interface CurrencyPriceReference {
  currency: string
  item_count: number
  avg_price: number
  min_price: number
  max_price: number
  last_price: number
  last_quote_at: string
}

/** 要素/HS 编码下的历史价格参考汇总 */
export interface PriceReference {
  hs_code: string
  product_name: string
  match_by: PriceMatchBy
  sample_count: number
  currency_stats: CurrencyPriceReference[]
  samples: PriceReferenceSample[]
}

/** 单条报价的合理性校验结果 */
export interface PriceCheckResult {
  verdict: PriceVerdict
  unit_price: number | null
  currency: string
  deviation_rate: number | null
  tolerance: number
  reference_avg: number | null
  reference_min: number | null
  reference_max: number | null
  sample_count: number
  match_by: PriceMatchBy
  hs_code: string
  message: string
}

export interface PriceCheckPayload {
  product_name?: string
  hs_code?: string
  unit_price?: number | null
  currency?: string
  tolerance?: number
  only_confirmed?: boolean
}

export interface BatchPriceCheckItem {
  item_id: number
  supplier_name: string
  product_name: string
  spec: string
  unit_price: number | null
  currency: string
  verdict: PriceVerdict
  deviation_rate: number | null
  reference_avg: number | null
  sample_count: number
  match_by: PriceMatchBy
  message: string
}

export interface BatchPriceCheckResult {
  batch_id: number
  tolerance: number
  total: number
  low: number
  normal: number
  high: number
  no_reference: number
  items: BatchPriceCheckItem[]
}

/** 按要素的 HS 编码/商品名关联历史成交价 */
export function fetchElementPriceReference(elementId: number, onlyConfirmed = true) {
  return http.get<PriceReference>(`/elements/${elementId}/price-reference`, {
    params: { only_confirmed: onlyConfirmed },
  })
}

/** 单条报价合理性校验 */
export function checkQuoteItemPrice(itemId: number, payload: PriceCheckPayload = {}) {
  return http.post<PriceCheckResult>(`/quotes/items/${itemId}/price-check`, payload)
}

/** 批次级价格校验：逐条判定 + 汇总 */
export function checkQuoteBatchPrices(batchId: number, payload: { tolerance?: number; only_confirmed?: boolean } = {}) {
  return http.post<BatchPriceCheckResult>(`/quotes/batches/${batchId}/price-check`, payload)
}