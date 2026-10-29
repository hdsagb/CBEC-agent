<template>
  <div class="app">
    <!-- ================= 顶栏 ================= -->
    <header class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M4 17V7l8-3 8 3v10" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" />
            <path d="M8 12h8M8 15h5" stroke="#fff" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </div>
        <div class="brand-text">
          <div class="name">CBEC Agent</div>
          <div class="sub">跨境电商智能助理</div>
        </div>
      </div>

      <form class="global-search" @submit.prevent="handleSearch">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
          <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="1.8" />
          <path d="M20 20l-3.2-3.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
        </svg>
        <input v-model="keyword" aria-label="全局搜索" placeholder="搜索商品、客户、HS 编码或直接向 Agent 提问…" />
        <kbd>Ctrl K</kbd>
      </form>

      <div class="top-actions">
        <button class="icon-btn" type="button" aria-label="通知" @click="notifyEmpty">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
            <path d="M10 19a2 2 0 0 0 4 0" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
        </button>
        <el-popover placement="bottom-end" :width="200" trigger="click">
          <template #reference>
            <button class="avatar" type="button">
              <span class="pic">{{ initials }}</span>
              <span class="who">
                <b>{{ displayName }}</b>
                <span>{{ roleLabel }}</span>
              </span>
            </button>
          </template>
          <div class="user-menu">
            <div class="user-menu-head">
              <b>{{ displayName }}</b>
              <span>{{ auth.user?.username }}</span>
            </div>
            <button class="user-menu-item danger" type="button" @click="handleLogout">退出登录</button>
          </div>
        </el-popover>
      </div>
    </header>

    <!-- ================= 左侧导航 ================= -->
    <aside class="rail" role="navigation" aria-label="主导航">
      <div class="rail-label">智能助理</div>
      <RouterLink v-if="allow('agent.use')" :to="{ name: 'agent' }" class="nav-item" active-class="is-active">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 3l2.2 5.1L20 9.3l-4 3.7L17 19l-5-2.8L7 19l1-6-4-3.7 5.8-1.2L12 3Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
        </svg>
        <span class="txt">Agent 对话</span><span class="tag">核心</span>
      </RouterLink>

      <div class="rail-label">业务工作台</div>
      <RouterLink v-if="allow('dashboard.view')" :to="{ name: 'dashboard' }" class="nav-item" active-class="is-active">
        <svg viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="8" height="8" rx="2" stroke="currentColor" stroke-width="1.7" />
          <rect x="13" y="3" width="8" height="5" rx="2" stroke="currentColor" stroke-width="1.7" />
          <rect x="13" y="10" width="8" height="11" rx="2" stroke="currentColor" stroke-width="1.7" />
          <rect x="3" y="13" width="8" height="8" rx="2" stroke="currentColor" stroke-width="1.7" />
        </svg>
        <span class="txt">工作台</span>
      </RouterLink>
      <RouterLink v-if="allow('elements.read')" :to="{ name: 'elements' }" class="nav-item" active-class="is-active">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M5 4h11l3 3v13H5V4Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
          <path d="M8 9h7M8 13h7M8 17h4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        </svg>
        <span class="txt">申报要素库</span>
      </RouterLink>
      <RouterLink v-if="allow('quotes.use')" :to="{ name: 'quotes' }" class="nav-item" active-class="is-active">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        </svg>
        <span class="txt">智能比价</span>
      </RouterLink>
      <RouterLink v-if="allow('suppliers.read')" :to="{ name: 'suppliers' }" class="nav-item" active-class="is-active">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M3 17V7h11v10" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
          <path d="M14 10h4l3 3v4h-7" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
          <circle cx="7" cy="18" r="1.8" stroke="currentColor" stroke-width="1.7" />
          <circle cx="17" cy="18" r="1.8" stroke="currentColor" stroke-width="1.7" />
        </svg>
        <span class="txt">供应商库</span>
      </RouterLink>
      <RouterLink v-if="allow('marks.use')" :to="{ name: 'marks' }" class="nav-item" active-class="is-active">
        <svg viewBox="0 0 24 24" fill="none">
          <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.7" />
          <path d="M3 9h18M7 13h4M7 16h7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        </svg>
        <span class="txt">箱唛生成</span>
      </RouterLink>
      <RouterLink v-if="allow('reports.read')" :to="{ name: 'reports' }" class="nav-item" active-class="is-active">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M3 21h18" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          <path d="M6 21V11l5-3.4V21" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
          <path d="M13 21V4l5 3.4V21" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
        </svg>
        <span class="txt">数据分析</span>
      </RouterLink>

      <template v-if="allow('admin.access')">
        <div class="rail-label">系统</div>
        <RouterLink :to="{ name: 'admin' }" class="nav-item" active-class="is-active">
          <svg viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="8" r="3.4" stroke="currentColor" stroke-width="1.7" />
            <path d="M5 20c0-3.3 3.1-5.4 7-5.4S19 16.7 19 20" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          <span class="txt">管理</span>
        </RouterLink>
      </template>

      <div class="rail-foot">
        <div class="rail-card">
          <b>已接入 3 个业务工具</b>
          <p>申报要素检索、多供应商比价、箱唛任务，均可通过 Agent 一句话调用。</p>
        </div>
      </div>
    </aside>

    <!-- ================= 主区 ================= -->
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { can, permissionForRoute, roleLabel as toRoleLabel, type Permission } from '@/permissions'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const keyword = ref('')

function allow(permission: Permission): boolean {
  return can(auth.user?.role, permission)
}

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '未登录')
const roleLabel = computed(() => toRoleLabel(auth.user?.role))
const initials = computed(() => {
  const name = auth.user?.display_name || auth.user?.username || ''
  return name ? name.slice(0, 2).toUpperCase() : 'U'
})

function handleSearch() {
  const text = keyword.value.trim()
  if (!text) return
  keyword.value = ''
  router.push({ name: 'elements', query: { keyword: text } })
}

function notifyEmpty() {
  ElMessage.info('暂无新通知')
}

function handleLogout() {
  auth.logout()
  router.push({ name: 'login' })
}

onMounted(() => {
  // 以服务端角色为准刷新一次；角色被调整后菜单会立即按新权限重算
  void auth.refreshMe()
})

watch(
  () => auth.user?.role,
  (role) => {
    const permission = permissionForRoute(router.currentRoute.value.name)
    if (permission && !can(role, permission)) {
      router.replace({ name: 'forbidden' })
    }
  },
)
</script>

<style scoped>
.app {
  display: grid;
  height: 100vh;
  overflow: hidden;
  grid-template-columns: var(--rail-w) 1fr;
  grid-template-rows: 58px 1fr;
  grid-template-areas: 'top top' 'rail main';
}

/* ---- 顶栏 ---- */
.topbar {
  grid-area: top;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 18px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  z-index: 20;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: calc(var(--rail-w) - 18px);
}

.brand .mark {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  flex: none;
  background: linear-gradient(145deg, var(--brand-500), var(--brand-600));
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.34);
}

.brand .mark svg {
  width: 18px;
  height: 18px;
}

.brand .name {
  font-weight: 700;
  letter-spacing: 0.2px;
  font-size: 15px;
}

.brand .sub {
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 0.5px;
}

.global-search {
  flex: 1;
  max-width: 420px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 7px 14px;
  color: var(--muted);
}

.global-search input {
  border: 0;
  background: transparent;
  outline: 0;
  width: 100%;
  font-size: 13.5px;
  color: var(--text);
}

.global-search kbd {
  font: 11px/1 var(--mono);
  color: var(--muted);
  background: #fff;
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 5px;
  padding: 3px 6px;
  white-space: nowrap;
}

.top-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: #fff;
  display: grid;
  place-items: center;
  color: var(--text-2);
  transition: 0.15s;
}

.icon-btn:hover {
  background: var(--surface-2);
  border-color: var(--border-strong);
  color: var(--text);
}

.icon-btn svg {
  width: 17px;
  height: 17px;
}

.avatar {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 5px 10px 5px 5px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border);
  background: #fff;
}

.avatar .pic {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex: none;
  background: var(--ink-800);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.3px;
}

.avatar .who {
  line-height: 1.15;
  text-align: left;
}

.avatar .who b {
  font-size: 12.5px;
  font-weight: 600;
  display: block;
}

.avatar .who span {
  font-size: 10.5px;
  color: var(--muted);
}

.user-menu-head {
  padding: 2px 4px 10px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
}

.user-menu-head b {
  display: block;
  font-size: 13px;
}

.user-menu-head span {
  font-size: 11.5px;
  color: var(--muted);
}

.user-menu-item {
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 8px 6px;
  border-radius: 7px;
  font-size: 12.5px;
  color: var(--text-2);
}

.user-menu-item:hover {
  background: var(--surface-2);
}

.user-menu-item.danger {
  color: #b42318;
}

/* ---- 左侧导航 ---- */
.rail {
  grid-area: rail;
  background: var(--ink-900);
  color: var(--rail-fg);
  display: flex;
  flex-direction: column;
  padding: 14px 12px;
  overflow-y: auto;
}

.rail-label {
  font-size: 10.5px;
  letter-spacing: 1.4px;
  text-transform: uppercase;
  color: #5d6b85;
  margin: 14px 10px 7px;
}

.rail-label:first-child {
  margin-top: 4px;
}

.rail :deep(.nav-item) {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--rail-fg);
  padding: 9px 11px;
  border-radius: 9px;
  font-size: 13.5px;
  text-align: left;
  margin-bottom: 2px;
  transition: 0.15s;
  position: relative;
  text-decoration: none;
}

.rail :deep(.nav-item svg) {
  width: 17px;
  height: 17px;
  flex: none;
}

.rail :deep(.nav-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: var(--rail-fg-strong);
}

.rail :deep(.nav-item.is-active) {
  background: rgba(20, 184, 166, 0.14);
  color: #fff;
  font-weight: 600;
}

.rail :deep(.nav-item.is-active::before) {
  content: '';
  position: absolute;
  left: -12px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  border-radius: 0 3px 3px 0;
  background: var(--brand-400);
}

.rail :deep(.nav-item .txt) {
  white-space: nowrap;
}

.rail :deep(.nav-item .tag) {
  margin-left: auto;
  font-size: 9.5px;
  letter-spacing: 0.6px;
  color: var(--brand-400);
  border: 1px solid rgba(45, 212, 191, 0.35);
  border-radius: var(--radius-pill);
  padding: 2px 7px;
}

.rail-foot {
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.rail-card {
  background: linear-gradient(150deg, rgba(20, 184, 166, 0.16), rgba(124, 108, 240, 0.12));
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius);
  padding: 11px 12px;
}

.rail-card b {
  display: block;
  color: #fff;
  font-size: 12.5px;
  margin-bottom: 3px;
}

.rail-card p {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
  color: #93a2bd;
}

/* ---- 主区 ---- */
.main {
  grid-area: main;
  overflow: hidden;
  position: relative;
}

/* ---- 窄屏适配 ---- */
@media (max-width: 900px) {
  .app {
    grid-template-columns: 68px 1fr;
  }

  .brand {
    min-width: auto;
  }

  .brand-text {
    display: none;
  }

  .rail :deep(.nav-item) {
    justify-content: center;
    padding: 11px 0;
  }

  .rail :deep(.nav-item .txt),
  .rail :deep(.nav-item .tag),
  .rail-label {
    display: none;
  }

  .rail-card {
    display: none;
  }
}

@media (max-width: 640px) {
  .global-search {
    display: none;
  }

  .avatar .who {
    display: none;
  }
}
</style>