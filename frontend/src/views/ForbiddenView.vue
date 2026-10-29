<template>
  <div class="page">
    <div class="page-inner forbidden">
      <el-result icon="warning" title="403 · 权限不足" :sub-title="subtitle">
        <template #extra>
          <el-button type="primary" @click="goHome">返回工作台</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const subtitle = computed(() => {
  const from = route.query.from
  return from
    ? `当前账号无权访问「${from}」，请联系管理员调整角色后重试。`
    : '当前账号无权访问该页面，请联系管理员调整角色后重试。'
})

function goHome() {
  router.replace({ name: 'agent' })
}
</script>

<style scoped>
.forbidden {
  display: grid;
  place-items: center;
  min-height: 60vh;
}
</style>
