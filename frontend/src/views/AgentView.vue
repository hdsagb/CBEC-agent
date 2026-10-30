<template>
  <div class="agent">
    <!-- ================= 会话列表 ================= -->
    <div class="conv-list">
      <div class="conv-head">
        <b>会话</b>
        <button class="btn-new" type="button" :disabled="creatingSession" @click="handleNewSession">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none">
            <path d="M12 5v14M5 12h14" stroke="#fff" stroke-width="2.2" stroke-linecap="round" />
          </svg>
          新建
        </button>
      </div>
      <div class="conv-scroll">
        <div v-if="sessionsLoading" class="conv-hint">加载中…</div>
        <template v-else-if="sessions.length">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="conv"
            :class="{ 'is-active': s.id === activeSessionId }"
          >
            <button class="conv-main" type="button" @click="selectSession(s.id)">
              <b>{{ s.title || '新会话' }}</b>
              <span>#{{ s.id }}</span>
            </button>
            <span class="conv-acts">
              <button class="act" type="button" title="重命名" @click.stop="handleRename(s)">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M4 20h4l10-10-4-4L4 16v4Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
                  <path d="M13.5 6.5l4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                </svg>
              </button>
              <button class="act danger" type="button" title="删除" @click.stop="handleDelete(s)">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </button>
            </span>
          </div>
        </template>
        <div v-else class="conv-hint">暂无会话，点击「新建」开始</div>
      </div>
    </div>

    <!-- ================= 对话流 ================= -->
    <div class="chat">
      <div class="chat-head">
        <div>
          <div class="t">{{ activeSession?.title || '新会话' }}</div>
          <div class="d">{{ headDesc }}</div>
        </div>
        <button class="chip-model" type="button" :title="llmTitle" @click="openLLMDialog">
          <span class="dot" :class="llmDotClass"></span>
          {{ llmModelLabel }}
        </button>
      </div>

      <div ref="streamRef" class="stream">
        <div class="stream-inner">
          <div v-if="messagesLoading" class="conv-hint">加载历史消息…</div>

          <div v-else-if="!turns.length" class="chat-empty">
            <div class="ce-mark">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M12 3l2.2 5.1L20 9.3l-4 3.7L17 19l-5-2.8L7 19l1-6-4-3.7 5.8-1.2L12 3Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" />
              </svg>
            </div>
            <h2>可以这样用 Agent</h2>
            <p>一句话调用申报要素检索、多供应商比价与箱唛任务；结果直接来自系统数据。</p>
            <div class="ce-list">
              <button v-for="s in SUGGESTIONS" :key="s" class="ce-item" type="button" @click="fillComposer(s)">
                {{ s }}
              </button>
            </div>
          </div>

          <template v-for="(turn, idx) in turns" :key="idx">
            <div v-if="turn.role === 'user'" class="msg user">
              <div class="ava">{{ initials }}</div>
              <div class="bubble">{{ turn.content }}</div>
            </div>

            <div v-else class="msg bot">
              <div class="ava" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none">
                  <path d="M12 3l2.2 5.1L20 9.3l-4 3.7L17 19l-5-2.8L7 19l1-6-4-3.7 5.8-1.2L12 3Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" />
                </svg>
              </div>
              <div class="bubble">
                <div v-if="turn.toolResults.length" class="tools">
                  <details
                    v-for="(tr, i) in turn.toolResults"
                    :key="i"
                    class="tool"
                    :class="toolClass(tr.name)"
                    open
                  >
                    <summary>
                      <span class="tico"><ToolIcon :name="tr.name" /></span>
                      <span class="t-title">
                        <span class="tname">{{ tr.name }}</span>
                        <span class="tmeta">{{ toolMeta(tr) }}</span>
                      </span>
                      <span class="tstat" :class="{ warn: toolFailed(tr) }">{{ toolStat(tr) }}</span>
                      <svg class="caret" viewBox="0 0 24 24" width="13" height="13" fill="none">
                        <path d="M9 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                    </summary>
                    <div class="tbody" v-html="highlightJson(pretty(tr.result))"></div>
                  </details>
                </div>

                <div v-if="turn.content" class="content">{{ turn.content }}</div>

                <div v-for="(card, i) in searchCards(turn)" :key="`s${i}`" class="data-card">
                  <div class="card-hd">
                    <ToolIcon name="search_elements" />
                    <b>申报要素检索结果</b>
                    <span class="hint">命中 {{ card.items.length }} 条</span>
                  </div>
                  <table>
                    <thead>
                      <tr><th>商品名称</th><th>HS编码</th><th>客户</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="it in card.items" :key="it.id">
                        <td>{{ it.product_name }}</td>
                        <td><code class="hsc">{{ it.hs_code }}</code></td>
                        <td>{{ it.customer_name }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div class="card-ft">
                    <button
                      v-for="it in card.items"
                      :key="`cite-${it.id}`"
                      class="cite"
                      type="button"
                      @click="copyDeclaration(it.id)"
                    >
                      <svg viewBox="0 0 24 24" fill="none">
                        <path d="M5 4h11l3 3v13H5V4Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
                        <path d="M8 9h7M8 13h7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                      </svg>
                      {{ it.product_name }} · {{ it.customer_name }}（点击复制报关文本）
                    </button>
                  </div>
                </div>

                <div v-for="(card, i) in compareCards(turn)" :key="`c${i}`" class="data-card">
                  <div class="card-hd">
                    <ToolIcon name="compare_quotes" />
                    <b>比价结果 · 批次 #{{ card.batchId ?? '—' }}</b>
                    <span v-if="card.recommended" class="hint">推荐供应商：{{ card.recommended }}</span>
                  </div>
                  <table v-if="card.rows.length">
                    <thead>
                      <tr><th>商品</th><th>规格</th><th>最优供应商</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, ri) in card.rows" :key="ri" :class="{ best: ri === 0 }">
                        <td>{{ row.product_name || '—' }}</td>
                        <td>{{ row.spec || '—' }}</td>
                        <td>
                          {{ row.best_supplier || '—' }}
                          <span v-if="ri === 0" class="pill best">最优</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="card-ft muted">该批次暂无可比价结果（请先确认明细）</div>
                </div>

                <div v-for="(card, i) in exportCards(turn)" :key="`m${i}`" class="data-card">
                  <div class="card-hd">
                    <ToolIcon name="export_marks" />
                    <b>箱唛导出 · 任务 #{{ card.jobId ?? '—' }}</b>
                    <span class="hint">{{ card.format.toUpperCase() }}</span>
                  </div>
                  <div class="card-ft">
                    <a class="dl" :href="card.url" target="_blank" rel="noopener">
                      <svg viewBox="0 0 24 24" fill="none">
                        <path d="M12 3v10m0 0l-3.6-3.6M12 13l3.6-3.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                        <path d="M4 16v2.5A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5V16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                      </svg>
                      下载 {{ card.format.toUpperCase() }}
                    </a>
                    <span class="note">{{ card.message }}</span>
                  </div>
                </div>

                <div v-for="(card, i) in importCards(turn)" :key="`i${i}`" class="data-card">
                  <div class="card-hd">
                    <ToolIcon name="import_elements" />
                    <b>申报要素批量导入</b>
                    <span class="hint">新增 {{ card.created }} · 跳过重复 {{ card.skipped }} · 无效 {{ card.invalid }}</span>
                  </div>
                  <ul v-if="card.errors.length" class="err-list">
                    <li v-for="(msg, ei) in card.errors" :key="ei">{{ msg }}</li>
                  </ul>
                  <div v-else class="card-ft muted">全部记录已按「HS编码 + 商品名称 + 客户名称」去重处理</div>
                </div>

                <div v-for="(card, i) in batchCards(turn)" :key="`b${i}`" class="data-card">
                  <div class="card-hd">
                    <ToolIcon name="list_quote_batches" />
                    <b>比价批次</b>
                    <span class="hint">共 {{ card.items.length }} 个</span>
                  </div>
                  <table v-if="card.items.length">
                    <thead>
                      <tr><th>批次</th><th>名称</th><th>状态</th><th>供应商</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="b in card.items" :key="b.batchId">
                        <td>#{{ b.batchId }}</td>
                        <td>{{ b.name || '—' }}</td>
                        <td>{{ b.status || '—' }}</td>
                        <td>{{ b.sourceCount }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="card-ft muted">暂无比价批次</div>
                </div>
              </div>
            </div>
          </template>

          <div v-if="sending" class="msg bot">
            <div class="ava" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none">
                <path d="M12 3l2.2 5.1L20 9.3l-4 3.7L17 19l-5-2.8L7 19l1-6-4-3.7 5.8-1.2L12 3Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" />
              </svg>
            </div>
            <div class="bubble typing"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>

      <div class="composer">
        <div class="composer-inner">
          <div class="box">
            <textarea
              ref="inputRef"
              v-model="draft"
              rows="1"
              aria-label="向 Agent 提问"
              placeholder="输入指令，例如：帮我对比批次 #12 的报价并导出最优供应商"
              @input="autoGrow"
              @keydown="onKeydown"
            ></textarea>
            <div class="box-bar">
              <button class="mini" type="button" @click="goQuotes">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M8 12.5V7a4 4 0 1 1 8 0v9a2.5 2.5 0 1 1-5 0V8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                </svg>
                报价单
              </button>
              <button class="send" type="button" :disabled="sending || !draft.trim()" @click="handleSend">
                发送
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M4 12l16-8-6 8 6 8-16-8Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" />
                </svg>
              </button>
            </div>
          </div>
          <div class="legal">Agent 可能出错，关键报价与报关要素请以原始单据为准。</div>
        </div>
      </div>
    </div>

    <!-- ================= 上下文面板 ================= -->
    <div class="ctx">
      <div class="group">
        <h4>可调用能力</h4>
        <button v-for="t in tools" :key="t.name" class="cap" type="button" @click="insertCapability(t)">
          <span class="ico"><ToolIcon :name="t.name" /></span>
          <span class="cap-body">
            <b>{{ capabilityLabel(t.name) }}</b>
            <span>{{ t.description }}</span>
          </span>
        </button>
        <div v-if="!tools.length" class="conv-hint">工具列表加载中…</div>
      </div>

      <div class="group">
        <h4>本会话上下文</h4>
        <div class="kv"><span>会话</span><b>{{ activeSessionId === null ? '—' : `#${activeSessionId}` }}</b></div>
        <div class="kv"><span>对话轮次</span><b>{{ turns.length }}</b></div>
        <div class="kv"><span>工具调用</span><b>{{ toolCallTotal }} 次</b></div>
        <div class="kv"><span>可调用工具</span><b>{{ tools.length }} 个</b></div>
      </div>

      <div v-if="toolStats.length" class="group">
        <h4>工具调用统计</h4>
        <div v-for="s in toolStats" :key="s.name" class="kv"><span>{{ s.name }}</span><b>{{ s.count }} 次</b></div>
      </div>
    </div>

    <!-- 点击右上角模型芯片后，在画面中心弹出的配置窗口 -->
    <LLMModelDialog v-model="modelDialogVisible" :config="llmConfig" @saved="handleLLMSaved" />
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  createAgentSession,
  deleteAgentSession,
  fetchAgentMessages,
  fetchAgentSessions,
  fetchAgentTools,
  renameAgentSession,
  sendAgentMessage,
  type AgentTool,
  type ChatMessage,
  type ChatSession,
  type ToolResult,
} from '@/api/agent'
import { fetchDeclarationText } from '@/api/elements'
import { fetchLLMConfig, llmStatusLabel, refreshLLMStatus, type LLMConfig } from '@/api/settings'
import LLMModelDialog from '@/components/LLMModelDialog.vue'
import ToolIcon from '@/components/ToolIcon.vue'
import { useAuthStore } from '@/stores/auth'

interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  toolResults: ToolResult[]
}

interface SearchItem {
  id: number
  product_name: string
  hs_code: string
  customer_name: string
}

interface CompareRow {
  product_name: string
  spec: string
  best_supplier: string
}

const SUGGESTIONS = [
  '帮我查一下沃尔玛蓝牙耳机的申报要素',
  '对比批次 #1 的供应商报价，推荐最优供应商',
  '用标准出口唛生成一个 120 箱的箱唛任务',
  '把订单 SO-20261010-003 的箱唛导出成 PDF',
]

const CAPABILITY_LABEL: Record<string, string> = {
  search_elements: '检索申报要素',
  compare_quotes: '多供应商比价',
  create_marks: '生成箱唛任务',
  export_marks: '导出箱唛文件',
  import_elements: '批量导入要素',
  list_quote_batches: '查询比价批次',
}

const auth = useAuthStore()
const router = useRouter()

const tools = ref<AgentTool[]>([])
const sessions = ref<ChatSession[]>([])
const sessionsLoading = ref(false)
const creatingSession = ref(false)
const activeSessionId = ref<number | null>(null)

const turns = ref<ChatTurn[]>([])
const messagesLoading = ref(false)

const draft = ref('')
const sending = ref(false)
const streamRef = ref<HTMLElement>()
const inputRef = ref<HTMLTextAreaElement>()

/* ---------------- 大模型状态 ---------------- */
const llmConfig = ref<LLMConfig | null>(null)
const modelDialogVisible = ref(false)
let llmPollTimer: ReturnType<typeof setInterval> | undefined

const llmDotClass = computed(() => {
  const status = llmConfig.value?.status ?? 'unconfigured'
  if (status === 'ok') return 'ok'
  if (status === 'unconfigured') return 'idle'
  if (status === 'unknown') return 'warn'
  return 'bad'
})

const llmModelLabel = computed(() => llmConfig.value?.model || '未配置模型')

const llmTitle = computed(() => {
  const config = llmConfig.value
  if (!config) return '点击配置大模型'
  const status = llmStatusLabel(config.status)
  const lines = [`状态：${status}`, `接口：${config.base_url || '未配置'}`]
  if (config.status !== 'ok' && config.status_message) lines.push(config.status_message)
  lines.push('点击修改配置')
  return lines.join('\n')
})

const initials = computed(() => {
  const name = auth.user?.display_name || auth.user?.username || ''
  return name ? name.slice(0, 2).toUpperCase() : 'U'
})

const activeSession = computed(
  () => sessions.value.find((s) => s.id === activeSessionId.value) ?? null,
)

const headDesc = computed(() =>
  tools.value.length
    ? `已接入 ${tools.value.length} 个业务工具 · 数据实时来自本地系统`
    : '数据实时来自本地系统',
)

const toolCallTotal = computed(() =>
  turns.value.reduce((sum, turn) => sum + turn.toolResults.length, 0),
)

const toolStats = computed(() => {
  const counter = new Map<string, number>()
  for (const turn of turns.value) {
    for (const tr of turn.toolResults) {
      counter.set(tr.name, (counter.get(tr.name) ?? 0) + 1)
    }
  }
  return [...counter.entries()].map(([name, count]) => ({ name, count }))
})

/* ---------------- 工具函数 ---------------- */

function errorMessage(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : String(value)
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

function capabilityLabel(name: string): string {
  return CAPABILITY_LABEL[name] ?? name
}

function toolClass(name: string): string {
  if (name === 'search_elements') return 'violet'
  if (name === 'create_marks' || name === 'export_marks') return 'amber'
  return ''
}

function toolFailed(tr: ToolResult): boolean {
  return Boolean(asRecord(tr.result).error)
}

function toolMeta(tr: ToolResult): string {
  const r = asRecord(tr.result)
  if (r.error) return asText(r.error)
  if (tr.name === 'search_elements') return `命中 ${asText(r.count) || asArray(r.items).length} 条记录`
  if (tr.name === 'compare_quotes') return `批次 #${asText(r.batch_id) || '—'} · ${asArray(r.products).length} 个商品`
  if (tr.name === 'create_marks') return `任务 #${asText(r.job_id) || '—'} · ${asText(r.total_boxes) || '—'} 箱`
  if (tr.name === 'export_marks') return `任务 #${asText(r.job_id) || '—'} · ${asText(r.format).toUpperCase()} 文件`
  if (tr.name === 'import_elements') {
    return `新增 ${asText(r.created) || 0} · 跳过 ${asText(r.skipped) || 0} · 无效 ${asText(r.invalid) || 0}`
  }
  if (tr.name === 'list_quote_batches') return `共 ${asText(r.count) || 0} 个批次`
  return capabilityLabel(tr.name)
}

function toolStat(tr: ToolResult): string {
  if (toolFailed(tr)) return '失败'
  if (tr.name === 'search_elements') {
    const r = asRecord(tr.result)
    return `命中 ${asText(r.count) || asArray(r.items).length} 条`
  }
  if (tr.name === 'import_elements') return `新增 ${asText(asRecord(tr.result).created) || 0} 条`
  if (tr.name === 'export_marks') return '已出图'
  return '完成'
}

function pretty(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

/** 对 JSON 文本做轻量着色（先转义，再包裹 span，避免 XSS） */
function highlightJson(json: string): string {
  return json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/("(?:\\.|[^"\\])*")(\s*:)/g, '<span class="k">$1</span>$2')
    .replace(/:\s*("(?:\\.|[^"\\])*")/g, ': <span class="v">$1</span>')
    .replace(/:\s*(-?\d+(?:\.\d+)?)/g, ': <span class="v">$1</span>')
}

/** 后端 tool_calls_json 为标准 JSON 数组，解析失败时尝试单引号替换兼容旧数据 */
function parseToolResults(raw: string): ToolResult[] {
  if (!raw) return []
  for (const text of [raw, raw.replace(/'/g, '"')]) {
    try {
      const data: unknown = JSON.parse(text)
      if (Array.isArray(data)) {
        return data.map((item) => {
          const o = asRecord(item)
          return { name: asText(o.name), result: asRecord(o.result) }
        })
      }
    } catch {
      // 继续尝试下一种解析方式
    }
  }
  return []
}

function searchCards(turn: ChatTurn): { items: SearchItem[] }[] {
  return turn.toolResults
    .filter((tr) => tr.name === 'search_elements')
    .map((tr) => ({
      items: asArray(asRecord(tr.result).items).map((raw) => {
        const o = asRecord(raw)
        return {
          id: asNumber(o.id) ?? -1,
          product_name: asText(o.product_name),
          hs_code: asText(o.hs_code),
          customer_name: asText(o.customer_name),
        }
      }),
    }))
    .filter((card) => card.items.length > 0)
}

function compareCards(turn: ChatTurn): { batchId: number | null; recommended: string; rows: CompareRow[] }[] {
  return turn.toolResults
    .filter((tr) => tr.name === 'compare_quotes')
    .map((tr) => {
      const r = asRecord(tr.result)
      return {
        batchId: asNumber(r.batch_id),
        recommended: asText(r.recommended_supplier),
        rows: asArray(r.products).map((raw) => {
          const o = asRecord(raw)
          return {
            product_name: asText(o.product_name),
            spec: asText(o.spec),
            best_supplier: asText(o.best_supplier),
          }
        }),
      }
    })
}

function exportCards(turn: ChatTurn): { jobId: number | null; format: string; url: string; message: string }[] {
  return turn.toolResults
    .filter((tr) => tr.name === 'export_marks' && !asRecord(tr.result).error)
    .map((tr) => {
      const r = asRecord(tr.result)
      return {
        jobId: asNumber(r.job_id),
        format: asText(r.format) || 'pdf',
        url: asText(r.url),
        message: asText(r.message),
      }
    })
    .filter((card) => card.url)
}

function importCards(turn: ChatTurn): { created: number; skipped: number; invalid: number; errors: string[] }[] {
  return turn.toolResults
    .filter((tr) => tr.name === 'import_elements' && !asRecord(tr.result).error)
    .map((tr) => {
      const r = asRecord(tr.result)
      return {
        created: asNumber(r.created) ?? 0,
        skipped: asNumber(r.skipped) ?? 0,
        invalid: asNumber(r.invalid) ?? 0,
        errors: asArray(r.errors).map((msg) => asText(msg)),
      }
    })
}

function batchCards(turn: ChatTurn): { items: { batchId: number; name: string; status: string; sourceCount: number }[] }[] {
  return turn.toolResults
    .filter((tr) => tr.name === 'list_quote_batches' && !asRecord(tr.result).error)
    .map((tr) => ({
      items: asArray(asRecord(tr.result).items).map((raw) => {
        const o = asRecord(raw)
        return {
          batchId: asNumber(o.batch_id) ?? -1,
          name: asText(o.name),
          status: asText(o.status),
          sourceCount: asNumber(o.source_count) ?? 0,
        }
      }),
    }))
}

function toTurns(messages: ChatMessage[]): ChatTurn[] {
  return messages.map((m) => ({
    role: m.role === 'user' ? 'user' : 'assistant',
    content: m.content,
    toolResults: parseToolResults(m.tool_calls_json),
  }))
}

/* ---------------- 交互 ---------------- */

function scrollToBottom() {
  nextTick(() => {
    const el = streamRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function autoGrow() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 150)}px`
}

function fillComposer(text: string) {
  draft.value = text
  nextTick(() => {
    inputRef.value?.focus()
    autoGrow()
  })
}

function insertCapability(tool: AgentTool) {
  fillComposer(`请用「${capabilityLabel(tool.name)}」帮我处理：`)
}

function goQuotes() {
  router.push({ name: 'quotes' })
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    void handleSend()
  }
}

async function loadTools() {
  try {
    tools.value = await fetchAgentTools()
  } catch {
    tools.value = []
  }
}

/* ---------------- 大模型状态 ---------------- */

async function loadLLMConfig() {
  try {
    llmConfig.value = await fetchLLMConfig()
  } catch {
    // 未登录或接口异常时保持默认灰点，不打断对话
  }
}

async function pollLLMStatus() {
  try {
    const result = await refreshLLMStatus()
    llmConfig.value = result.config
  } catch {
    // 探测失败静默处理，芯片保留上一次状态
  }
}

function openLLMDialog() {
  modelDialogVisible.value = true
}

function handleLLMSaved(config: LLMConfig) {
  llmConfig.value = config
  void pollLLMStatus()
}

function onDocumentVisibility() {
  if (!document.hidden) void pollLLMStatus()
}

function startLLMPolling() {
  llmPollTimer = window.setInterval(() => {
    if (!document.hidden) void pollLLMStatus()
  }, 60000)
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    // 后端按创建顺序返回，这里倒序让最新会话排在前面
    sessions.value = (await fetchAgentSessions()).slice().sort((a, b) => b.id - a.id)
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载会话列表失败'))
  } finally {
    sessionsLoading.value = false
  }
}

async function loadMessages(sessionId: number) {
  messagesLoading.value = true
  try {
    const messages = await fetchAgentMessages(sessionId)
    turns.value = toTurns(messages)
  } catch (e) {
    turns.value = []
    ElMessage.error(errorMessage(e, '加载历史消息失败'))
  } finally {
    messagesLoading.value = false
    scrollToBottom()
  }
}

async function selectSession(sessionId: number) {
  if (activeSessionId.value === sessionId) return
  activeSessionId.value = sessionId
  turns.value = []
  await loadMessages(sessionId)
}

async function handleNewSession() {
  creatingSession.value = true
  try {
    const session = await createAgentSession()
    sessions.value = [session, ...sessions.value]
    activeSessionId.value = session.id
    turns.value = []
    draft.value = ''
    nextTick(autoGrow)
  } catch (e) {
    ElMessage.error(errorMessage(e, '新建会话失败'))
  } finally {
    creatingSession.value = false
  }
}

async function handleRename(session: ChatSession) {
  let title = ''
  try {
    const { value } = await ElMessageBox.prompt('请输入新的会话名称', '重命名会话', {
      inputValue: session.title || '新会话',
      inputPlaceholder: '会话名称',
      inputValidator: (v: string) => (v && v.trim() ? true : '名称不能为空'),
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    title = value.trim()
  } catch {
    // 用户取消或关闭弹窗
    return
  }
  if (!title || title === session.title) return
  try {
    const updated = await renameAgentSession(session.id, title)
    const idx = sessions.value.findIndex((item) => item.id === session.id)
    if (idx >= 0) sessions.value[idx] = updated
    ElMessage.success('已重命名')
  } catch (e) {
    ElMessage.error(errorMessage(e, '重命名失败'))
  }
}

async function handleDelete(session: ChatSession) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title || '新会话'}」吗？会话内的对话记录将一并清除。`,
      '删除会话',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteAgentSession(session.id)
    sessions.value = sessions.value.filter((item) => item.id !== session.id)
    if (activeSessionId.value === session.id) {
      activeSessionId.value = sessions.value[0]?.id ?? null
      turns.value = []
      if (activeSessionId.value !== null) await loadMessages(activeSessionId.value)
    }
    ElMessage.success('会话已删除')
  } catch (e) {
    ElMessage.error(errorMessage(e, '删除失败'))
  }
}

/** 首次进入时若无会话则自动建一个，保证可直接对话 */
async function ensureSession(): Promise<number | null> {
  if (activeSessionId.value !== null) return activeSessionId.value
  try {
    const session = await createAgentSession()
    sessions.value = [session, ...sessions.value]
    activeSessionId.value = session.id
    return session.id
  } catch (e) {
    ElMessage.error(errorMessage(e, '创建会话失败'))
    return null
  }
}

async function handleSend() {
  const text = draft.value.trim()
  if (!text || sending.value) return

  const sessionId = await ensureSession()
  if (sessionId === null) return

  turns.value.push({ role: 'user', content: text, toolResults: [] })
  draft.value = ''
  nextTick(autoGrow)
  scrollToBottom()

  sending.value = true
  try {
    const reply = await sendAgentMessage(sessionId, text)
    turns.value.push({
      role: 'assistant',
      content: reply.content,
      toolResults: parseToolResults(reply.tool_calls_json),
    })
  } catch (e) {
    ElMessage.error(errorMessage(e, 'Agent 响应失败，请重试'))
    turns.value.push({
      role: 'assistant',
      content: '抱歉，本次请求未能完成。请稍后重试，或改用「申报要素库 / 智能比价」页面直接操作。',
      toolResults: [],
    })
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

async function copyDeclaration(itemId: number) {
  if (itemId < 0) return
  try {
    const data = await fetchDeclarationText(itemId)
    await navigator.clipboard.writeText(data.text)
    ElMessage.success('已复制报关格式文本')
  } catch (e) {
    ElMessage.error(errorMessage(e, '获取报关文本失败，请前往申报要素库操作'))
  }
}

onMounted(async () => {
  // 芯片先用持久化的状态快速渲染，再异步真实探测一次
  void loadLLMConfig()
  void pollLLMStatus()
  startLLMPolling()
  document.addEventListener('visibilitychange', onDocumentVisibility)

  await Promise.all([loadTools(), loadSessions()])
  if (sessions.value.length) {
    activeSessionId.value = sessions.value[0].id
    await loadMessages(activeSessionId.value)
  }
})

onBeforeUnmount(() => {
  if (llmPollTimer) clearInterval(llmPollTimer)
  document.removeEventListener('visibilitychange', onDocumentVisibility)
})
</script>

<style scoped>
.agent {
  display: grid;
  grid-template-columns: 236px 1fr 264px;
  height: 100%;
  min-height: 0;
}

/* ---- 会话列表 ---- */
.conv-list {
  border-right: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.conv-head {
  padding: 14px 14px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conv-head b {
  font-size: 13px;
}

.btn-new {
  border: 0;
  background: var(--brand-600);
  color: #fff;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: 0.15s;
}

.btn-new:hover {
  background: #0b8276;
}

.btn-new:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.conv-scroll {
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.conv {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 1px solid transparent;
  border-radius: 9px;
  padding: 4px 6px 4px 0;
  margin-bottom: 3px;
  transition: 0.15s;
}

.conv-main {
  flex: 1;
  min-width: 0;
  text-align: left;
  border: 0;
  background: transparent;
  border-radius: 9px;
  padding: 5px 6px 5px 10px;
}

.conv:hover {
  background: var(--surface-2);
}

.conv.is-active {
  background: var(--brand-050);
  border-color: #bfeae4;
}

.conv-main b {
  display: block;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-main > span {
  font-size: 11px;
  color: var(--muted);
}

.conv-acts {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: 0.15s;
}

.conv:hover .conv-acts,
.conv.is-active .conv-acts {
  opacity: 1;
}

.conv-acts .act {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  transition: 0.15s;
}

.conv-acts .act svg {
  width: 14px;
  height: 14px;
}

.conv-acts .act:hover {
  background: var(--surface);
  color: var(--brand-600);
}

.conv-acts .act.danger:hover {
  color: #dc2626;
}

.conv-hint {
  padding: 14px 10px;
  font-size: 12px;
  color: var(--muted);
}

/* ---- 对话 ---- */
.chat {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--bg);
}

.chat-head {
  padding: 13px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-head .t {
  font-weight: 650;
  font-size: 14px;
}

.chat-head .d {
  font-size: 11.5px;
  color: var(--muted);
}

.chip-model {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-family: inherit;
  color: var(--text-2);
  border: 1px solid var(--border);
  background: var(--surface-2);
  border-radius: var(--radius-pill);
  padding: 5px 11px;
  white-space: nowrap;
  cursor: pointer;
  transition: 0.15s;
}

.chip-model:hover {
  border-color: var(--brand-500);
  color: var(--text);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand-500);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.18);
}

.dot.ok {
  background: var(--brand-500);
}

.dot.idle {
  background: #9ca3af;
  box-shadow: 0 0 0 3px rgba(156, 163, 175, 0.16);
}

.dot.warn {
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.16);
}

.dot.bad {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.16);
}

.stream {
  flex: 1;
  overflow-y: auto;
  padding: 22px 20px 8px;
}

.stream-inner {
  max-width: 820px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 48px 16px;
}

.ce-mark {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, var(--brand-500), var(--brand-600));
  box-shadow: 0 6px 16px rgba(13, 148, 136, 0.3);
  margin-bottom: 14px;
}

.ce-mark svg {
  width: 24px;
  height: 24px;
}

.chat-empty h2 {
  margin: 0 0 6px;
  font-size: 16px;
}

.chat-empty p {
  margin: 0 0 18px;
  font-size: 12.5px;
  color: var(--muted);
  max-width: 420px;
}

.ce-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 460px;
}

.ce-item {
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: var(--radius);
  padding: 11px 14px;
  font-size: 12.5px;
  color: var(--text-2);
  text-align: left;
  transition: 0.15s;
}

.ce-item:hover {
  border-color: var(--brand-500);
  color: var(--brand-600);
  background: var(--brand-050);
}

/* ---- 消息 ---- */
.msg {
  display: flex;
  gap: 12px;
  animation: rise 0.32s ease both;
}

.msg .ava {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  flex: none;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
}

.msg.user {
  flex-direction: row-reverse;
}

.msg.user .ava {
  background: var(--ink-800);
  color: #fff;
}

.msg.bot .ava {
  background: linear-gradient(145deg, var(--brand-500), var(--brand-600));
  color: #fff;
  box-shadow: 0 4px 10px rgba(13, 148, 136, 0.3);
}

.bubble {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 12px 15px;
  font-size: 13.5px;
  line-height: 1.68;
  box-shadow: var(--shadow-1);
  max-width: min(660px, 100%);
  overflow-x: auto;
}

.msg.user .bubble {
  background: var(--ink-800);
  border-color: var(--ink-800);
  color: #f1f5fb;
}

.msg.bot .bubble {
  max-width: 100%;
  width: 100%;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

.typing {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 16px 15px;
}

.typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--border-strong);
  animation: blink 1.2s infinite ease-in-out;
}

.typing span:nth-child(2) {
  animation-delay: 0.18s;
}

.typing span:nth-child(3) {
  animation-delay: 0.36s;
}

/* ---- 工具卡 ---- */
.tools {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.tool {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  overflow: hidden;
  transition: 0.18s;
}

.tool:hover {
  border-color: #c9d8d5;
  box-shadow: var(--shadow-1);
}

.tool summary {
  list-style: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 12px;
}

.tool summary::-webkit-details-marker {
  display: none;
}

.tool .tico {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex: none;
  background: var(--brand-050);
  color: var(--brand-600);
}

.tool .tico svg {
  width: 15px;
  height: 15px;
}

.tool.violet .tico {
  background: var(--violet-050);
  color: var(--violet-500);
}

.tool.amber .tico {
  background: var(--amber-050);
  color: #b45309;
}

.t-title {
  min-width: 0;
}

.tool .tname {
  font: 600 12.5px/1.3 var(--mono);
  color: var(--text);
  display: block;
}

.tool .tmeta {
  font-size: 11px;
  color: var(--muted);
  margin-top: 1px;
  display: block;
}

.tool .tstat {
  margin-left: auto;
  font-size: 10.5px;
  font-weight: 700;
  color: #067a6d;
  background: var(--brand-050);
  border-radius: var(--radius-pill);
  padding: 3px 8px;
  white-space: nowrap;
}

.tool .tstat.warn {
  color: #a15c00;
  background: var(--amber-050);
}

.tool .caret {
  color: var(--muted);
  transition: 0.2s;
  flex: none;
}

.tool[open] .caret {
  transform: rotate(90deg);
}

.tool .tbody {
  border-top: 1px solid var(--border);
  background: var(--surface-2);
  padding: 10px 12px;
  font: 11.5px/1.75 var(--mono);
  color: var(--text-2);
  white-space: pre-wrap;
  overflow-x: auto;
}

.tool .tbody :deep(.k) {
  color: var(--violet-500);
}

.tool .tbody :deep(.v) {
  color: #067a6d;
}

/* ---- 数据卡 ---- */
.data-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-1);
  overflow: hidden;
  margin: 12px 0;
}

.card-hd {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
}

.card-hd svg {
  width: 15px;
  height: 15px;
  color: var(--brand-600);
  flex: none;
}

.card-hd b {
  font-size: 12.5px;
}

.card-hd .hint {
  font-size: 11px;
  color: var(--muted);
  margin-left: auto;
}

.card-ft {
  padding: 12px 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.card-ft.muted {
  font-size: 12px;
  display: block;
}

.dl {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--brand-500);
  background: var(--brand-050);
  color: var(--brand-600);
  border-radius: 8px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 650;
  text-decoration: none;
  transition: 0.15s;
}

.dl:hover {
  background: var(--brand-500);
  color: #fff;
}

.dl svg {
  width: 14px;
  height: 14px;
}

.note {
  font-size: 11.5px;
  color: var(--muted);
  align-self: center;
}

.err-list {
  margin: 0;
  padding: 11px 14px 11px 30px;
  font-size: 12px;
  color: #a15c00;
  line-height: 1.7;
}

.err-list li {
  list-style: disc;
}

/* ---- composer ---- */
.composer {
  padding: 12px 20px 18px;
  background: linear-gradient(180deg, rgba(245, 246, 248, 0), var(--bg) 40%);
}

.composer-inner {
  max-width: 820px;
  margin: 0 auto;
}

.box {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-2);
  transition: 0.18s;
}

.box:focus-within {
  border-color: var(--brand-500);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.15), var(--shadow-2);
}

.box textarea {
  width: 100%;
  border: 0;
  outline: 0;
  resize: none;
  padding: 13px 15px 4px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text);
  background: transparent;
  max-height: 150px;
}

.box textarea::placeholder {
  color: var(--muted);
}

.box-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 11px 10px;
}

.mini {
  border: 1px solid var(--border);
  background: var(--surface-2);
  border-radius: 8px;
  padding: 5px 10px;
  font-size: 11.5px;
  color: var(--text-2);
  display: flex;
  align-items: center;
  gap: 6px;
  transition: 0.15s;
}

.mini:hover {
  background: #fff;
  border-color: var(--border-strong);
}

.mini svg {
  width: 14px;
  height: 14px;
}

.send {
  margin-left: auto;
  border: 0;
  background: var(--brand-600);
  color: #fff;
  border-radius: 9px;
  padding: 8px 16px;
  font-size: 12.5px;
  font-weight: 650;
  display: flex;
  align-items: center;
  gap: 7px;
  transition: 0.15s;
}

.send:hover {
  background: #0b8276;
}

.send:disabled {
  background: #c7cfda;
  cursor: not-allowed;
}

.send svg {
  width: 15px;
  height: 15px;
}

.legal {
  text-align: center;
  font-size: 10.5px;
  color: var(--muted);
  margin-top: 9px;
}

/* ---- 上下文面板 ---- */
.ctx {
  border-left: 1px solid var(--border);
  background: var(--surface);
  overflow-y: auto;
  padding: 16px 15px;
}

.ctx h4 {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  color: var(--muted);
}

.ctx .group {
  margin-bottom: 20px;
}

.cap {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 7px;
  background: var(--surface-2);
  transition: 0.15s;
  width: 100%;
  text-align: left;
}

.cap:hover {
  border-color: var(--brand-500);
  background: var(--brand-050);
}

.cap .ico {
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: #fff;
  border: 1px solid var(--border);
  display: grid;
  place-items: center;
  flex: none;
  color: var(--brand-600);
}

.cap .ico svg {
  width: 14px;
  height: 14px;
}

.cap-body {
  min-width: 0;
}

.cap-body b {
  font-size: 12px;
  display: block;
}

.cap-body span {
  font-size: 10.5px;
  color: var(--muted);
  display: block;
  line-height: 1.5;
}

.kv {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}

.kv:last-child {
  border-bottom: 0;
}

.kv span {
  color: var(--muted);
}

.kv b {
  font-weight: 600;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.3;
  }
  40% {
    opacity: 1;
  }
}

/* ---- 窄屏适配 ---- */
@media (max-width: 1180px) {
  .agent {
    grid-template-columns: 200px 1fr;
  }

  .ctx {
    display: none;
  }
}

@media (max-width: 900px) {
  .agent {
    grid-template-columns: 1fr;
  }

  .conv-list {
    display: none;
  }
}
</style>