<template>
  <el-dialog
    v-model="visible"
    title="大模型配置"
    width="560px"
    align-center
    :close-on-click-modal="false"
    :show-close="canEdit"
    class="llm-dialog"
  >
    <div class="head">
      <span class="status" :class="dotClass">
        <span class="dot" />
        {{ statusText }}
      </span>
      <span class="hint" v-if="config?.status_message">{{ config.status_message }}</span>
    </div>

    <el-form label-position="top" class="form" @submit.prevent>
      <el-form-item label="提供方">
        <el-select v-model="form.provider" :disabled="!canEdit" class="w-full">
          <el-option v-for="p in PROVIDERS" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
      </el-form-item>

      <el-form-item label="接口地址（OpenAI 兼容）">
        <el-input
          v-model="form.base_url"
          :disabled="!canEdit"
          placeholder="https://api.example.com/v1"
          spellcheck="false"
        />
      </el-form-item>

      <el-form-item label="模型名称">
        <el-input v-model="form.model" :disabled="!canEdit" placeholder="例如 deepseek-chat" />
      </el-form-item>

      <el-form-item label="API Key">
        <div class="key-row">
          <el-input
            v-model="form.api_key"
            :disabled="!canEdit || form.clearApiKey"
            type="password"
            autocomplete="new-password"
            :placeholder="keyPlaceholder"
          />
          <el-button
            v-if="canEdit && config?.api_key_configured"
            link
            type="danger"
            @click="toggleClear('api')"
          >
            {{ form.clearApiKey ? '取消清除' : '清除' }}
          </el-button>
        </div>
      </el-form-item>

      <el-collapse class="vision">
        <el-collapse-item title="图片识别（可选，多模态模型）" name="vision">
          <el-form-item label="视觉模型名称">
            <el-input
              v-model="form.vision_model"
              :disabled="!canEdit"
              placeholder="留空则使用本地 OCR 兜底"
            />
          </el-form-item>
          <el-form-item label="视觉模型接口地址">
            <el-input
              v-model="form.vision_base_url"
              :disabled="!canEdit"
              placeholder="留空时复用上面的接口地址"
            />
          </el-form-item>
          <el-form-item label="视觉模型 API Key">
            <div class="key-row">
              <el-input
                v-model="form.vision_api_key"
                :disabled="!canEdit || form.clearVisionKey"
                type="password"
                autocomplete="new-password"
                :placeholder="visionKeyPlaceholder"
              />
              <el-button
                v-if="canEdit && config?.vision_api_key_configured"
                link
                type="danger"
                @click="toggleClear('vision')"
              >
                {{ form.clearVisionKey ? '取消清除' : '清除' }}
              </el-button>
            </div>
          </el-form-item>
        </el-collapse-item>
      </el-collapse>
    </el-form>

    <div class="foot">
      <span class="source" v-if="config">
        {{ config.source === 'db' ? '当前使用页面保存的配置' : '当前使用环境变量兜底配置' }}
      </span>
      <div class="acts">
        <el-button v-if="canEdit" :loading="testing" @click="handleTest">测试连接</el-button>
        <el-button v-if="canEdit" @click="visible = false">取消</el-button>
        <el-button v-else @click="visible = false">关闭</el-button>
        <el-button v-if="canEdit" type="primary" :loading="saving" @click="handleSave">
          保存并切换
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

import { llmStatusLabel, saveLLMConfig, testLLMConfig, type LLMConfig } from '@/api/settings'

const props = defineProps<{ modelValue: boolean; config: LLMConfig | null }>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved', config: LLMConfig): void
}>()

const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
  { value: 'openai', label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { value: 'moonshot', label: 'Moonshot', base_url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { value: 'zhipu', label: '智谱 GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  {
    value: 'dashscope',
    label: '通义千问',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
  },
  { value: 'custom', label: '自定义（OpenAI 兼容）', base_url: '', model: '' },
]

const form = reactive({
  provider: 'deepseek',
  base_url: '',
  model: '',
  api_key: '',
  vision_model: '',
  vision_base_url: '',
  vision_api_key: '',
  clearApiKey: false,
  clearVisionKey: false,
})

const saving = ref(false)
const testing = ref(false)

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const canEdit = computed(() => props.config?.can_edit !== false)
const statusText = computed(() => llmStatusLabel(props.config?.status))
const dotClass = computed(() => {
  const status = props.config?.status ?? 'unconfigured'
  if (status === 'ok') return 'ok'
  if (status === 'unconfigured') return 'idle'
  if (status === 'unknown') return 'warn'
  return 'bad'
})

const keyPlaceholder = computed(() =>
  props.config?.api_key_configured
    ? `已配置（${props.config.api_key_masked}），留空保持不变`
    : '粘贴 API Key，输入时以 * 显示',
)
const visionKeyPlaceholder = computed(() =>
  props.config?.vision_api_key_configured
    ? `已配置（${props.config.vision_api_key_masked}），留空保持不变`
    : '留空时复用主模型 Key',
)

watch(
  () => props.modelValue,
  (open) => {
    if (open) syncFromConfig()
  },
)

watch(
  () => form.provider,
  (next, prev) => {
    const target = PROVIDERS.find((p) => p.value === next)
    const source = PROVIDERS.find((p) => p.value === prev)
    if (!target) return
    if (!form.base_url || form.base_url === source?.base_url) form.base_url = target.base_url
    if (!form.model || form.model === source?.model) form.model = target.model
  },
)

function syncFromConfig() {
  const config = props.config
  form.provider = config?.provider || 'deepseek'
  form.base_url = config?.base_url || ''
  form.model = config?.model || ''
  form.api_key = ''
  form.vision_model = config?.vision_model || ''
  form.vision_base_url = config?.vision_base_url || ''
  form.vision_api_key = ''
  form.clearApiKey = false
  form.clearVisionKey = false
}

function toggleClear(kind: 'api' | 'vision') {
  if (kind === 'api') {
    form.clearApiKey = !form.clearApiKey
    if (form.clearApiKey) form.api_key = ''
  } else {
    form.clearVisionKey = !form.clearVisionKey
    if (form.clearVisionKey) form.vision_api_key = ''
  }
}

function validate(): string | null {
  if (!form.base_url.trim()) return '请填写接口地址'
  if (!form.model.trim()) return '请填写模型名称'
  if (form.vision_model.trim() && !form.vision_base_url.trim()) return '填写视觉模型时需要提供接口地址'
  if (!form.clearApiKey && !form.api_key.trim() && !props.config?.api_key_configured) {
    return '请填写 API Key'
  }
  return null
}

async function handleSave() {
  const error = validate()
  if (error) {
    ElMessage.warning(error)
    return
  }
  saving.value = true
  try {
    const payload = {
      provider: form.provider,
      base_url: form.base_url.trim(),
      model: form.model.trim(),
      vision_model: form.vision_model.trim(),
      vision_base_url: form.vision_base_url.trim(),
    } as Parameters<typeof saveLLMConfig>[0]
    if (form.clearApiKey) payload.api_key = ''
    else if (form.api_key.trim()) payload.api_key = form.api_key.trim()
    if (form.clearVisionKey) payload.vision_api_key = ''
    else if (form.vision_api_key.trim()) payload.vision_api_key = form.vision_api_key.trim()

    const saved = await saveLLMConfig(payload)
    emit('saved', saved)
    visible.value = false
    ElMessage.success('已保存，新的模型配置立即生效')
  } catch (e) {
    ElMessage.error(errorMessage(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  try {
    const result = await testLLMConfig()
    emit('saved', result.config)
    const type = result.status === 'ok' ? 'success' : 'warning'
    ElMessage({ type, message: `${result.message}（${result.latency_ms} ms）`, duration: 3500 })
  } catch (e) {
    ElMessage.error(errorMessage(e, '测试连接失败'))
  } finally {
    testing.value = false
  }
}

function errorMessage(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
</script>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: -6px 0 14px;
}

.head .hint {
  font-size: 11.5px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--text-2);
  border: 1px solid var(--border);
  background: var(--surface-2);
  border-radius: var(--radius-pill);
  padding: 3px 10px;
  white-space: nowrap;
}

.status .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #9ca3af;
}

.status.ok .dot {
  background: var(--brand-500);
}

.status.warn .dot {
  background: #f59e0b;
}

.status.bad .dot {
  background: #ef4444;
}

.form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.w-full {
  width: 100%;
}

.key-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.vision {
  border-top: 1px solid var(--border);
  margin-top: 4px;
}

.foot {
  display: flex;
  align-items: center;
  gap: 12px;
  border-top: 1px solid var(--border);
  padding-top: 14px;
  margin-top: 6px;
}

.foot .source {
  font-size: 11.5px;
  color: var(--muted);
}

.foot .acts {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
</style>
