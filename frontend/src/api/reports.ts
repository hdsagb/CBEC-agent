import { http } from '@/api/http'

export interface SupplierTrendPoint {
  month: string
  supplier_name: string
  currency: string
  avg_price: number
  min_price: number
  max_price: number
  item_count: number
}

export interface SupplierPriceTrend {
  months: string[]
  suppliers: string[]
  currencies: string[]
  points: SupplierTrendPoint[]
}

export interface CategorySlice {
  hs_chapter: string
  label: string
  element_count: number
  customer_count: number
  share: number
}

export interface CategoryDistribution {
  total_elements: number
  slices: CategorySlice[]
}

export interface SavingGroup {
  batch_id: number
  batch_name: string
  product_name: string
  spec: string
  currency: string
  best_supplier: string
  best_price: number | null
  max_price: number | null
  saving: number
  saving_rate: number
}

export interface CurrencySaving {
  currency: string
  total_savings: number
  group_count: number
}

export interface Savings {
  total_savings: number
  by_currency: CurrencySaving[]
  batch_count: number
  group_count: number
  groups: SavingGroup[]
}

export function fetchSupplierPriceTrend(months = 6) {
  return http.get<SupplierPriceTrend>('/reports/supplier-price-trend', { params: { months } })
}

export function fetchCategoryDistribution() {
  return http.get<CategoryDistribution>('/reports/category-distribution')
}

export function fetchSavings() {
  return http.get<Savings>('/reports/savings')
}