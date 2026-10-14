<template>
  <div class="page">
    <div class="page-inner">
      <div class="page-head">
        <div>
          <h1>数据分析报表</h1>
          <p>沉淀报价与申报数据，观察供应商价格走势、报关品类分布与比价节省成效。</p>
        </div>
        <div class="actions">
          <div class="field">
            <label>统计区间</label>
            <select v-model.number="months">
              <option :value="3">最近 3 个月</option>
              <option :value="6">最近 6 个月</option>
              <option :value="12">最近 12 个月</option>
            </select>
          </div>
          <button class="btn" type="button" :disabled="loading" @click="load">刷新</button>
        </div>
      </div>

      <div class="grid-kpi">
        <div class="kpi">
          <div class="lbl">累计节省金额</div>
          <div class="val">{{ savings ? fmtNum(savings.total_savings) : '—' }}</div>
          <div class="delta mut">
            <template v-if="savings && savings.by_currency.length">
              {{ savings.by_currency.map((c) => `${c.currency} ${fmtNum(c.total_savings)}`).join(' · ') }}
            </template>
            <template v-else>原币种直接加总，未做汇率折算</template>
          </div>
        </div>
        <div class="kpi">
          <div class="lbl">参与比价批次</div>
          <div class="val">{{ savings ? fmtNum(savings.batch_count) : '—' }}</div>
          <div class="delta mut">已产生比价结果的批次</div>
        </div>
        <div class="kpi">
          <div class="lbl">覆盖 HS 品类</div>
          <div class="val">{{ category ? fmtNum(category.slices.length) : '—' }}</div>
          <div class="delta mut">按 HS 编码前两位章节归集</div>
        </div>
        <div class="kpi">
          <div class="lbl">报价供应商</div>
          <div class="val">{{ trend ? fmtNum(trend.suppliers.length) : '—' }}</div>
          <div class="delta mut">区间内提供有效报价的供应商</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>供应商价格走势</b>
          <div class="hd-tools">
            <select v-if="trend && trend.currencies.length" v-model="trendCurrency" class="mini">
              <option v-for="c in trend.currencies" :key="c" :value="c">{{ c }}</option>
            </select>
            <span class="hint">各供应商月度平均报价单价</span>
          </div>
        </div>
        <div class="panel-bd">
          <div v-if="chart" class="chart-wrap">
            <svg :viewBox="`0 0 ${chart.width} ${chart.height}`" class="chart" role="img" aria-label="供应商价格走势">
              <line
                v-for="t in chart.yTicks"
                :key="`y-${t.y}`"
                :x1="chart.padL"
                :x2="chart.width - chart.padR"
                :y1="t.y"
                :y2="t.y"
                class="grid"
              />
              <text v-for="t in chart.yTicks" :key="`yl-${t.y}`" :x="chart.padL - 8" :y="t.y + 4" class="axis-y">
                {{ t.label }}
              </text>
              <text
                v-for="t in chart.xTicks"
                :key="`xl-${t.x}`"
                :x="t.x"
                :y="chart.height - chart.padB + 18"
                class="axis-x"
              >
                {{ t.label }}
              </text>
              <path v-for="s in chart.series" :key="`p-${s.name}`" :d="s.path" class="line" :stroke="s.color" />
              <g v-for="s in chart.series" :key="`d-${s.name}`">
                <circle v-for="d in s.dots" :key="`${s.name}-${d.month}`" :cx="d.cx" :cy="d.cy" r="3.4" :fill="s.color">
                  <title>{{ s.name }} · {{ d.month }} · {{ d.price }}</title>
                </circle>
              </g>
            </svg>
            <div class="legend">
              <span v-for="s in chart.series" :key="`l-${s.name}`">
                <i :style="{ background: s.color }"></i>{{ s.name }}
              </span>
            </div>
          </div>
          <div v-else class="empty">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <span>暂无报价数据</span>
            <span>在「智能比价」完成解析与确认后，这里会按月份展示各供应商的价格走势。</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>报关品类分布</b>
          <span class="hint">共 {{ category?.total_elements ?? 0 }} 条申报要素</span>
        </div>
        <div class="panel-bd">
          <div v-if="category && category.slices.length" class="cat-list">
            <div v-for="s in category.slices" :key="s.hs_chapter" class="cat-row">
              <div class="cat-name">
                <code class="hsc">{{ s.hs_chapter }}</code>
                <b>{{ s.label }}</b>
              </div>
              <div class="cat-bar">
                <i :style="{ width: barWidth(s) }"></i>
              </div>
              <div class="cat-num">
                <b>{{ s.element_count }}</b>
                <span>{{ (s.share * 100).toFixed(1) }}% · {{ s.customer_count }} 家客户</span>
              </div>
            </div>
          </div>
          <div v-else class="empty">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M5 4h11l3 3v13H5V4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              <path d="M8 9h7M8 13h7M8 17h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <span>暂无申报要素数据</span>
            <span>在「申报要素库」录入或批量导入后，即可按 HS 章节查看品类分布。</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>比价节省金额明细</b>
          <span class="hint">同币种内「最高报价 − 最优报价」，按批次最新一次比价结果</span>
        </div>
        <div class="panel-bd no-pad">
          <table v-if="savings && savings.groups.length">
            <thead>
              <tr>
                <th>批次</th>
                <th>商品</th>
                <th>规格</th>
                <th>最优供应商</th>
                <th class="num">最优价</th>
                <th class="num">最高价</th>
                <th class="num">节省</th>
                <th class="num">节省率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(g, idx) in savings.groups" :key="`${g.batch_id}-${idx}`">
                <td>{{ g.batch_name }}</td>
                <td>{{ g.product_name || '—' }}</td>
                <td>{{ g.spec || '—' }}</td>
                <td>{{ g.best_supplier || '—' }}</td>
                <td class="num">{{ money(g.best_price, g.currency) }}</td>
                <td class="num muted">{{ money(g.max_price, g.currency) }}</td>
                <td class="num"><span class="pill best">省 {{ money(g.saving, g.currency) }}</span></td>
                <td class="num">{{ (g.saving_rate * 100).toFixed(1) }}%</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <span>暂无节省记录</span>
            <span>同一商品有两家及以上有效报价并完成比价后，才会产生节省金额。</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'

import {
  fetchCategoryDistribution,
  fetchSavings,
  fetchSupplierPriceTrend,
  type CategoryDistribution,
  type Savings,
  type SupplierPriceTrend,
} from '@/api/reports'

const PALETTE = ['#0d9488', '#7c6cf0', '#f59e0b', '#2563eb', '#db2777', '#16a34a', '#dc2626', '#0891b2']

const loading = ref(false)
const months = ref(6)
const trend = ref<SupplierPriceTrend | null>(null)
const category = ref<CategoryDistribution | null>(null)
const savings = ref<Savings | null>(null)
const trendCurrency = ref('')

interface Dot {
  cx: number
  cy: number
  price: number
  month: string
}

interface Series {
  name: string
  color: string
  path: string
  dots: Dot[]
}

interface TrendChart {
  width: number
  height: number
  padL: number
  padR: number
  padT: number
  padB: number
  yTicks: { y: number; label: string }[]
  xTicks: { x: number; label: string }[]
  series: Series[]
}

const chart = computed<TrendChart | null>(() => {
  const data = trend.value
  if (!data) return null
  const points = data.points.filter((p) => p.currency === trendCurrency.value)
  if (!points.length) return null

  const monthList = [...new Set(points.map((p) => p.month))].sort()
  const values = points.map((p) => p.avg_price)
  let lo = Math.min(...values)
  let hi = Math.max(...values)
  if (hi === lo) {
    const pad = hi === 0 ? 1 : Math.abs(hi) * 0.2
    lo -= pad
    hi += pad
  }

  const width = 780
  const height = 280
  const padL = 56
  const padR = 20
  const padT = 18
  const padB = 34
  const innerW = width - padL - padR
  const innerH = height - padT - padB

  const xAt = (index: number) =>
    monthList.length === 1 ? padL + innerW / 2 : padL + (index / (monthList.length - 1)) * innerW
  const yAt = (value: number) => padT + ((hi - value) / (hi - lo)) * innerH

  const yTicks = Array.from({ length: 5 }, (_, i) => {
    const value = hi - ((hi - lo) * i) / 4
    return { y: yAt(value), label: value.toFixed(2) }
  })
  const xTicks = monthList.map((month, i) => ({ x: xAt(i), label: month.slice(2) }))

  const suppliers = [...new Set(points.map((p) => p.supplier_name))].sort()
  const series: Series[] = suppliers.map((name, si) => {
    const dots: Dot[] = []
    monthList.forEach((month, i) => {
      const hit = points.find((p) => p.supplier_name === name && p.month === month)
      if (hit) dots.push({ cx: xAt(i), cy: yAt(hit.avg_price), price: hit.avg_price, month })
    })
    return {
      name,
      color: PALETTE[si % PALETTE.length],
      dots,
      path: dots.map((d, i) => `${i === 0 ? 'M' : 'L'}${d.cx.toFixed(1)} ${d.cy.toFixed(1)}`).join(' '),
    }
  })

  return { width, height, padL, padR, padT, padB, yTicks, xTicks, series }
})

function fmtNum(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function money(value: number | null, currency: string): string {
  if (value === null || value === undefined) return '—'
  return `${fmtNum(value)} ${currency}`
}

function barWidth(slice: { element_count: number }): string {
  const max = Math.max(...(category.value?.slices ?? []).map((s) => s.element_count), 1)
  return `${Math.max(6, Math.round((slice.element_count / max) * 100))}%`
}

async function load() {
  loading.value = true
  const [t, c, s] = await Promise.allSettled([
    fetchSupplierPriceTrend(months.value),
    fetchCategoryDistribution(),
    fetchSavings(),
  ])

  if (t.status === 'fulfilled') {
    trend.value = t.value
    if (!t.value.currencies.includes(trendCurrency.value)) {
      trendCurrency.value = t.value.currencies[0] ?? ''
    }
  } else {
    ElMessage.error('加载价格走势失败')
  }
  category.value = c.status === 'fulfilled' ? c.value : null
  savings.value = s.status === 'fulfilled' ? s.value : null
  if (c.status === 'rejected' || s.status === 'rejected') {
    ElMessage.error('部分报表数据加载失败')
  }
  loading.value = false
}

watch(months, load)
onMounted(load)
</script>

<style scoped>
.actions {
  align-items: center;
}

.hd-tools {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.mini {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text);
  background: var(--surface);
}

.panel-bd.no-pad {
  padding: 0;
}

.chart-wrap {
  width: 100%;
}

.chart {
  width: 100%;
  height: auto;
  display: block;
}

.grid {
  stroke: var(--border);
  stroke-width: 1;
}

.axis-y,
.axis-x {
  fill: var(--muted);
  font-size: 10.5px;
  font-family: var(--mono);
}

.axis-x {
  text-anchor: middle;
}

.line {
  fill: none;
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--text-2);
}

.legend i {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 2px;
  margin-right: 6px;
}

.cat-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cat-row {
  display: grid;
  grid-template-columns: 220px 1fr 130px;
  align-items: center;
  gap: 12px;
}

.cat-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.cat-name b {
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cat-bar {
  height: 9px;
  border-radius: var(--radius-pill);
  background: #eef1f5;
  overflow: hidden;
}

.cat-bar i {
  display: block;
  height: 100%;
  border-radius: var(--radius-pill);
  background: linear-gradient(90deg, var(--brand-500), var(--brand-400));
}

.cat-num {
  text-align: right;
  line-height: 1.25;
}

.cat-num b {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.cat-num span {
  display: block;
  font-size: 11px;
  color: var(--muted);
}

@media (max-width: 900px) {
  .cat-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .cat-num {
    text-align: left;
  }
}
</style>