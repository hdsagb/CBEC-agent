<template>
  <div class="editor">
    <div class="ed-main">
      <div class="ed-toolbar">
        <div class="group">
          <span class="lbl">画布</span>
          <input v-model.number="draft.width_mm" class="mini" type="number" min="10" max="1000" step="5" />
          <span class="times">×</span>
          <input v-model.number="draft.height_mm" class="mini" type="number" min="10" max="1000" step="5" />
          <span class="unit">mm</span>
          <label class="chk"><input v-model="draft.border" type="checkbox" /> 边框</label>
          <label class="chk"><input v-model="snap" type="checkbox" /> 吸附</label>
        </div>
        <div class="group">
          <span class="lbl">缩放</span>
          <button class="zbtn" type="button" @click="zoom(-1)">−</button>
          <span class="zoom">{{ pxPerMm.toFixed(1) }}</span>
          <button class="zbtn" type="button" @click="zoom(1)">+</button>
        </div>
        <div class="group">
          <button
            v-for="kind in KINDS"
            :key="kind"
            class="btn"
            type="button"
            @click="addBlock(kind)"
          >
            + {{ KIND_LABEL[kind] }}
          </button>
          <button class="btn danger" type="button" :disabled="selected === null" @click="removeSelected">删除元素</button>
        </div>
      </div>

      <div class="ed-canvas-wrap">
        <svg
          class="ed-canvas"
          :width="canvasW"
          :height="canvasH"
          @pointerdown.self="selected = null"
        >
          <defs>
            <pattern id="ed-grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M10 0 L0 0 0 10" fill="none" stroke="#e6ebf2" stroke-width="0.6" />
            </pattern>
          </defs>
          <rect class="grid" :width="canvasW" :height="canvasH" fill="url(#ed-grid)" />
          <rect class="ed-frame" x="0.5" y="0.5" :width="canvasW - 1" :height="canvasH - 1" v-if="draft.border" />

          <g class="guide">
            <text v-if="draft.title" class="g-title" :x="canvasW / 2" y="18" text-anchor="middle">{{ draft.title }}</text>
            <rect
              v-if="draft.rows.length"
              class="g-rows"
              x="6"
              :y="26"
              :width="Math.max(0, canvasW - 12)"
              :height="Math.max(0, canvasH - 26 - (draft.footer ? 24 : 6))"
            />
            <text v-if="draft.rows.length" class="g-rows-label" :x="canvasW / 2" :y="canvasH / 2" text-anchor="middle">
              {{ draft.rows.length }} 行字段 · 自动均分
            </text>
            <text v-if="draft.footer" class="g-footer" :x="canvasW / 2" :y="canvasH - 9" text-anchor="middle">{{ draft.footer }}</text>
          </g>

          <g v-for="(block, index) in draft.blocks" :key="index">
            <rect
              class="hit"
              :class="{ sel: selected === index }"
              :x="px(block.x_mm)"
              :y="px(block.y_mm)"
              :width="px(blockW(block))"
              :height="px(blockH(block))"
              @pointerdown.stop="startDrag($event, index)"
            />
            <text
              v-if="block.kind === 'text'"
              class="el-text"
              :x="textX(block)"
              :y="px(block.y_mm) + textSize(block) * 0.86"
              :font-size="textSize(block)"
              :font-weight="block.bold ? 700 : 400"
              :text-anchor="textAnchor(block)"
            >{{ block.text || '（空文字）' }}</text>
            <image
              v-else-if="block.kind === 'image' && block.src"
              class="el-image"
              :href="block.src"
              :x="px(block.x_mm)"
              :y="px(block.y_mm)"
              :width="px(blockW(block))"
              :height="px(blockH(block))"
              preserveAspectRatio="none"
            />
            <g v-else class="ph">
              <rect class="ph-bg" :x="px(block.x_mm)" :y="px(block.y_mm)" :width="px(blockW(block))" :height="px(blockH(block))" />
              <text
                class="ph-label"
                :x="px(block.x_mm) + px(blockW(block)) / 2"
                :y="px(block.y_mm) + px(blockH(block)) / 2 + 3.5"
                text-anchor="middle"
              >{{ KIND_LABEL[block.kind] }}</text>
            </g>
            <rect
              v-if="block.kind !== 'text' && selected === index"
              class="handle"
              :x="px(block.x_mm) + px(blockW(block)) - 4"
              :y="px(block.y_mm) + px(blockH(block)) - 4"
              width="8"
              height="8"
              @pointerdown.stop="startResize($event, index)"
            />
          </g>
        </svg>
      </div>

      <div class="ed-preview">
        <div class="preview-hd">
          <b>真实渲染预览</b>
          <span class="hint">由服务端 300dpi 渲染引擎出图，与最终导出完全一致</span>
        </div>
        <div class="preview-bar">
          <input v-model="previewOrder" class="mini wide" placeholder="订单号" />
          <span class="lbl">第</span>
          <input v-model.number="previewBoxNo" class="mini" type="number" min="1" />
          <span class="lbl">箱</span>
          <button class="btn primary" type="button" :disabled="previewing" @click="runPreview">
            {{ previewing ? '渲染中…' : '生成预览' }}
          </button>
        </div>
        <div class="preview-fields">
          <div v-for="(field, index) in previewFields" :key="index" class="field-row">
            <input v-model="field.label" class="mini" placeholder="字段名，如 品名" />
            <input v-model="field.value" class="mini wide" placeholder="字段值（可含 {占位符}）" />
            <button class="zbtn" type="button" @click="previewFields.splice(index, 1)">−</button>
          </div>
          <button class="btn ghost" type="button" @click="previewFields.push({ label: '', value: '' })">+ 预览字段</button>
        </div>
        <div v-if="previewResult" class="preview-img">
          <img :src="previewResult.url" alt="箱唛预览" />
          <span class="hint">{{ previewResult.message }}</span>
        </div>
      </div>
    </div>

    <aside class="ed-side">
      <div class="side-block">
        <div class="side-hd"><b>模板</b></div>
        <label class="field">
          <span>名称</span>
          <input v-model="draft.name" class="mini wide" placeholder="如 标准出口唛" />
        </label>
        <label class="field">
          <span>标题</span>
          <input v-model="draft.title" class="mini wide" placeholder="SHIPPING MARK" />
        </label>
        <label class="field">
          <span>页脚</span>
          <input v-model="draft.footer" class="mini wide" placeholder="MADE IN CHINA" />
        </label>
      </div>

      <div class="side-block">
        <div class="side-hd">
          <b>行字段</b>
          <button class="btn ghost" type="button" @click="addRow">+ 添加</button>
        </div>
        <div v-if="!draft.rows.length" class="side-empty">暂无行字段，行式区域会自动均分画布</div>
        <div v-for="(row, index) in draft.rows" :key="index" class="field-row">
          <input v-model="row.label" class="mini" placeholder="标签/字段名" />
          <input v-model="row.value" class="mini wide" placeholder="取值（留空则取同名字段）" />
          <button class="zbtn" type="button" @click="removeRow(index)">−</button>
        </div>
      </div>

      <div class="side-block">
        <div class="side-hd"><b>元素属性</b></div>
        <div v-if="!selectedBlock" class="side-empty">在画布上点选一个元素后，可在此精确调整位置与内容</div>
        <template v-else>
          <div class="field">
            <span>类型</span>
            <span class="tag">{{ KIND_LABEL[selectedBlock.kind] }}</span>
          </div>
          <label v-if="selectedBlock.kind !== 'image'" class="field">
            <span>内容</span>
            <input v-model="selectedBlock.text" class="mini wide" placeholder="支持 {order_no} 等占位符" />
          </label>
          <div class="field-row">
            <label class="field">
              <span>X</span>
              <input v-model.number="selectedBlock.x_mm" class="mini" type="number" step="1" />
            </label>
            <label class="field">
              <span>Y</span>
              <input v-model.number="selectedBlock.y_mm" class="mini" type="number" step="1" />
            </label>
          </div>
          <div v-if="selectedBlock.kind === 'qrcode'" class="field-row">
            <label class="field">
              <span>边长 mm</span>
              <input v-model.number="selectedBlock.size_mm" class="mini" type="number" min="5" step="1" />
            </label>
          </div>
          <div v-else class="field-row">
            <label class="field">
              <span>宽 mm</span>
              <input v-model.number="selectedBlock.w_mm" class="mini" type="number" min="1" step="1" />
            </label>
            <label v-if="selectedBlock.kind !== 'text'" class="field">
              <span>高 mm</span>
              <input v-model.number="selectedBlock.h_mm" class="mini" type="number" min="1" step="1" />
            </label>
          </div>
          <template v-if="selectedBlock.kind === 'text'">
            <div class="field-row">
              <label class="field">
                <span>字号 pt</span>
                <input v-model.number="selectedBlock.size" class="mini" type="number" min="4" step="1" />
              </label>
              <label class="field">
                <span>对齐</span>
                <select v-model="selectedBlock.align" class="mini">
                  <option value="left">左</option>
                  <option value="center">中</option>
                  <option value="right">右</option>
                </select>
              </label>
            </div>
            <label class="chk"><input v-model="selectedBlock.bold" type="checkbox" /> 加粗</label>
          </template>
          <div v-if="selectedBlock.kind === 'image'" class="field">
            <span>素材</span>
            <span class="hint">{{ selectedBlock.src ? selectedBlock.src.split('/').pop() : '未选择' }}</span>
          </div>
        </template>
      </div>

      <div class="side-block">
        <div class="side-hd">
          <b>素材库</b>
          <button class="btn ghost" type="button" :disabled="uploading" @click="fileInput?.click()">
            {{ uploading ? '上传中…' : '+ 上传图片' }}
          </button>
          <input ref="fileInput" class="hidden-input" type="file" accept="image/*" @change="onPickFile" />
        </div>
        <div v-if="!assets.length" class="side-empty">还没有素材，上传 Logo 后可在图片元素中引用</div>
        <div v-else class="asset-grid">
          <div v-for="asset in assets" :key="asset.id" class="asset">
            <img :src="asset.file_url" :alt="asset.type" @click="pickAsset(asset)" />
            <button class="asset-del" type="button" @click="removeAsset(asset)">×</button>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'

import {
  deleteMarkAsset,
  previewMarkLayout,
  uploadMarkAsset,
  type MarkAsset,
  type MarkBlock,
  type MarkBlockKind,
  type MarkLayout,
  type MarkRow,
} from '@/api/marks'

const props = defineProps<{
  name: string
  layout: MarkLayout
  assets: MarkAsset[]
}>()

const emit = defineEmits<{
  (e: 'update:name', value: string): void
  (e: 'update:layout', value: MarkLayout): void
  (e: 'assets-changed'): void
}>()

const KINDS: MarkBlockKind[] = ['text', 'image', 'qrcode', 'barcode']
const KIND_LABEL: Record<MarkBlockKind, string> = {
  text: '文字',
  image: '图片',
  qrcode: '二维码',
  barcode: '条形码',
}
const PT_TO_MM = 25.4 / 72
const DEFAULT_SIZE: Record<MarkBlockKind, { w: number; h: number }> = {
  text: { w: 60, h: 8 },
  image: { w: 30, h: 30 },
  qrcode: { w: 25, h: 25 },
  barcode: { w: 60, h: 12 },
}

function toRows(rows?: MarkLayout['rows']): MarkRow[] {
  return (rows ?? []).map((row) =>
    typeof row === 'string' ? { label: row, value: '' } : { label: row.label ?? '', value: row.value ?? '' },
  )
}

// 组件按 key 重新挂载，故 draft 只需在挂载时从 props 深拷贝一次
const draft = reactive({
  name: props.name,
  width_mm: props.layout.width_mm || 100,
  height_mm: props.layout.height_mm || 100,
  border: props.layout.border !== false,
  title: props.layout.title ?? '',
  footer: props.layout.footer ?? '',
  separator: props.layout.separator ?? ': ',
  rows: toRows(props.layout.rows),
  blocks: (props.layout.blocks ?? []).map((block) => ({ ...block })) as MarkBlock[],
})

const pxPerMm = ref(3)
const snap = ref(true)
const selected = ref<number | null>(null)

const canvasW = computed(() => Math.round(draft.width_mm * pxPerMm.value))
const canvasH = computed(() => Math.round(draft.height_mm * pxPerMm.value))
const selectedBlock = computed<MarkBlock | null>(() =>
  selected.value === null ? null : draft.blocks[selected.value] ?? null,
)

function px(mm?: number | null): number {
  return (mm ?? 0) * pxPerMm.value
}

function blockW(block: MarkBlock): number {
  if (block.kind === 'qrcode') return block.size_mm ?? DEFAULT_SIZE.qrcode.w
  if (block.kind === 'text') return block.w_mm ?? Math.max(10, draft.width_mm - (block.x_mm ?? 0) - 4)
  return block.w_mm ?? DEFAULT_SIZE[block.kind].w
}

function blockH(block: MarkBlock): number {
  if (block.kind === 'qrcode') return block.size_mm ?? DEFAULT_SIZE.qrcode.w
  if (block.kind === 'text') return textSize(block) * 1.5 / pxPerMm.value
  return block.h_mm ?? DEFAULT_SIZE[block.kind].h
}

function textSize(block: MarkBlock): number {
  return (block.size ?? 12) * PT_TO_MM * pxPerMm.value
}

function textX(block: MarkBlock): number {
  const left = px(block.x_mm)
  const width = px(blockW(block))
  if (block.align === 'center') return left + width / 2
  if (block.align === 'right') return left + width
  return left
}

function textAnchor(block: MarkBlock): 'start' | 'middle' | 'end' {
  return block.align === 'center' ? 'middle' : block.align === 'right' ? 'end' : 'start'
}

function cleanBlock(block: MarkBlock): MarkBlock {
  const base: MarkBlock = { kind: block.kind, x_mm: block.x_mm ?? 0, y_mm: block.y_mm ?? 0 }
  if (block.kind === 'text') {
    return {
      ...base,
      text: block.text ?? '',
      w_mm: Math.round(blockW(block) * 10) / 10,
      size: block.size ?? 12,
      align: block.align ?? 'left',
      bold: !!block.bold,
    }
  }
  if (block.kind === 'image') {
    return { ...base, src: block.src ?? '', w_mm: block.w_mm ?? DEFAULT_SIZE.image.w, h_mm: block.h_mm ?? DEFAULT_SIZE.image.h }
  }
  if (block.kind === 'qrcode') {
    return { ...base, text: block.text ?? '', size_mm: block.size_mm ?? DEFAULT_SIZE.qrcode.w }
  }
  return { ...base, text: block.text ?? '', w_mm: block.w_mm ?? DEFAULT_SIZE.barcode.w, h_mm: block.h_mm ?? DEFAULT_SIZE.barcode.h }
}

/** 产出可直接落库的干净版式：去掉空行、补齐默认值、剔除 undefined 字段。 */
function serialize(): MarkLayout {
  return {
    width_mm: draft.width_mm,
    height_mm: draft.height_mm,
    dpi: props.layout.dpi ?? 300,
    margin_mm: props.layout.margin_mm ?? 4,
    border: draft.border,
    title: draft.title,
    footer: draft.footer,
    separator: draft.separator,
    rows: draft.rows
      .filter((row) => row.label || row.value)
      .map((row) => (row.value ? { label: row.label, value: row.value } : { label: row.label })),
    blocks: draft.blocks.map(cleanBlock),
  }
}

watch(
  draft,
  () => {
    emit('update:name', draft.name)
    emit('update:layout', serialize())
  },
  { deep: true },
)

function zoom(delta: number) {
  pxPerMm.value = Math.min(8, Math.max(1.5, pxPerMm.value + delta * 0.5))
}

function step(): number {
  return snap.value ? 1 : 0.5
}

function roundTo(value: number): number {
  const grid = step()
  return Math.round(value / grid) * grid
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function addBlock(kind: MarkBlockKind) {
  const size = DEFAULT_SIZE[kind]
  const gap = 3
  const margin = 6
  // 新元素依次排在前一个元素下方；纵向到底后另起一列，避免元素完全重叠看不清
  let y = margin
  let colRight = margin
  for (const block of draft.blocks) {
    y = Math.max(y, (block.y_mm ?? 0) + blockH(block) + gap)
    colRight = Math.max(colRight, (block.x_mm ?? 0) + blockW(block) + gap)
  }
  const wrapped = y + size.h > draft.height_mm
  const block: MarkBlock = {
    kind,
    x_mm: roundTo(clamp(wrapped ? colRight : margin, 0, Math.max(0, draft.width_mm - size.w))),
    y_mm: roundTo(clamp(wrapped ? margin : y, 0, Math.max(0, draft.height_mm - size.h))),
  }
  if (kind === 'text') {
    block.text = '新文字'
    block.size = 12
    block.align = 'left'
    block.w_mm = size.w
  } else if (kind === 'image') {
    block.src = props.assets[0]?.file_url ?? ''
    block.w_mm = size.w
    block.h_mm = size.h
  } else if (kind === 'qrcode') {
    block.text = '{order_no}'
    block.size_mm = size.w
  } else {
    block.text = '{order_no}'
    block.w_mm = size.w
    block.h_mm = size.h
  }
  draft.blocks.push(block)
  selected.value = draft.blocks.length - 1
}

function removeSelected() {
  if (selected.value === null) return
  draft.blocks.splice(selected.value, 1)
  selected.value = null
}

function addRow() {
  draft.rows.push({ label: '', value: '' })
}

function removeRow(index: number) {
  draft.rows.splice(index, 1)
}

interface DragState {
  mode: 'move' | 'resize'
  index: number
  startX: number
  startY: number
  x0: number
  y0: number
  w0: number
  h0: number
}

const drag = ref<DragState | null>(null)

function beginDrag(event: PointerEvent, index: number, mode: DragState['mode']) {
  selected.value = index
  const block = draft.blocks[index]
  drag.value = {
    mode,
    index,
    startX: event.clientX,
    startY: event.clientY,
    x0: block.x_mm ?? 0,
    y0: block.y_mm ?? 0,
    w0: blockW(block),
    h0: blockH(block),
  }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', stopDrag)
}

function startDrag(event: PointerEvent, index: number) {
  beginDrag(event, index, 'move')
}

function startResize(event: PointerEvent, index: number) {
  beginDrag(event, index, 'resize')
}

function onPointerMove(event: PointerEvent) {
  const state = drag.value
  if (!state) return
  const block = draft.blocks[state.index]
  const dxMm = (event.clientX - state.startX) / pxPerMm.value
  const dyMm = (event.clientY - state.startY) / pxPerMm.value

  if (state.mode === 'move') {
    block.x_mm = clamp(roundTo(state.x0 + dxMm), 0, Math.max(0, draft.width_mm - state.w0))
    block.y_mm = clamp(roundTo(state.y0 + dyMm), 0, Math.max(0, draft.height_mm - state.h0))
    return
  }
  const width = clamp(roundTo(state.w0 + dxMm), 5, Math.max(5, draft.width_mm - (block.x_mm ?? 0)))
  if (block.kind === 'qrcode') {
    block.size_mm = width
    return
  }
  block.w_mm = width
  if (block.kind !== 'text') {
    block.h_mm = clamp(roundTo(state.h0 + dyMm), 3, Math.max(3, draft.height_mm - (block.y_mm ?? 0)))
  }
}

function stopDrag() {
  drag.value = null
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', stopDrag)
}

onBeforeUnmount(stopDrag)

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function onPickFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  try {
    const asset = await uploadMarkAsset(file, 'logo')
    emit('assets-changed')
    if (selectedBlock.value?.kind === 'image') selectedBlock.value.src = asset.file_url
    ElMessage.success('素材已上传')
  } catch (error) {
    ElMessage.error(errorMessage(error, '素材上传失败'))
  } finally {
    uploading.value = false
  }
}

async function removeAsset(asset: MarkAsset) {
  try {
    await deleteMarkAsset(asset.id)
    emit('assets-changed')
    ElMessage.success('素材已删除')
  } catch (error) {
    ElMessage.error(errorMessage(error, '删除素材失败'))
  }
}

function pickAsset(asset: MarkAsset) {
  if (selectedBlock.value?.kind === 'image') {
    selectedBlock.value.src = asset.file_url
    return
  }
  ElMessage.info('请先在画布上选中一个图片元素，再点击素材应用')
}

const previewOrder = ref('SO-20261012-001')
const previewBoxNo = ref(1)
const previewing = ref(false)
const previewResult = ref<{ url: string; message: string } | null>(null)
const previewFields = ref<MarkRow[]>([
  { label: '品名', value: '蓝牙耳机' },
  { label: '目的港', value: 'LOS ANGELES' },
])

async function runPreview() {
  previewing.value = true
  try {
    const fields: Record<string, string> = {}
    for (const item of previewFields.value) {
      if (item.label) fields[item.label] = item.value ?? ''
    }
    const boxNo = Math.max(1, previewBoxNo.value || 1)
    const result = await previewMarkLayout({
      layout_json: JSON.stringify(serialize()),
      fields_json: JSON.stringify(fields),
      order_no: previewOrder.value,
      total_boxes: boxNo,
      start_no: 1,
      box_no: boxNo,
    })
    previewResult.value = { url: result.url, message: result.message }
  } catch (error) {
    ElMessage.error(errorMessage(error, '预览失败'))
  } finally {
    previewing.value = false
  }
}
</script>

<style scoped>
.editor {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 288px;
  gap: 14px;
  align-items: start;
}

.ed-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ed-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2, #f8fafc);
}

.group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.lbl {
  font-size: 12px;
  color: var(--muted);
}

.times,
.unit {
  font-size: 12px;
  color: var(--muted);
}

.mini {
  width: 62px;
  height: 26px;
  padding: 0 6px;
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #fff;
  color: inherit;
}

.mini.wide {
  width: 100%;
  min-width: 0;
}

.mini:focus {
  outline: none;
  border-color: var(--brand-500);
}

.zoom {
  min-width: 26px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

.zbtn {
  width: 24px;
  height: 24px;
  line-height: 1;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #fff;
  color: inherit;
  cursor: pointer;
}

.zbtn:hover {
  border-color: var(--brand-500);
  color: var(--brand-600);
}

.chk {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}

.btn {
  height: 26px;
  padding: 0 10px;
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #fff;
  color: inherit;
  cursor: pointer;
  transition: 0.15s;
}

.btn:hover:not(:disabled) {
  border-color: var(--brand-500);
  color: var(--brand-600);
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn.primary {
  border-color: var(--brand-500);
  background: var(--brand-500);
  color: #fff;
}

.btn.primary:hover:not(:disabled) {
  color: #fff;
  opacity: 0.9;
}

.btn.ghost {
  border-style: dashed;
}

.btn.danger:hover:not(:disabled) {
  border-color: #e5484d;
  color: #e5484d;
}

.ed-canvas-wrap {
  overflow: auto;
  max-height: 460px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background:
    repeating-conic-gradient(#f1f4f8 0% 25%, #ffffff 0% 50%) 50% / 16px 16px;
}

.ed-canvas {
  display: block;
  margin: 0 auto;
  background: #fff;
  touch-action: none;
  user-select: none;
}

.grid,
.ed-frame,
.guide {
  pointer-events: none;
}

.ed-frame {
  fill: none;
  stroke: #94a3b8;
  stroke-width: 1.2;
}

.g-title {
  font-size: 13px;
  font-weight: 700;
  fill: #334155;
}

.g-footer {
  font-size: 11px;
  fill: #334155;
}

.g-rows {
  fill: rgba(148, 163, 184, 0.08);
  stroke: #cbd5e1;
  stroke-dasharray: 4 3;
}

.g-rows-label {
  font-size: 10px;
  fill: #94a3b8;
}

.hit {
  fill: transparent;
  stroke: transparent;
  cursor: move;
  pointer-events: all;
}

.hit:hover {
  stroke: var(--brand-500);
  stroke-dasharray: 3 2;
}

.hit.sel {
  stroke: var(--brand-500);
  stroke-width: 1.4;
  fill: rgba(59, 130, 246, 0.06);
}

.el-text {
  fill: #0f172a;
  pointer-events: none;
}

/* 图片/二维码/条形码的视觉层必须让出指针事件，否则会挡住下方的 .hit 拖拽/选中层 */
.el-image,
.ph {
  pointer-events: none;
}

.ph-bg {
  fill: #eef2ff;
  stroke: #c7d2fe;
  stroke-dasharray: 3 2;
}

.ph-label {
  font-size: 10px;
  fill: #4f46e5;
}

.handle {
  fill: #fff;
  stroke: var(--brand-500);
  stroke-width: 1.2;
  cursor: nwse-resize;
}

.ed-preview {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  background: var(--surface-2, #f8fafc);
}

.preview-hd {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.preview-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.preview-bar .mini.wide {
  width: 200px;
}

.preview-fields {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.preview-img {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
}

.preview-img img {
  max-width: 100%;
  max-height: 360px;
  border: 1px solid var(--border);
  background: #fff;
}

.hint {
  font-size: 11.5px;
  color: var(--muted);
}

.ed-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 620px;
  overflow: auto;
  padding-right: 2px;
}

.side-block {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
}

.side-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.side-empty {
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.6;
}

.field {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.field > span:first-child {
  flex: 0 0 56px;
  font-size: 12px;
  color: var(--muted);
}

.field-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.field-row .field {
  margin-bottom: 0;
  flex: 1;
}

.field-row .field > span:first-child {
  flex: 0 0 22px;
}

.tag {
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  color: var(--brand-600, #2563eb);
}

.hidden-input {
  display: none;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 8px;
}

.asset {
  position: relative;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.asset img {
  display: block;
  width: 100%;
  height: 58px;
  object-fit: contain;
  cursor: pointer;
}

.asset-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  line-height: 1;
  border: none;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  cursor: pointer;
  font-size: 12px;
}
</style>
