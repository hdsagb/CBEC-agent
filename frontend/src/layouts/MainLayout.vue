<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">跨境电商智能 Agent</div>
      <el-menu mode="horizontal" :default-active="route.path" router class="nav" :ellipsis="false">
        <el-menu-item index="/dashboard">工作台</el-menu-item>
        <el-menu-item index="/elements">申报要素库</el-menu-item>
        <el-menu-item index="/quotes">智能比价</el-menu-item>
        <el-menu-item index="/marks">箱唛生成</el-menu-item>
        <el-menu-item v-if="isAdmin" index="/admin">管理</el-menu-item>
      </el-menu>
      <div class="user-area">
        <span class="user-name">{{ auth.user?.display_name || auth.user?.username }}</span>
        <el-button link type="danger" @click="handleLogout">退出</el-button>
      </div>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isAdmin = computed(() => auth.user?.role === 'admin')

function handleLogout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.layout {
  height: 100%;
}
.header {
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}
.brand {
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
}
.nav {
  flex: 1;
  border-bottom: none;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}
.main {
  background: #f5f7fa;
}
</style>
