<template>
  <div class="page">
    <div class="page-inner">
      <div class="page-head">
        <div>
          <h1>箱唛生成</h1>
          <p>模板化管理箱唛，选择模板与箱号范围后创建导出任务。</p>
        </div>
        <div class="actions">
          <button class="btn" type="button" :disabled="loading" @click="load">刷新</button>
          <button class="btn primary" type="button" @click="openTemplateDialog">新建模板</button>
        </div>
      </div>

      <div v-if="loading" class="empty"><span>加载中…</span></div>

      <div v-else-if="!templates.length" class="panel">
        <div class="panel-bd">
          <div class="empty">
            <svg viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.6" />
              <path d="M3 9h18M7 13h4M7 16h7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <span>暂无箱唛模板</span>
            <span>点击右上角「新建模板」创建第一个模板，之后即可基于模板创建导出任务。</span>
          </div>
        </div>
      </div>

      <template v-else>
        <div class="tpl-grid">
          <button
            v-for="(tpl, idx) in templates"
            :key="tpl.id"
            class="tpl"
            type="button"
            @click="openJobDialog(tpl.id)"
          >
            <img v-if="tpl.thumbnail_url" class="thumb-img" :src="tpl.thumbnail_url" :alt="tpl.name" />
            <div v-else class="thumb">{{ `SHIPPING MARK ${String(idx + 1).padStart(2, '0')}` }}</div>
            <div class="meta">
              <b>{{ tpl.name }}</b>
              <span>{{ layoutPreview(tpl.layout_json) }}</span>
            </div>
          </button>
        </div>
        <p class="grid-tip">点击模板卡片可直接基于该模板创建箱唛任务。</p>
      </template>

      <div class="panel" style="margin-top: 18px">
        <div class="panel-hd">
          <b>最近任务</b>
          <span class="hint">{{ jobs.length }} 条</span>
        </div>
        <table v-if="jobs.length">
          <thead>
            <tr>
              <th>订单号</th>
              <th>模板</th>
              <th class="num">箱数</th>
              <th>箱号范围</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id">
              <td>{{ job.order_no || `#${job.id}` }}</td>
              <td>{{ templateName(job.template_id) }}</td>
              <td class="num">{{ job.total_boxes }}</td>
              <td>{{ job.start_no }} – {{ job.start_no + job.total_boxes - 1 }}</td>
              <td>
                <button class="pill muted action" type="button" @click="handleExport(job.id, 'pdf')">导出 PDF</button>
                <button class="pill muted action" type="button" @click="handleExport(job.id, 'png')">导出 PNG</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">
          <svg viewBox="0 0 24 24" fill="none">
            <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.6" />
            <path d="M3 9h18" stroke="currentColor" stroke-width="1.6" />
          </svg>
          <span>暂无箱唛任务</span>
        </div>
      </div>
    </div>

    <!-- 新建模板 -->
    <el-dialog v-model="templateDialogVisible" title="新建箱唛模板" width="520px">
      <el-form @submit.prevent>
        <el-form-item label="模板名称">
          <el-input v-model="templateForm.name" placeholder="如 标准出口唛" @keyup.enter="submitTemplate" />
        </el-form-item>
        <el-form-item label="版式定义">
          <el-input
            v-model="templateForm.layout_json"
            type="textarea"
            :rows="6"
            placeholder='JSON 版式，如 {"rows":["品名","箱号","重量"]}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingTemplate" @click="submitTemplate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新建任务 -->
    <el-dialog v-model="jobDialogVisible" title="新建箱唛任务" width="520px">
      <el-form @submit.prevent>
        <el-form-item label="模板">
          <el-select v-model="jobForm.template_id" placeholder="选择模板" style="width: 100%">
            <el-option v-for="tpl in templates" :key="tpl.id" :label="tpl.name" :value="tpl.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="订单号">
          <el-input v-model="jobForm.order_no" placeholder="如 SO-20261010-004" />
        </el-form-item>
        <el-form-item label="总箱数">
          <el-input-number v-model="jobForm.total_boxes" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="起始箱号">
          <el-input-number v-model="jobForm.start_no" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="唛头字段">
          <el-input
            v-model="jobForm.fields_json"
            type="textarea"
            :rows="5"
            placeholder='JSON 字段，如 {"品名":"蓝牙耳机","目的港":"LAX"}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="jobDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingJob" @click="submitJob">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createMarkJob,
  createMarkTemplate,
  exportMarkJob,
  fetchMarkJobs,
  fetchMarkTemplates,
  type MarkJob,
  type MarkTemplate,
} from '@/api/marks'

const loading = ref(false)
const templates = ref<MarkTemplate[]>([])
const jobs = ref<MarkJob[]>([])

const templateDialogVisible = ref(false)
const submittingTemplate = ref(false)
const templateForm = reactive({ name: '', layout_json: '{}' })

const jobDialogVisible = ref(false)
const submittingJob = ref(false)
const jobForm = reactive({
  template_id: 0,
  order_no: '',
  total_boxes: 1,
  start_no: 1,
  fields_json: '{}',
})

const templateNameMap = computed<Record<number, string>>(() => {
  const map: Record<number, string> = {}
  for (const tpl of templates.value) map[tpl.id] = tpl.name
  return map
})

function templateName(templateId: number): string {
  return templateNameMap.value[templateId] ?? `#${templateId}`
}

function layoutPreview(layoutJson: string): string {
  const text = (layoutJson || '').trim()
  if (!text || text === '{}') return '未设置版式'
  return text.length > 40 ? `${text.slice(0, 40)}…` : text
}

function errorMessage(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function load() {
  loading.value = true
  try {
    const [tpls, jobList] = await Promise.all([fetchMarkTemplates(), fetchMarkJobs()])
    templates.value = tpls
    jobs.value = jobList
  } catch (e) {
    ElMessage.error(errorMessage(e, '加载箱唛数据失败'))
  } finally {
    loading.value = false
  }
}

function openTemplateDialog() {
  templateForm.name = ''
  templateForm.layout_json = '{}'
  templateDialogVisible.value = true
}

async function submitTemplate() {
  const name = templateForm.name.trim()
  if (!name) {
    ElMessage.warning('请输入模板名称')
    return
  }
  submittingTemplate.value = true
  try {
    await createMarkTemplate(name, templateForm.layout_json.trim() || '{}')
    templateDialogVisible.value = false
    ElMessage.success('模板已创建')
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '创建模板失败'))
  } finally {
    submittingTemplate.value = false
  }
}

function openJobDialog(templateId: number) {
  jobForm.template_id = templateId
  jobForm.order_no = ''
  jobForm.total_boxes = 1
  jobForm.start_no = 1
  jobForm.fields_json = '{}'
  jobDialogVisible.value = true
}

async function submitJob() {
  if (!jobForm.template_id) {
    ElMessage.warning('请选择模板')
    return
  }
  if (!jobForm.order_no.trim()) {
    ElMessage.warning('请输入订单号')
    return
  }
  submittingJob.value = true
  try {
    await createMarkJob({
      template_id: jobForm.template_id,
      order_no: jobForm.order_no.trim(),
      total_boxes: jobForm.total_boxes,
      start_no: jobForm.start_no,
      fields_json: jobForm.fields_json.trim() || '{}',
    })
    jobDialogVisible.value = false
    ElMessage.success('箱唛任务已创建')
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '创建任务失败'))
  } finally {
    submittingJob.value = false
  }
}

async function handleExport(jobId: number, format: 'pdf' | 'png') {
  try {
    const res = await exportMarkJob(jobId, format)
    if (res.url) {
      // 导出接口是异步 await 之后才拿到 url，用 a 标签触发避免被当作弹窗拦截
      const link = document.createElement('a')
      link.href = res.url
      link.target = '_blank'
      link.rel = 'noopener'
      link.click()
      ElMessage.success(res.message || '导出完成')
    } else {
      ElMessage.info(res.message || '导出失败')
    }
  } catch (e) {
    ElMessage.error(errorMessage(e, '导出失败'))
  }
}

onMounted(load)
</script>

<style scoped>
.tpl {
  padding: 0;
}

.thumb-img {
  width: 100%;
  height: 112px;
  object-fit: cover;
  display: block;
}

.grid-tip {
  margin: 10px 0 0;
  font-size: 11.5px;
  color: var(--muted);
}

.action {
  border: 1px solid var(--border);
  margin-right: 6px;
  transition: 0.15s;
}

.action:hover {
  border-color: var(--brand-500);
  color: var(--brand-600);
}
</style>