<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => String(route.meta.title ?? '功能页面'))
</script>

<template>
  <section class="page-view placeholder-view">
    <el-empty :description="`${title}将在后续 Phase 实现`" />
  </section>
</template>
