<script setup>
import BrushFlowV9 from './BrushFlowV9.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'BrushFlow' },
})

defineEmits(['action'])
</script>

<template>
  <BrushFlowV9 :api="api" :plugin-id="pluginId" @action="$emit('action')" />
</template>
