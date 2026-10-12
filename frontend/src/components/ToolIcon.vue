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
    <template v-else-if="name === 'export_marks'">
      <path d="M12 3v10m0 0l-3.6-3.6M12 13l3.6-3.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M4 16v2.5A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5V16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else-if="name === 'import_elements'">
      <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.8" />
      <path d="M7 9h5M7 13h3M7 17h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <path d="M17.5 8.5v6m0 0l-2.2-2.2M17.5 14.5l2.2-2.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </template>
    <template v-else-if="name === 'list_quote_batches'">
      <path d="M9 6h11M9 12h11M9 18h11" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <rect x="3.2" y="4.9" width="2.2" height="2.2" rx="0.7" fill="currentColor" />
      <rect x="3.2" y="10.9" width="2.2" height="2.2" rx="0.7" fill="currentColor" />
      <rect x="3.2" y="16.9" width="2.2" height="2.2" rx="0.7" fill="currentColor" />
    </template>
    <template v-else>
      <path d="M12 3l2.2 5.1L20 9.3l-4 3.7L17 19l-5-2.8L7 19l1-6-4-3.7 5.8-1.2L12 3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
    </template>
  </svg>
</template>

<script setup lang="ts">
defineProps<{ name: string }>()
</script>