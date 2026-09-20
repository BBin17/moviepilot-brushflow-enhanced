<script setup>
import { onMounted } from 'vue'
import SmartBrushFlow from './SmartBrushFlow.vue'

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
  <SmartBrushFlow
    :api="api"
    plugin-id="SmartBrushFlow"
    initial-tab="config"
    show-close
    compact
    @close="$emit('close')"
  />
</template>
