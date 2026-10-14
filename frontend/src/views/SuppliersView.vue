<template>
  <div class="page">
    <div class="page-inner">
      <div class="page-head">
        <div>
          <h1>供应商库</h1>
          <p>沉淀供应商档案与历史报价数据，支撑「供应商优选」的长期决策。</p>
        </div>
        <div class="actions">
          <el-button v-if="canEdit" type="primary" @click="openCreate">新建供应商</el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab">
        <!-- ================= 供应商档案 ================= -->
        <el-tab-pane label="供应商档案" name="profiles">
          <el-card shadow="never" class="filter-card">
            <el-form :inline="true" @submit.prevent>
              <el-form-item label="关键词">
                <el-input
                  v-model="query.keyword"
                  placeholder="名称 / 地区 / 主营品类 / 联系人"
                  clearable
                  style="width: 260px"
                  @keyup.enter="handleSearch"
                />
              </el-form-item>
              <el-form-item label="状态">
                <el-select v-model="query.status" placeholder="全部" clearable style="width: 140px" @change="handleSearch">
                  <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
                <el-button @click="handleReset">重置</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card shadow="never" class="table-card">
            <el-table v-loading="loading" :data="rows" border stripe empty-text="暂无供应商档案">
              <el-table-column label="供应商" min-width="200">
                <template #default="{ row }">
                  <div class="cell-main">{{ row.name }}</div>
                  <div v-if="row.main_category" class="cell-sub">{{ row.main_category }}</div>
                </template>
              </el-table-column>
              <el-table-column label="地区" width="110">
                <template #default="{ row }">{{ row.region || '-' }}</template>
              </el-table-column>
              <el-table-column label="联系人" min-width="160">
                <template #default="{ row }">
                  <div v-if="row.contact_name">{{ row.contact_name }}</div>
                  <div v-if="row.contact_phone" class="cell-sub">{{ row.contact_phone }}</div>
                  <span v-if="!row.contact_name && !row.contact_phone">-</span>
                </template>
              </el-table-column>
              <el-table-column label="评级" width="150">
                <template #default="{ row }">
                  <el-rate :model-value="row.rating" disabled size="small" />
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="STATUS_META[row.status]?.type ?? 'info'" size="small">
                    {{ STATUS_META[row.status]?.label ?? row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="备注" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">{{ row.remarks || '-' }}</template>
              </el-table-column>
              <el-table-column label="更新时间" width="160">
                <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openQuotes(row)">历史报价</el-button>
                  <el-button v-if="canEdit" link type="primary" @click="openEdit(row)">编辑</el-button>
                  <el-button v-if="isAdmin" link type="danger" @click="handleDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>

            <div class="pager">
              <el-pagination
                v-model:current-page="query.page"
                v-model:page-size="query.page_size"
                :total="total"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                background
                @current-change="load"
                @size-change="handleSizeChange"
              />
            </div>
          </el-card>
        </el-tab-pane>

        <!-- ================= 历史报价库 ================= -->
        <el-tab-pane label="历史报价库" name="quotes">
          <el-card shadow="never" class="table-card">
            <div class="card-title">
              <b>供应商报价概览</b>
              <el-input
                v-model="statKeyword"
                placeholder="按供应商名称搜索"
                clearable
                style="width: 220px"
                @keyup.enter="loadStats"
                @clear="loadStats"
              />
            </div>
            <el-table v-loading="statsLoading" :data="stats" border stripe empty-text="暂无报价数据">
              <el-table-column label="供应商" min-width="180">
                <template #default="{ row }">
                  <div class="cell-main">{{ row.supplier_name }}</div>
                  <div v-if="row.supplier_id" class="cell-sub">
                    已建档<template v-if="row.region"> · {{ row.region }}</template>
                  </div>
                  <div v-else class="cell-sub warn">未建档</div>
                </template>
              </el-table-column>
              <el-table-column prop="item_count" label="报价条数" width="100" align="center" />
              <el-table-column prop="product_count" label="覆盖商品" width="100" align="center" />
              <el-table-column label="币种" width="120">
                <template #default="{ row }">{{ row.currencies.join(' / ') || '-' }}</template>
              </el-table-column>
              <el-table-column label="均价（按币种）" min-width="220">
                <template #default="{ row }">
                  <span v-if="!row.price_stats.length">-</span>
                  <span v-else>{{ row.price_stats.map((p: CurrencyPriceStat) => `${p.currency} ${fmtNum(p.avg_price)}`).join(' · ') }}</span>
                </template>
              </el-table-column>
              <el-table-column label="最近报价" width="160">
                <template #default="{ row }">{{ formatTime(row.last_quote_at) }}</template>
              </el-table-column>
              <el-table-column label="档案状态" width="110">
                <template #default="{ row }">
                  <el-tag v-if="row.status" :type="STATUS_META[row.status]?.type ?? 'info'" size="small">
                    {{ STATUS_META[row.status]?.label ?? row.status }}
                  </el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="110" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="drillIntoQuotes(row.supplier_name)">查看报价</el-button>
                </template>
              </el-table-column>
            </el-table>

            <div class="pager">
              <el-pagination
                v-model:current-page="statQuery.page"
                v-model:page-size="statQuery.page_size"
                :total="statTotal"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                background
                @current-change="loadStats"
                @size-change="handleStatSizeChange"
              />
            </div>
          </el-card>

          <el-card shadow="never" class="filter-card">
            <el-form :inline="true" @submit.prevent>
              <el-form-item label="商品/规格">
                <el-input
                  v-model="quoteQuery.keyword"
                  placeholder="商品名 / 规格 / 供应商名"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuoteSearch"
                />
              </el-form-item>
              <el-form-item label="供应商">
                <el-input
                  v-model="quoteQuery.supplier_name"
                  placeholder="精确匹配供应商名"
                  clearable
                  style="width: 200px"
                  @keyup.enter="handleQuoteSearch"
                />
              </el-form-item>
              <el-form-item label="币种">
                <el-select v-model="quoteQuery.currency" placeholder="全部" clearable style="width: 120px" @change="handleQuoteSearch">
                  <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="quotesLoading" @click="handleQuoteSearch">查询</el-button>
                <el-button @click="handleQuoteReset">重置</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card shadow="never" class="table-card">
            <el-table v-loading="quotesLoading" :data="quotes" border stripe empty-text="暂无历史报价记录">
              <el-table-column label="商品" min-width="200">
                <template #default="{ row }">
                  <div class="cell-main">{{ row.product_name || '-' }}</div>
                  <div v-if="row.spec" class="cell-sub">{{ row.spec }}</div>
                </template>
              </el-table-column>
              <el-table-column prop="supplier_name" label="供应商" min-width="150" show-overflow-tooltip />
              <el-table-column label="单价" width="130" align="right">
                <template #default="{ row }">
                  <span v-if="row.unit_price === null">-</span>
                  <span v-else>{{ row.currency }} {{ fmtNum(row.unit_price) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="MOQ" width="90" align="right">
                <template #default="{ row }">{{ row.moq ?? '-' }}</template>
              </el-table-column>
              <el-table-column label="货期(天)" width="100" align="right">
                <template #default="{ row }">{{ row.lead_time_days ?? '-' }}</template>
              </el-table-column>
              <el-table-column prop="batch_name" label="所属批次" min-width="150" show-overflow-tooltip />
              <el-table-column label="确认" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.confirmed ? 'success' : 'info'" size="small">{{ row.confirmed ? '已确认' : '待确认' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="报价时间" width="160">
                <template #default="{ row }">{{ formatTime(row.quote_time) }}</template>
              </el-table-column>
            </el-table>

            <div class="pager">
              <el-pagination
                v-model:current-page="quoteQuery.page"
                v-model:page-size="quoteQuery.page_size"
                :total="quoteTotal"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                background
                @current-change="loadQuotes"
                @size-change="handleQuoteSizeChange"
              />
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <!-- 新建 / 编辑 -->
      <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新建供应商' : '编辑供应商'" width="680px">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="供应商名称" prop="name">
                <el-input v-model="form.name" placeholder="全称，需唯一" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="地区">
                <el-input v-model="form.region" placeholder="如 深圳" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="主营品类">
                <el-input v-model="form.main_category" placeholder="如 消费电子" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="合作状态">
                <el-select v-model="form.status" style="width: 100%">
                  <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="联系人">
                <el-input v-model="form.contact_name" placeholder="可选" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="联系电话">
                <el-input v-model="form.contact_phone" placeholder="可选" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="联系邮箱">
                <el-input v-model="form.contact_email" placeholder="可选" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="综合评级">
                <el-rate v-model="form.rating" allow-half show-score />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="备注">
                <el-input v-model="form.remarks" type="textarea" :rows="3" placeholder="可选" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
        </template>
      </el-dialog>

      <!-- 档案关联的历史报价 -->
      <el-drawer v-model="quotesDrawerVisible" :title="`历史报价 · ${drawerSupplierName}`" size="720px">
        <el-table v-loading="drawerLoading" :data="drawerQuotes" border stripe empty-text="该供应商暂无历史报价">
          <el-table-column label="商品" min-width="180">
            <template #default="{ row }">
              <div class="cell-main">{{ row.product_name || '-' }}</div>
              <div v-if="row.spec" class="cell-sub">{{ row.spec }}</div>
            </template>
          </el-table-column>
          <el-table-column label="单价" width="120" align="right">
            <template #default="{ row }">
              <span v-if="row.unit_price === null">-</span>
              <span v-else>{{ row.currency }} {{ fmtNum(row.unit_price) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="batch_name" label="批次" min-width="150" show-overflow-tooltip />
          <el-table-column label="报价时间" width="160">
            <template #default="{ row }">{{ formatTime(row.quote_time) }}</template>
          </el-table-column>
        </el-table>
      </el-drawer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { useAuthStore } from '@/stores/auth'
import {
  createSupplier,
  deleteSupplier,
  fetchQuoteCurrencies,
  fetchQuotes,
  fetchQuoteStats,
  fetchSuppliers,
  fetchSupplierQuotes,
  updateSupplier,
  type CurrencyPriceStat,
  type SupplierItem,
  type SupplierPayload,
  type SupplierQuoteRow,
  type SupplierQuoteStat,
} from '@/api/suppliers'

const auth = useAuthStore()
const ROLE_LEVEL: Record<string, number> = { merchandiser: 0, customs: 1, admin: 2 }
const canEdit = computed(() => (ROLE_LEVEL[auth.user?.role ?? ''] ?? -1) >= 1)
const isAdmin = computed(() => auth.user?.role === 'admin')

const STATUS_OPTIONS = [
  { value: 'active', label: '合作中' },
  { value: 'paused', label: '暂停合作' },
  { value: 'blacklisted', label: '已拉黑' },
]
const STATUS_META: Record<string, { label: string; type: 'success' | 'warning' | 'danger' | 'info' }> = {
  active: { label: '合作中', type: 'success' },
  paused: { label: '暂停合作', type: 'warning' },
  blacklisted: { label: '已拉黑', type: 'danger' },
}

const activeTab = ref<'profiles' | 'quotes'>('profiles')

// ---- 档案列表 ----
const loading = ref(false)
const rows = ref<SupplierItem[]>([])
const total = ref(0)
const query = reactive({ keyword: '', status: '', page: 1, page_size: 10 })

// ---- 历史报价概览 ----
const statsLoading = ref(false)
const stats = ref<SupplierQuoteStat[]>([])
const statTotal = ref(0)
const statKeyword = ref('')
const statQuery = reactive({ page: 1, page_size: 10 })

// ---- 报价明细检索 ----
const quotesLoading = ref(false)
const quotes = ref<SupplierQuoteRow[]>([])
const quoteTotal = ref(0)
const currencies = ref<string[]>([])
const quoteQuery = reactive({ keyword: '', supplier_name: '', currency: '', page: 1, page_size: 10 })

// ---- 弹窗 ----
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

// ---- 档案历史报价抽屉 ----
const quotesDrawerVisible = ref(false)
const drawerLoading = ref(false)
const drawerSupplierName = ref('')
const drawerQuotes = ref<SupplierQuoteRow[]>([])

const emptyForm = (): SupplierPayload => ({
  name: '',
  region: '',
  main_category: '',
  contact_name: '',
  contact_phone: '',
  contact_email: '',
  rating: 0,
  status: 'active',
  remarks: '',
})
const form = reactive<SupplierPayload>(emptyForm())

const rules: FormRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }],
}

function fmtNum(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

function formatTime(value: string | null): string {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}

function errorMessage(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

// ---------------- 档案 ----------------

async function load() {
  loading.value = true
  try {
    const data = await fetchSuppliers({
      keyword: query.keyword || undefined,
      status: query.status || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    rows.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载供应商列表失败'))
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

function handleReset() {
  query.keyword = ''
  query.status = ''
  query.page = 1
  load()
}

function handleSizeChange() {
  query.page = 1
  load()
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row: SupplierItem) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    region: row.region,
    main_category: row.main_category,
    contact_name: row.contact_name,
    contact_phone: row.contact_phone,
    contact_email: row.contact_email,
    rating: row.rating,
    status: row.status,
    remarks: row.remarks,
  })
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await createSupplier({ ...form })
      ElMessage.success('新建成功')
    } else if (editingId.value !== null) {
      await updateSupplier(editingId.value, { ...form })
      ElMessage.success('保存成功')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '保存失败'))
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: SupplierItem) {
  try {
    await ElMessageBox.confirm(`确定删除供应商「${row.name}」的档案吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteSupplier(row.id)
    ElMessage.success('已删除')
    if (rows.value.length === 1 && query.page > 1) query.page -= 1
    load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '删除失败'))
  }
}

async function openQuotes(row: SupplierItem) {
  drawerSupplierName.value = row.name
  drawerQuotes.value = []
  quotesDrawerVisible.value = true
  drawerLoading.value = true
  try {
    const data = await fetchSupplierQuotes(row.id, { page: 1, page_size: 50 })
    drawerQuotes.value = data.items
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载历史报价失败'))
  } finally {
    drawerLoading.value = false
  }
}

// ---------------- 历史报价库 ----------------

async function loadStats() {
  statsLoading.value = true
  try {
    const data = await fetchQuoteStats({
      keyword: statKeyword.value || undefined,
      page: statQuery.page,
      page_size: statQuery.page_size,
    })
    stats.value = data.items
    statTotal.value = data.total
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载报价概览失败'))
  } finally {
    statsLoading.value = false
  }
}

function handleStatSizeChange() {
  statQuery.page = 1
  loadStats()
}

async function loadQuotes() {
  quotesLoading.value = true
  try {
    const data = await fetchQuotes({
      keyword: quoteQuery.keyword || undefined,
      supplier_name: quoteQuery.supplier_name || undefined,
      currency: quoteQuery.currency || undefined,
      page: quoteQuery.page,
      page_size: quoteQuery.page_size,
    })
    quotes.value = data.items
    quoteTotal.value = data.total
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载历史报价失败'))
  } finally {
    quotesLoading.value = false
  }
}

function handleQuoteSearch() {
  quoteQuery.page = 1
  loadQuotes()
}

function handleQuoteReset() {
  quoteQuery.keyword = ''
  quoteQuery.supplier_name = ''
  quoteQuery.currency = ''
  quoteQuery.page = 1
  loadQuotes()
}

function handleQuoteSizeChange() {
  quoteQuery.page = 1
  loadQuotes()
}

/** 从概览下钻到明细检索，按供应商名过滤 */
function drillIntoQuotes(supplierName: string) {
  quoteQuery.keyword = ''
  quoteQuery.supplier_name = supplierName
  quoteQuery.currency = ''
  quoteQuery.page = 1
  loadQuotes()
}

async function loadCurrencies() {
  try {
    currencies.value = await fetchQuoteCurrencies()
  } catch {
    currencies.value = []
  }
}

onMounted(() => {
  load()
  loadStats()
  loadQuotes()
  loadCurrencies()
})
</script>

<style scoped>
.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}
.filter-card {
  margin-bottom: 12px;
}
.table-card {
  margin-bottom: 12px;
}
.table-card :deep(.el-card__body) {
  padding-top: 12px;
}
.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.cell-main {
  font-weight: 500;
}
.cell-sub {
  color: var(--muted);
  font-size: 12px;
}
.cell-sub.warn {
  color: var(--el-color-warning, #e6a23c);
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>