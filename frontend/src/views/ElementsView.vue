<template>
  <div class="page">
    <div class="page-inner">
      <div class="page-head">
        <div>
          <h1>申报要素库</h1>
          <p>按「客户 + 产品」沉淀报关要素，检索复用、一键复制报关文本。</p>
        </div>
        <div class="actions">
          <el-button v-if="canEdit" link type="primary" @click="handleDownloadTemplate">下载模板</el-button>
          <el-button v-if="canEdit" :loading="importing" @click="triggerImport">导入 Excel</el-button>
          <el-button :loading="exporting" @click="handleExport">导出 Excel</el-button>
          <el-button v-if="canEdit" type="primary" @click="openCreate">新建要素</el-button>
          <input ref="fileInputRef" type="file" accept=".xlsx,.xlsm" class="hidden-file" @change="handleImportFile" />
        </div>
      </div>

      <div class="elements-page">
        <!-- 筛选栏 -->
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" @submit.prevent>
            <el-form-item label="关键词">
              <el-input
                v-model="query.keyword"
                placeholder="产品名 / 客户名 / HS编码 / 英文名"
                clearable
                style="width: 260px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="HS编码">
              <el-input v-model="query.hs_code" placeholder="如 8517" clearable style="width: 140px" @keyup.enter="handleSearch" />
            </el-form-item>
            <el-form-item label="客户">
              <el-input v-model="query.customer_name" placeholder="客户名称" clearable style="width: 160px" @keyup.enter="handleSearch" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

    <!-- 列表 -->
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="rows" border stripe empty-text="暂无要素记录">
        <el-table-column prop="hs_code" label="HS编码" width="120" />
        <el-table-column label="商品名称" min-width="200">
          <template #default="{ row }">
            <div class="cell-main">{{ row.product_name }}</div>
            <div v-if="row.name_en" class="cell-sub">{{ row.name_en }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" width="140" show-overflow-tooltip />
        <el-table-column label="品牌 / 型号" min-width="160">
          <template #default="{ row }">{{ [row.brand, row.model].filter(Boolean).join(' / ') || '-' }}</template>
        </el-table-column>
        <el-table-column label="规格" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.spec || '-' }}</template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="70" align="center" />
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link type="primary" @click="openDeclarationText(row)">复制报关文本</el-button>
            <el-button v-if="canEdit" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canEdit" link type="primary" @click="handleDuplicate(row)">复制复用</el-button>
            <el-button v-if="canDelete" link type="danger" @click="handleDelete(row)">删除</el-button>
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

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="要素详情" size="480px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="HS编码">{{ detail.hs_code }}</el-descriptions-item>
        <el-descriptions-item label="商品名称">{{ detail.product_name }}</el-descriptions-item>
        <el-descriptions-item label="英文名称">{{ detail.name_en || '-' }}</el-descriptions-item>
        <el-descriptions-item label="客户名称">{{ detail.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="品牌">{{ detail.brand || '-' }}</el-descriptions-item>
        <el-descriptions-item label="型号">{{ detail.model || '-' }}</el-descriptions-item>
        <el-descriptions-item label="规格">{{ detail.spec || '-' }}</el-descriptions-item>
        <el-descriptions-item label="材质">{{ detail.material || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用途">{{ detail.usage || '-' }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ detail.version }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatTime(detail.updated_at) }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="detail && parsedExtra(detail.elements_json).length">
        <div class="extra-title">其它要素</div>
        <el-descriptions :column="1" border>
          <el-descriptions-item v-for="(item, idx) in parsedExtra(detail.elements_json)" :key="idx" :label="item.name || '未命名'">
            {{ item.value || '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </template>

      <div class="extra-title">历史价格参考</div>
      <div v-loading="priceRefLoading" class="price-ref">
        <div v-if="priceRef" class="ref-head">
          <el-tag size="small" effect="plain">匹配方式：{{ matchByText(priceRef.match_by) }}</el-tag>
          <span class="muted">历史样本 {{ priceRef.sample_count }} 条</span>
        </div>
        <template v-if="priceRef && priceRef.currency_stats.length">
          <el-table :data="priceRef.currency_stats" size="small" border>
            <el-table-column prop="currency" label="币种" width="70" />
            <el-table-column label="样本" width="60" align="right">
              <template #default="{ row }">{{ row.item_count }}</template>
            </el-table-column>
            <el-table-column label="均价" align="right">
              <template #default="{ row }">{{ row.avg_price }}</template>
            </el-table-column>
            <el-table-column label="区间" align="right">
              <template #default="{ row }">{{ row.min_price }} ~ {{ row.max_price }}</template>
            </el-table-column>
          </el-table>
          <el-table :data="priceRef.samples" size="small" border class="sample-table">
            <el-table-column prop="supplier_name" label="供应商" min-width="100" show-overflow-tooltip />
            <el-table-column label="单价" width="110" align="right">
              <template #default="{ row }">{{ row.currency }} {{ row.unit_price }}</template>
            </el-table-column>
            <el-table-column label="报价时间" width="150">
              <template #default="{ row }">{{ formatTime(row.quote_time) }}</template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else-if="!priceRefLoading" :image-size="60" description="暂无历史参考价" />
      </div>
    </el-drawer>

    <!-- 新建 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新建要素' : '编辑要素'" width="680px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="HS编码" prop="hs_code">
              <el-input v-model="form.hs_code" placeholder="如 8517.62" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="商品名称" prop="product_name">
              <el-input v-model="form.product_name" placeholder="中文品名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="英文名称">
              <el-input v-model="form.name_en" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户名称" prop="customer_name">
              <el-input v-model="form.customer_name" placeholder="客户名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="品牌">
              <el-input v-model="form.brand" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格">
              <el-input v-model="form.spec" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="材质">
              <el-input v-model="form.material" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="用途">
              <el-input v-model="form.usage" placeholder="可选" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="其它要素">
          <div class="extra-editor">
            <div v-for="(item, idx) in extraRows" :key="idx" class="extra-row">
              <el-input v-model="item.name" placeholder="要素名称" style="width: 180px" />
              <el-input v-model="item.value" placeholder="要素值" style="flex: 1" />
              <el-button link type="danger" @click="extraRows.splice(idx, 1)">移除</el-button>
            </div>
            <el-button link type="primary" @click="extraRows.push({ name: '', value: '' })">+ 添加要素</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 报关格式文本 -->
    <el-dialog v-model="textVisible" title="报关格式文本" width="560px">
      <el-input v-model="declarationText" type="textarea" :rows="14" readonly />
      <template #footer>
        <el-button @click="textVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyToClipboard(declarationText)">复制到剪贴板</el-button>
      </template>
    </el-dialog>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  copyElement,
  createElement,
  deleteElement,
  downloadElementTemplate,
  exportElements,
  fetchDeclarationText,
  fetchElements,
  importElements,
  updateElement,
  type ElementItem,
  type ElementPayload,
} from '@/api/elements'
import { errorMessage } from '@/api/error'
import { fetchElementPriceReference, type PriceMatchBy, type PriceReference } from '@/api/priceReference'
import { can } from '@/permissions'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

const canEdit = computed(() => can(auth.user?.role, 'elements.write'))
const canDelete = computed(() => can(auth.user?.role, 'elements.delete'))

const loading = ref(false)
const rows = ref<ElementItem[]>([])
const total = ref(0)
const query = reactive({ keyword: '', hs_code: '', customer_name: '', page: 1, page_size: 10 })

const detailVisible = ref(false)
const detail = ref<ElementItem | null>(null)
const priceRef = ref<PriceReference | null>(null)
const priceRefLoading = ref(false)

const MATCH_BY_TEXT: Record<PriceMatchBy, string> = {
  product: '按商品名命中',
  hs_code: '同 HS 编码兜底',
  none: '无匹配',
}

function matchByText(value: PriceMatchBy): string {
  return MATCH_BY_TEXT[value] ?? value
}

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const extraRows = ref<{ name: string; value: string }[]>([])

const textVisible = ref(false)
const declarationText = ref('')

const exporting = ref(false)
const importing = ref(false)
const fileInputRef = ref<HTMLInputElement>()

const emptyForm = (): ElementPayload => ({
  hs_code: '',
  product_name: '',
  name_en: '',
  customer_name: '',
  brand: '',
  model: '',
  spec: '',
  material: '',
  usage: '',
  elements_json: '[]',
  source_file_url: '',
})
const form = reactive<ElementPayload>(emptyForm())

const rules: FormRules = {
  hs_code: [{ required: true, message: '请输入HS编码', trigger: 'blur' }],
  product_name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  customer_name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }],
}

function formatTime(value: string): string {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}

function parsedExtra(json: string): { name: string; value: string }[] {
  try {
    const arr = JSON.parse(json || '[]')
    if (!Array.isArray(arr)) return []
    return arr.map((i) => ({ name: String(i?.name ?? ''), value: String(i?.value ?? '') }))
  } catch {
    return []
  }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchElements({
      keyword: query.keyword || undefined,
      hs_code: query.hs_code || undefined,
      customer_name: query.customer_name || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    rows.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载要素列表失败'))
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
  query.hs_code = ''
  query.customer_name = ''
  query.page = 1
  load()
}

function handleSizeChange() {
  query.page = 1
  load()
}

function openDetail(row: ElementItem) {
  detail.value = row
  detailVisible.value = true
  priceRef.value = null
  priceRefLoading.value = true
  fetchElementPriceReference(row.id)
    .then((data) => {
      priceRef.value = data
    })
    .catch((e) => {
      ElMessage.error(errorMessage(e, '加载历史价格参考失败'))
    })
    .finally(() => {
      priceRefLoading.value = false
    })
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  Object.assign(form, emptyForm())
  extraRows.value = []
  dialogVisible.value = true
}

function openEdit(row: ElementItem) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    hs_code: row.hs_code,
    product_name: row.product_name,
    name_en: row.name_en,
    customer_name: row.customer_name,
    brand: row.brand,
    model: row.model,
    spec: row.spec,
    material: row.material,
    usage: row.usage,
    elements_json: row.elements_json,
    source_file_url: row.source_file_url,
  })
  extraRows.value = parsedExtra(row.elements_json)
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const payload: ElementPayload = {
    ...form,
    elements_json: JSON.stringify(extraRows.value.filter((r) => r.name || r.value)),
  }
  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await createElement(payload)
      ElMessage.success('新建成功')
    } else if (editingId.value !== null) {
      await updateElement(editingId.value, payload)
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

async function handleDuplicate(row: ElementItem) {
  try {
    await copyElement(row.id)
    ElMessage.success('已复制为一条新记录')
    load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '复制复用失败'))
  }
}

async function openDeclarationText(row: ElementItem) {
  try {
    const data = await fetchDeclarationText(row.id)
    declarationText.value = data.text
    textVisible.value = true
  } catch (e) {
    ElMessage.error(errorMessage(e, '获取报关文本失败'))
  }
}

async function copyToClipboard(text: string) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const area = document.createElement('textarea')
      area.value = text
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      document.execCommand('copy')
      document.body.removeChild(area)
    }
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请在文本框中手动选择复制')
  }
}

async function handleDelete(row: ElementItem) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.product_name}」这条要素记录吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteElement(row.id)
    ElMessage.success('已删除')
    if (rows.value.length === 1 && query.page > 1) query.page -= 1
    load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '删除失败'))
  }
}

/** 触发浏览器下载（blob 用 download 属性指定文件名） */
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function stamp(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`
}

/** 导出当前筛选条件下的全部记录 */
async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportElements({
      keyword: query.keyword || undefined,
      hs_code: query.hs_code || undefined,
      customer_name: query.customer_name || undefined,
    })
    saveBlob(blob, `申报要素_${stamp()}.xlsx`)
    ElMessage.success('导出完成')
  } catch (e) {
    ElMessage.error(errorMessage(e, '导出失败'))
  } finally {
    exporting.value = false
  }
}

async function handleDownloadTemplate() {
  try {
    saveBlob(await downloadElementTemplate(), '申报要素导入模板.xlsx')
  } catch (e) {
    ElMessage.error(errorMessage(e, '模板下载失败'))
  }
}

function triggerImport() {
  fileInputRef.value?.click()
}

async function handleImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  try {
    const res = await importElements(file)
    const summary = `共 ${res.total} 行：新增 ${res.created}，重复跳过 ${res.skipped}，无效 ${res.invalid}`
    if (res.invalid > 0) {
      await ElMessageBox.alert(`${summary}\n\n${res.errors.join('\n')}`, '导入完成（部分行未导入）', {
        confirmButtonText: '知道了',
      }).catch(() => undefined)
    } else {
      ElMessage.success(summary)
    }
    if (res.created > 0) {
      query.page = 1
      load()
    }
  } catch (e) {
    ElMessage.error(errorMessage(e, '导入失败'))
  } finally {
    importing.value = false
    input.value = '' // 允许连续导入同一个文件
  }
}

onMounted(() => {
  // 支持顶栏全局搜索带词进入
  const keyword = route.query.keyword
  if (typeof keyword === 'string' && keyword.trim()) {
    query.keyword = keyword.trim()
  }
  load()
})
</script>

<style scoped>
.elements-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}
.filter-card :deep(.el-card__body) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.table-card :deep(.el-card__body) {
  padding-top: 12px;
}
.cell-main {
  font-weight: 500;
}
.cell-sub {
  color: var(--muted);
  font-size: 12px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.extra-title {
  margin: 16px 0 8px;
  font-weight: 600;
}
.price-ref {
  min-height: 40px;
}
.ref-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.muted {
  color: var(--muted);
  font-size: 13px;
}
.sample-table {
  margin-top: 8px;
}
.extra-editor {
  width: 100%;
}
.extra-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.hidden-file {
  display: none;
}
</style>