<script setup>
import SmartBrushFlow from './SmartBrushFlow.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'SmartBrushFlow' },
})

defineEmits(['action'])
</script>

<template>
  <SmartBrushFlow :api="api" :plugin-id="pluginId" @action="$emit('action')" />
</template>
