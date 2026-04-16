<template>
  <svg 
    viewBox="0 0 24 24" 
    class="w-6 h-6 transition-colors duration-300"
    :class="signalLevel <= 2 ? 'text-red-500 animate-pulse' : 'text-green-400'"
  >
    <rect 
      x="1" y="18" width="3" height="4" rx="1"
      :fill="signalLevel >= 1 ? 'currentColor' : '#374151'" 
    />
    <rect 
      x="6" y="14" width="3" height="8" rx="1"
      :fill="signalLevel >= 2 ? 'currentColor' : '#374151'" 
    />
    <rect 
      x="11" y="10" width="3" height="12" rx="1"
      :fill="signalLevel >= 3 ? 'currentColor' : '#374151'" 
    />
    <rect 
      x="16" y="6" width="3" height="16" rx="1"
      :fill="signalLevel >= 4 ? 'currentColor' : '#374151'" 
    />
    <rect 
      x="21" y="2" width="3" height="20" rx="1"
      :fill="signalLevel >= 5 ? 'currentColor' : '#374151'" 
    />
  </svg>
</template>

<script setup>
// 接收父组件传来的图传信号质量 (1-5)
defineProps({
  signalLevel: {
    type: Number,
    default: 5
  }
})
</script>
