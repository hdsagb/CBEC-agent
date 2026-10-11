<template>
  <div class="page">
    <div class="page-inner">
      <div class="page-head">
        <div>
          <h1>工作台</h1>
          <p>今天是 {{ todayText }}，{{ summaryText }}</p>
        </div>
        <div class="actions">
          <button class="btn" type="button" :disabled="loading" @click="load">刷新</button>
          <button class="btn primary" type="button" @click="router.push({ name: 'agent' })">向 Agent 提问</button>
        </div>
      </div>

      <div class="grid-kpi">
        <div class="kpi">
          <div class="lbl">进行中比价批次</div>
          <div class="val">{{ fmt(activeBatchCount) }}</div>
          <div class="delta mut">状态非「已比价」的批次</div>
        </div>
        <div class="kpi">
          <div class="lbl">待确认报价明细</div>
          <div class="val">—</div>
          <div class="delta down">需按批次在智能比价页核对</div>
        </div>
        <div class="kpi">
          <div class="lbl">申报要素库记录</div>
          <div class="val">{{ fmt(elementTotal) }}</div>
          <div class="delta">客户 + 产品维度沉淀</div>
        </div>
        <div class="kpi">
          <div class="lbl">箱唛任务</div>
          <div class="val">{{ fmt(markJobCount) }}</div>
          <div class="delta">累计创建任务数</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>快捷入口</b>
        </div>
        <div class="panel-bd">
          <div class="quick">
            <button v-for="q in quickLinks" :key="q.name" class="quick-item" type="button" @click="router.push({ name: q.name })">
              <b>{{ q.title }}</b>
              <span>{{ q.desc }}</span>
            </button>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>最近动态</b>
          <span class="hint">动态流接口待接入</span>
        </div>
        <div class="panel-bd">
          <div class="empty">
            <svg viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" />
              <path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <span>暂无可展示的动态数据</span>
            <span>后端暂未提供动态流接口，接入后将在此展示比价、要素更新与箱唛导出记录。</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchElements } from '@/api/elements'
import { fetchMarkJobs } from '@/api/marks'
import { fetchQuoteBatches } from '@/api/quotes'

const router = useRouter()

const loading = ref(false)
const elementTotal = ref<number | null>(null)
const activeBatchCount = ref<number | null>(null)
const markJobCount = ref<number | null>(null)

const todayText = computed(() => {
  const now = new Date()
  return `${now.getMonth() + 1} 月 ${now.getDate()} 日`
})

const summaryText = computed(() => {
  if (loading.value) return '正在汇总最新数据…'
  if (elementTotal.value === null && activeBatchCount.value === null && markJobCount.value === null) {
    return '暂未获取到业务数据。'
  }
  return `当前有 ${activeBatchCount.value ?? 0} 个比价批次进行中，要素库累计 ${elementTotal.value ?? 0} 条记录。`
})

const quickLinks = [
  { name: 'agent', title: 'Agent 对话', desc: '一句话调度要素检索、比价与箱唛任务' },
  { name: 'quotes', title: '智能比价', desc: '上传报价单 → 解析确认 → 四维加权比价' },
  { name: 'elements', title: '申报要素库', desc: '检索复用报关要素，一键复制报关文本' },
  { name: 'marks', title: '箱唛生成', desc: '模板化管理箱唛并导出任务' },
]

function fmt(value: number | null): string {
  return value === null ? '—' : value.toLocaleString()
}

async function load() {
  loading.value = true
  const [elements, batches, jobs] = await Promise.allSettled([
    fetchElements({ page: 1, page_size: 1 }),
    fetchQuoteBatches(),
    fetchMarkJobs(),
  ])

  elementTotal.value = elements.status === 'fulfilled' ? elements.value.total : null
  activeBatchCount.value =
    batches.status === 'fulfilled' ? batches.value.filter((b) => b.status !== 'compared').length : null
  markJobCount.value = jobs.status === 'fulfilled' ? jobs.value.length : null
  loading.value = false
}

onMounted(load)
</script>

<style scoped>
.quick {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.quick-item {
  border: 1px solid var(--border);
  background: var(--surface-2);
  border-radius: var(--radius);
  padding: 12px 14px;
  text-align: left;
  transition: 0.15s;
}

.quick-item:hover {
  border-color: var(--brand-500);
  background: var(--brand-050);
}

.quick-item b {
  display: block;
  font-size: 12.5px;
  color: var(--text);
}

.quick-item span {
  display: block;
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.55;
}
</style>