<template>
  <div class="page">
    <div class="page-inner">
      <div class="page-head">
        <div>
          <h1>智能比价</h1>
          <p>上传报价单 → AI 解析 → 人工确认 → 四维加权比价看板。</p>
        </div>
      </div>

      <div class="quotes-page">
        <!-- 批次选择 -->
        <el-card shadow="never" class="block">
      <div class="batch-bar">
        <div class="batch-select">
          <span class="label">比价批次</span>
          <el-select
            v-model="currentBatchId"
            placeholder="选择或新建批次"
            style="width: 280px"
            @change="handleBatchChange"
          >
            <el-option v-for="b in batches" :key="b.id" :label="`${b.name}（${b.sources.length} 份报价）`" :value="b.id" />
          </el-select>
          <el-button type="primary" plain @click="batchDialogVisible = true">新建批次</el-button>
          <el-tag v-if="currentBatch" :type="statusTagType(currentBatch.status)" effect="light">
            {{ statusText(currentBatch.status) }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <template v-if="currentBatchId">
      <!-- 上传报价文件 -->
      <el-card shadow="never" class="block">
        <template #header><span class="card-title">1. 上传报价文件</span></template>
        <el-upload
          drag
          multiple
          :auto-upload="false"
          :file-list="fileList"
          :accept="ACCEPT"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
        >
          <div class="el-upload__text">拖拽报价文件到此处，或<em>点击选择</em></div>
          <template #tip>
            <div class="el-upload__tip">支持 Excel / Word / PDF / 图片（png、jpg），一家供应商一份文件（文件名默认作为供应商名）</div>
          </template>
        </el-upload>
        <div class="upload-actions">
          <el-button type="primary" :loading="uploading" :disabled="!fileList.length" @click="handleUploadAll">
            上传全部
          </el-button>
        </div>

        <el-table v-if="currentBatch?.sources.length" :data="currentBatch.sources" size="small" border class="source-table">
          <el-table-column prop="supplier_name" label="供应商" min-width="160" show-overflow-tooltip />
          <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="file_type" label="格式" width="80" align="center" />
          <el-table-column label="解析状态" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="parseTagType(row.parse_status)" size="small" effect="light">
                {{ parseText(row.parse_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button link type="primary" :loading="parsingId === row.id" @click="handleParseOne(row.id)">
                解析
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 解析确认 -->
      <el-card shadow="never" class="block">
        <template #header>
          <div class="card-header">
            <span class="card-title">2. 解析确认</span>
            <div>
              <el-button type="primary" plain :loading="parsing" @click="handleParseAll">一键解析</el-button>
              <el-button
                type="success"
                plain
                :loading="confirming"
                :disabled="!unconfirmedCount"
                @click="handleConfirmAll"
              >
                全部确认（{{ items.length - unconfirmedCount }}/{{ items.length }}）
              </el-button>
            </div>
          </div>
        </template>

        <el-table v-loading="itemsLoading" :data="items" border size="small" empty-text="暂无明细，请先上传并解析报价文件">
          <el-table-column label="供应商" width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ sourceName(row.source_id) }}</template>
          </el-table-column>
          <el-table-column label="产品名称" min-width="160">
            <template #default="{ row }"><el-input v-model="row.product_name" size="small" /></template>
          </el-table-column>
          <el-table-column label="规格" min-width="140">
            <template #default="{ row }"><el-input v-model="row.spec" size="small" /></template>
          </el-table-column>
          <el-table-column label="单价" width="130">
            <template #default="{ row }">
              <el-input-number v-model="row.unit_price" size="small" :min="0" :controls="false" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="币种" width="90">
            <template #default="{ row }">
              <el-select v-model="row.currency" size="small">
                <el-option v-for="c in CURRENCIES" :key="c" :label="c" :value="c" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="MOQ" width="110">
            <template #default="{ row }">
              <el-input-number v-model="row.moq" size="small" :min="0" :controls="false" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="货期(天)" width="110">
            <template #default="{ row }">
              <el-input-number v-model="row.lead_time_days" size="small" :min="0" :controls="false" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="confidenceTagType(row.confidence)" size="small" effect="light">
                {{ Math.round(row.confidence * 100) }}%
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.confirmed" type="success" size="small" effect="light">已确认</el-tag>
              <el-tag v-else type="info" size="small" effect="light">待确认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="handleCheckRow(row)">校验</el-button>
              <el-button v-if="!row.confirmed" link type="primary" @click="handleConfirmOne(row)">确认</el-button>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 权重与比价 -->
      <el-card shadow="never" class="block">
        <template #header>
          <div class="card-header">
            <span class="card-title">3. 权重配置与比价</span>
            <div>
              <el-button
                type="warning"
                plain
                :disabled="!items.length"
                @click="handleCheckBatch"
              >
                批次价格校验
              </el-button>
              <el-button
                type="primary"
                :loading="comparing"
                :disabled="!confirmedCount"
                @click="handleCompare"
              >
                开始比价
              </el-button>
            </div>
          </div>
        </template>

        <div class="weights">
          <div v-for="dim in DIMENSIONS" :key="dim.key" class="weight-item">
            <div class="weight-label">
              <span>{{ dim.label }}</span>
              <span class="weight-value">{{ weights[dim.key].toFixed(2) }}</span>
            </div>
            <el-slider v-model="weights[dim.key]" :min="0" :max="1" :step="0.05" />
          </div>
        </div>
        <div v-if="!confirmedCount" class="muted">请先确认至少一条报价明细后再比价。</div>
      </el-card>

      <!-- 比价看板 -->
      <el-card v-if="compareResult" shadow="never" class="block">
        <template #header>
          <div class="card-header">
            <span class="card-title">4. 比价看板</span>
            <el-tag v-if="compareResult.recommended_supplier" type="success" effect="dark">
              推荐供应商：{{ compareResult.recommended_supplier }}
            </el-tag>
          </div>
        </template>

        <el-empty v-if="!compareResult.result.length" description="暂无可比价数据（请确认明细后重试）" />

        <div v-for="group in compareResult.result" :key="group.product_key" class="group">
          <div class="group-title">
            <span class="product">{{ group.product_name || '未命名商品' }}</span>
            <span v-if="group.spec" class="spec">{{ group.spec }}</span>
            <el-tag size="small" type="success" effect="plain">最优：{{ group.best_supplier }}</el-tag>
          </div>
          <el-table :data="group.candidates" border size="small" :row-class-name="rowClassName">
            <el-table-column prop="supplier_name" label="供应商" min-width="140" show-overflow-tooltip />
            <el-table-column label="单价" width="110" align="right">
              <template #default="{ row }">
                {{ row.unit_price === null ? '-' : `${row.currency} ${row.unit_price}` }}
              </template>
            </el-table-column>
            <el-table-column label="MOQ" width="90" align="right">
              <template #default="{ row }">{{ row.moq ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="货期(天)" width="90" align="right">
              <template #default="{ row }">{{ row.lead_time_days ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="置信度" width="90" align="right">
              <template #default="{ row }">{{ Math.round(row.confidence * 100) }}%</template>
            </el-table-column>
            <el-table-column label="价格分" width="80" align="right">
              <template #default="{ row }">{{ row.scores.price.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="MOQ分" width="80" align="right">
              <template #default="{ row }">{{ row.scores.moq.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="货期分" width="80" align="right">
              <template #default="{ row }">{{ row.scores.lead_time.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="置信分" width="80" align="right">
              <template #default="{ row }">{{ row.scores.confidence.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="总分" width="90" align="right">
              <template #default="{ row }">
                <strong>{{ row.total_score.toFixed(2) }}</strong>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>
    </template>

    <el-empty v-else description="请先选择或新建一个比价批次" />

    <!-- 新建批次 -->
    <el-dialog v-model="batchDialogVisible" title="新建比价批次" width="420px">
      <el-form @submit.prevent>
        <el-form-item label="批次名称">
          <el-input v-model="newBatchName" placeholder="如 Q3 蓝牙耳机采购比价" @keyup.enter="handleCreateBatch" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingBatch" @click="handleCreateBatch">创建</el-button>
      </template>
    </el-dialog>

    <!-- 价格校验（历史成交价联动） -->
    <el-dialog v-model="priceCheckVisible" :title="priceCheckTitle" width="880px">
      <div v-if="priceCheckSummary" class="verdict-summary">
        <el-tag type="warning" effect="light">偏低 {{ priceCheckSummary.low }}</el-tag>
        <el-tag type="success" effect="light">合理 {{ priceCheckSummary.normal }}</el-tag>
        <el-tag type="danger" effect="light">偏高 {{ priceCheckSummary.high }}</el-tag>
        <el-tag type="info" effect="light">无参考 {{ priceCheckSummary.no_reference }}</el-tag>
        <span class="muted">容差 ±{{ Math.round(priceCheckSummary.tolerance * 100) }}%</span>
      </div>
      <el-table
        v-loading="priceCheckLoading"
        :data="priceCheckRows"
        border
        size="small"
        empty-text="暂无校验数据"
      >
        <el-table-column prop="supplier_name" label="供应商" width="120" show-overflow-tooltip />
        <el-table-column prop="product_name" label="产品名称" min-width="140" show-overflow-tooltip />
        <el-table-column label="单价" width="110" align="right">
          <template #default="{ row }">
            {{ row.unit_price === null ? '-' : `${row.currency} ${row.unit_price}` }}
          </template>
        </el-table-column>
        <el-table-column label="判定" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="verdictTag(row.verdict)" size="small" effect="light">{{ verdictText(row.verdict) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="偏离" width="90" align="right">
          <template #default="{ row }">
            {{ row.deviation_rate === null ? '-' : `${(row.deviation_rate * 100).toFixed(1)}%` }}
          </template>
        </el-table-column>
        <el-table-column label="参考均价" width="100" align="right">
          <template #default="{ row }">{{ row.reference_avg === null ? '-' : row.reference_avg }}</template>
        </el-table-column>
        <el-table-column prop="message" label="说明" min-width="220" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="priceCheckVisible = false">关闭</el-button>
      </template>
    </el-dialog>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, type UploadUserFile } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  compareQuoteBatch,
  confirmQuoteItem,
  createQuoteBatch,
  fetchQuoteBatch,
  fetchQuoteBatches,
  fetchQuoteItems,
  parseQuoteBatch,
  parseQuoteSource,
  uploadQuoteSource,
  type CompareResult,
  type QuoteBatch,
  type QuoteItem,
} from '@/api/quotes'
import {
  checkQuoteBatchPrices,
  checkQuoteItemPrice,
  type BatchPriceCheckItem,
  type BatchPriceCheckResult,
  type PriceVerdict,
} from '@/api/priceReference'

const ACCEPT = '.xlsx,.xls,.docx,.pdf,.png,.jpg,.jpeg'
const CURRENCIES = ['CNY', 'USD', 'EUR', 'GBP']
const DIMENSIONS = [
  { key: 'price', label: '价格' },
  { key: 'moq', label: 'MOQ（起订量）' },
  { key: 'lead_time', label: '货期' },
  { key: 'confidence', label: '置信度' },
]

const batches = ref<QuoteBatch[]>([])
const currentBatchId = ref<number | null>(null)
const currentBatch = ref<QuoteBatch | null>(null)

const fileList = ref<UploadUserFile[]>([])
const uploading = ref(false)

const items = ref<QuoteItem[]>([])
const itemsLoading = ref(false)
const parsing = ref(false)
const parsingId = ref<number | null>(null)
const confirming = ref(false)

const weights = reactive<Record<string, number>>({ price: 0.5, moq: 0.2, lead_time: 0.2, confidence: 0.1 })
const comparing = ref(false)
const compareResult = ref<CompareResult | null>(null)

const batchDialogVisible = ref(false)
const newBatchName = ref('')
const creatingBatch = ref(false)

// 价格校验（历史成交价联动）
const priceCheckVisible = ref(false)
const priceCheckLoading = ref(false)
const priceCheckTitle = ref('价格校验')
const priceCheckRows = ref<BatchPriceCheckItem[]>([])
const priceCheckSummary = ref<BatchPriceCheckResult | null>(null)

const VERDICT_TEXT: Record<PriceVerdict, string> = {
  low: '偏低',
  normal: '合理',
  high: '偏高',
  no_reference: '无参考',
}
const VERDICT_TAG: Record<PriceVerdict, 'success' | 'info' | 'warning' | 'danger'> = {
  low: 'warning',
  normal: 'success',
  high: 'danger',
  no_reference: 'info',
}

function verdictText(value: PriceVerdict): string {
  return VERDICT_TEXT[value] ?? value
}
function verdictTag(value: PriceVerdict): 'success' | 'info' | 'warning' | 'danger' {
  return VERDICT_TAG[value] ?? 'info'
}

const confirmedCount = computed(() => items.value.filter((i) => i.confirmed).length)
const unconfirmedCount = computed(() => items.value.length - confirmedCount.value)

const sourceNameMap = computed<Record<number, string>>(() => {
  const map: Record<number, string> = {}
  for (const s of currentBatch.value?.sources ?? []) {
    map[s.id] = s.supplier_name || s.file_name
  }
  return map
})

function sourceName(sourceId: number): string {
  return sourceNameMap.value[sourceId] ?? `#${sourceId}`
}

function errorMessage(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) return '提交数据不合法，请检查后重试'
  return fallback
}

function statusText(status: string): string {
  return { uploaded: '待上传', parsing: '解析中', parsed: '待确认', confirmed: '已确认', compared: '已比价' }[status] ?? status
}
function statusTagType(status: string): 'success' | 'info' | 'warning' | 'primary' {
  if (status === 'compared') return 'success'
  if (status === 'confirmed') return 'primary'
  if (status === 'parsing') return 'warning'
  return 'info'
}
function parseText(status: string): string {
  return { pending: '待解析', parsing: '解析中', success: '解析成功', failed: '解析失败' }[status] ?? status
}
function parseTagType(status: string): 'success' | 'info' | 'warning' | 'danger' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'parsing') return 'warning'
  return 'info'
}
function confidenceTagType(confidence: number): 'success' | 'warning' | 'danger' {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.5) return 'warning'
  return 'danger'
}
function rowClassName({ row }: { row: { is_best: boolean } }): string {
  return row.is_best ? 'best-row' : ''
}

async function loadBatches() {
  try {
    batches.value = await fetchQuoteBatches()
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载批次列表失败'))
  }
}

async function loadCurrentBatch() {
  if (currentBatchId.value === null) return
  currentBatch.value = await fetchQuoteBatch(currentBatchId.value)
}

async function loadItems() {
  if (currentBatchId.value === null) {
    items.value = []
    return
  }
  itemsLoading.value = true
  try {
    items.value = await fetchQuoteItems(currentBatchId.value)
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载明细失败'))
  } finally {
    itemsLoading.value = false
  }
}

async function handleBatchChange() {
  compareResult.value = null
  fileList.value = []
  await Promise.all([loadCurrentBatch(), loadItems()])
}

async function handleCreateBatch() {
  const name = newBatchName.value.trim()
  if (!name) {
    ElMessage.warning('请输入批次名称')
    return
  }
  creatingBatch.value = true
  try {
    const batch = await createQuoteBatch(name)
    batches.value = [batch, ...batches.value]
    currentBatchId.value = batch.id
    newBatchName.value = ''
    batchDialogVisible.value = false
    await handleBatchChange()
    ElMessage.success('批次已创建')
  } catch (e) {
    ElMessage.error(errorMessage(e, '创建批次失败'))
  } finally {
    creatingBatch.value = false
  }
}

function onFileChange(_file: UploadUserFile, list: UploadUserFile[]) {
  fileList.value = list
}
function onFileRemove(_file: UploadUserFile, list: UploadUserFile[]) {
  fileList.value = list
}

async function handleUploadAll() {
  if (currentBatchId.value === null || !fileList.value.length) return
  uploading.value = true
  let ok = 0
  try {
    for (const f of fileList.value) {
      if (!f.raw) continue
      const supplier = f.name.replace(/\.[^.]+$/, '')
      await uploadQuoteSource(currentBatchId.value, f.raw, supplier)
      ok += 1
    }
    fileList.value = []
    await Promise.all([loadCurrentBatch(), loadBatches()])
    ElMessage.success(`已上传 ${ok} 份报价文件`)
  } catch (e) {
    ElMessage.error(errorMessage(e, '上传失败'))
  } finally {
    uploading.value = false
  }
}

async function handleParseOne(sourceId: number) {
  parsingId.value = sourceId
  try {
    const parsed = await parseQuoteSource(sourceId)
    ElMessage.success(`解析完成，得到 ${parsed.length} 条明细`)
    await Promise.all([loadCurrentBatch(), loadItems()])
  } catch (e) {
    ElMessage.error(errorMessage(e, '解析失败，请人工录入'))
    await loadCurrentBatch()
  } finally {
    parsingId.value = null
  }
}

async function handleParseAll() {
  if (currentBatchId.value === null) return
  parsing.value = true
  try {
    const parsed = await parseQuoteBatch(currentBatchId.value)
    await Promise.all([loadCurrentBatch(), loadItems()])
    ElMessage.success(parsed.length ? `解析完成，共 ${parsed.length} 条明细` : '未解析出明细，请检查文件表头')
  } catch (e) {
    ElMessage.error(errorMessage(e, '批量解析失败'))
  } finally {
    parsing.value = false
  }
}

async function confirmRow(row: QuoteItem) {
  await confirmQuoteItem(row.id, {
    product_name: row.product_name,
    spec: row.spec,
    unit_price: row.unit_price,
    currency: row.currency,
    moq: row.moq,
    lead_time_days: row.lead_time_days,
    valid_until: row.valid_until,
    remarks: row.remarks,
  })
}

async function handleConfirmOne(row: QuoteItem) {
  try {
    await confirmRow(row)
    row.confirmed = true
    ElMessage.success('已确认')
    await loadCurrentBatch()
  } catch (e) {
    ElMessage.error(errorMessage(e, '确认失败'))
  }
}

async function handleConfirmAll() {
  const pending = items.value.filter((i) => !i.confirmed)
  if (!pending.length) return
  confirming.value = true
  try {
    for (const row of pending) {
      await confirmRow(row)
      row.confirmed = true
    }
    ElMessage.success(`已确认 ${pending.length} 条明细`)
    await loadCurrentBatch()
  } catch (e) {
    ElMessage.error(errorMessage(e, '批量确认失败'))
  } finally {
    confirming.value = false
  }
}

async function handleCompare() {
  if (currentBatchId.value === null) return
  comparing.value = true
  try {
    compareResult.value = await compareQuoteBatch(currentBatchId.value, { ...weights })
    await loadCurrentBatch()
    ElMessage.success('比价完成')
  } catch (e) {
    ElMessage.error(errorMessage(e, '比价失败'))
  } finally {
    comparing.value = false
  }
}

/** 单条明细：与历史成交价比较，校验报价合理性 */
async function handleCheckRow(row: QuoteItem) {
  priceCheckTitle.value = '价格校验'
  priceCheckRows.value = []
  priceCheckSummary.value = null
  priceCheckVisible.value = true
  priceCheckLoading.value = true
  try {
    const res = await checkQuoteItemPrice(row.id, {})
    priceCheckRows.value = [
      {
        item_id: row.id,
        supplier_name: sourceName(row.source_id),
        product_name: row.product_name,
        spec: row.spec,
        unit_price: res.unit_price,
        currency: res.currency,
        verdict: res.verdict,
        deviation_rate: res.deviation_rate,
        reference_avg: res.reference_avg,
        sample_count: res.sample_count,
        match_by: res.match_by,
        message: res.message,
      },
    ]
  } catch (e) {
    priceCheckVisible.value = false
    ElMessage.error(errorMessage(e, '价格校验失败'))
  } finally {
    priceCheckLoading.value = false
  }
}

/** 批次级：逐条与历史成交价比较并汇总判定分布 */
async function handleCheckBatch() {
  if (currentBatchId.value === null) return
  priceCheckTitle.value = '批次价格校验'
  priceCheckRows.value = []
  priceCheckSummary.value = null
  priceCheckVisible.value = true
  priceCheckLoading.value = true
  try {
    const res = await checkQuoteBatchPrices(currentBatchId.value, {})
    priceCheckRows.value = res.items
    priceCheckSummary.value = res
  } catch (e) {
    priceCheckVisible.value = false
    ElMessage.error(errorMessage(e, '价格校验失败'))
  } finally {
    priceCheckLoading.value = false
  }
}

onMounted(async () => {
  await loadBatches()
  if (batches.value.length) {
    currentBatchId.value = batches.value[0].id
    await handleBatchChange()
  }
})
</script>

<style scoped>
.quotes-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.block :deep(.el-card__header) {
  padding: 12px 16px;
}
.card-title {
  font-weight: 600;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.batch-bar {
  display: flex;
  align-items: center;
}
.batch-select {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.batch-select .label {
  font-weight: 500;
}
.upload-actions {
  margin-top: 12px;
}
.source-table {
  margin-top: 12px;
}
.weights {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 8px 32px;
}
.weight-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}
.weight-value {
  color: var(--brand-600);
  font-weight: 600;
}
.weights :deep(.el-slider) {
  margin-bottom: 4px;
}
.group {
  margin-bottom: 20px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.group-title .product {
  font-weight: 600;
}
.group-title .spec {
  color: var(--muted);
  font-size: 13px;
}
.muted {
  color: var(--muted);
}
.verdict-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
:deep(.best-row) {
  background-color: #f0fdf9;
}
:deep(.best-row td) {
  font-weight: 600;
}
</style>