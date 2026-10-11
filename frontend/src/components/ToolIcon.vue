<template>
  <svg :viewBox="'0 0 24 24'" fill="none" aria-hidden="true">
    <template v-if="name === 'compare_quotes'">
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else-if="name === 'search_elements'">
      <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="1.8" />
      <path d="M20 20l-3.2-3.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else-if="name === 'create_marks'">
      <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.8" />
      <path d="M3 9h18M7 13h4M7 16h7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else>
      <path d="M12 3l2.2 5.1L20 9.3l-4 3.7L17 19l-5-2.8L7 19l1-6-4-3.7 5.8-1.2L12 3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
    </template>
  </svg>
</template>

<script setup lang="ts">
defineProps<{ name: string }>()
</script>