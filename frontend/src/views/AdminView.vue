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
  </div>
</template>

<script setup lang="ts">
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
</script>

<style scoped>
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