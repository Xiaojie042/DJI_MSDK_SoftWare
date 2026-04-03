<script setup>
import { useDroneStore } from '@/stores/droneStore'
import { nextTick, ref, watch } from 'vue'

const store = useDroneStore()
const terminalRef = ref(null)

// Auto-scroll to bottom of the terminal on new logs
watch(() => store.rawStream.length, async () => {
  await nextTick()
  if (terminalRef.value) {
    terminalRef.value.scrollTop = terminalRef.value.scrollHeight
  }
})
</script>

<template>
  <div class="raw-data-terminal glass-panel">
    <div class="terminal-header">
      <div class="console-title">
        <span class="pulse-dot"></span> 实时链路控制台 (最新50条)
      </div>
    </div>
    
    <div class="terminal-body" ref="terminalRef">
      <div v-if="store.rawStream.length === 0" class="no-data">
        [SYS] 等待 TCP 数据帧接入...
      </div>
      <div v-for="frame in store.rawStream" :key="frame.id" class="code-line">
        <span class="time">[{{ frame.time }}]</span> 
        <span class="json">RECV: {{ JSON.stringify(frame.data).substring(0, 150) }}...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.raw-data-terminal {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(59, 130, 246, 0.3);
  box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.5);
  font-family: 'Courier New', Courier, monospace;
}

.terminal-header {
  padding: 8px 15px;
  background: rgba(0, 0, 0, 0.4);
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
}

.console-title {
  font-size: 13px;
  color: #10b981;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background-color: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 10px #10b981;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.3; }
  100% { opacity: 1; }
}

.terminal-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 15px;
  scrollbar-width: thin;
  scrollbar-color: rgba(59, 130, 246, 0.5) transparent;
}

.terminal-body::-webkit-scrollbar {
  width: 6px;
}
.terminal-body::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5);
  border-radius: 3px;
}

.code-line {
  font-size: 12px;
  line-height: 1.4;
  margin-bottom: 4px;
  word-break: break-all;
}

.time {
  color: #8b5cf6;
  margin-right: 8px;
}

.json {
  color: #94a3b8;
}

.no-data {
  color: #64748b;
  font-style: italic;
  font-size: 13px;
}
</style>
