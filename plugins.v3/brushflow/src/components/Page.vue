<script setup>
import BrushFlowV9 from './BrushFlowV9.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
})

defineEmits(['action', 'close'])
</script>

<template>
  <BrushFlowV9
    :api="api"
    plugin-id="BrushFlow"
    show-close
    compact
    @action="$emit('action')"
    @close="$emit('close')"
  />
</template>
