<script setup>
import SmartBrushFlow from './SmartBrushFlow.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
})

defineEmits(['action', 'close'])
</script>

<template>
  <SmartBrushFlow
    :api="api"
    plugin-id="SmartBrushFlow"
    show-close
    compact
    @action="$emit('action')"
    @close="$emit('close')"
  />
</template>
