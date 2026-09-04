<script setup>
import { onMounted } from 'vue'
import BrushFlowV9 from './BrushFlowV9.vue'

defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['layout', 'close'])

onMounted(() => {
  emit('layout', { maxWidth: '80rem' })
})
</script>

<template>
  <BrushFlowV9
    :api="api"
    plugin-id="BrushFlow"
    initial-tab="config"
    show-close
    compact
    @close="$emit('close')"
  />
</template>
