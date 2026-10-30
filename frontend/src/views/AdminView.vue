<template>
  <div class="page">
    <div class="page-inner">
      <div class="page-head">
        <div>
          <h1>管理</h1>
          <p>用户与角色、系统参数设置（仅管理员可见）。</p>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>成员与角色</b>
          <span class="hint">用户管理接口待接入</span>
        </div>
        <div class="panel-bd">
          <div class="empty">
            <svg viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="3.4" stroke="currentColor" stroke-width="1.6" />
              <path d="M5 20c0-3.3 3.1-5.4 7-5.4S19 16.7 19 20" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <span>暂无法展示成员列表</span>
            <span>后端暂未提供用户查询与角色分配接口，接入后将在此展示成员与角色信息。</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>大模型配置</b>
          <span class="hint">全局共用一套配置，保存后立即对新对话生效</span>
        </div>
        <div class="panel-bd">
          <div class="llm">
            <div class="llm-main">
              <span class="llm-dot" :class="llmDotClass" />
              <div class="llm-text">
                <b>{{ llmConfig?.model || '未配置模型' }}</b>
                <span>
                  {{ llmStatusText }}
                  <template v-if="llmConfig?.base_url">· {{ llmConfig.base_url }}</template>
                </span>
              </div>
            </div>
            <span v-if="llmConfig" class="pill" :class="llmPillClass">{{ llmStatusText }}</span>
            <el-button type="primary" plain size="small" @click="openLLMDialog">配置</el-button>
          </div>
          <div v-if="llmConfig && llmConfig.status !== 'ok' && llmConfig.status_message" class="llm-msg">
            {{ llmConfig.status_message }}
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-hd">
          <b>系统设置</b>
          <span class="hint">配置接口待接入，暂不可修改</span>
        </div>
        <div class="panel-bd settings">
          <div v-for="item in settings" :key="item.title" class="setting">
            <div class="setting-text">
              <b>{{ item.title }}</b>
              <span>{{ item.desc }}</span>
            </div>
            <span class="pill muted">待接入</span>
            <button class="switch" :class="{ on: item.on }" type="button" disabled aria-label="待接入" />
          </div>
        </div>
      </div>
    </div>

    <LLMModelDialog v-model="modelDialogVisible" :config="llmConfig" @saved="handleLLMSaved" />
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { fetchLLMConfig, llmStatusLabel, type LLMConfig } from '@/api/settings'
import LLMModelDialog from '@/components/LLMModelDialog.vue'

const settings = [
  {
    title: '报价解析启用 LLM 增强',
    desc: '关闭后仅使用表头规则解析，适合无 API Key 环境',
    on: true,
  },
  {
    title: '比价结果自动推荐最优供应商',
    desc: '在批次完成后自动计算并标记',
    on: true,
  },
  {
    title: '箱唛导出水印',
    desc: '导出 PDF 时附加内部编号水印',
    on: false,
  },
]

const llmConfig = ref<LLMConfig | null>(null)
const modelDialogVisible = ref(false)

const llmStatusText = computed(() => llmStatusLabel(llmConfig.value?.status))
const llmDotClass = computed(() => {
  const status = llmConfig.value?.status ?? 'unconfigured'
  if (status === 'ok') return 'ok'
  if (status === 'unconfigured') return 'idle'
  if (status === 'unknown') return 'warn'
  return 'bad'
})
const llmPillClass = computed(() => (llmConfig.value?.status === 'ok' ? 'best' : 'warn'))

async function loadLLMConfig() {
  try {
    llmConfig.value = await fetchLLMConfig()
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载大模型配置失败'))
  }
}

function openLLMDialog() {
  modelDialogVisible.value = true
}

function handleLLMSaved(config: LLMConfig) {
  llmConfig.value = config
}

function errorMessage(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

onMounted(() => {
  void loadLLMConfig()
})
</script>

<style scoped>
.llm {
  display: flex;
  align-items: center;
  gap: 14px;
}

.llm-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.llm-text {
  min-width: 0;
}

.llm-text b {
  font-size: 12.5px;
}

.llm-text span {
  display: block;
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.llm-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex: none;
  background: var(--brand-500);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.18);
}

.llm-dot.idle {
  background: #9ca3af;
  box-shadow: 0 0 0 3px rgba(156, 163, 175, 0.16);
}

.llm-dot.warn {
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.16);
}

.llm-dot.bad {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.16);
}

.llm-msg {
  margin-top: 10px;
  font-size: 11.5px;
  color: #a15c00;
}

.settings {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.setting {
  display: flex;
  align-items: center;
  gap: 14px;
}

.setting-text {
  flex: 1;
}

.setting-text b {
  font-size: 12.5px;
}

.setting-text span {
  display: block;
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 2px;
}
</style>