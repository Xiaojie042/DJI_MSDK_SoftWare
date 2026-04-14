<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()
const terminalRef = ref(null)
const isExpanded = ref(false)

const recentFrames = computed(() => store.rawStream.slice(-12))
const latestFrameTime = computed(() => recentFrames.value.at(-1)?.time || '--:--:--')

const toggleConsole = () => {
  isExpanded.value = !isExpanded.value
}

watch(
  () => [store.rawStream.length, isExpanded.value],
  async ([, expanded]) => {
    if (!expanded) {
      return
    }

    await nextTick()

    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight
    }
  }
)
</script>

<template>
  <section class="raw-data-terminal glass-panel" :class="{ expanded: isExpanded }">
    <div class="terminal-header">
      <div class="title-stack">
        <p class="eyebrow">嵌入式界面</p>
        <div class="console-title">
          <span class="pulse-dot"></span>
          <strong>实时链路控制台</strong>
        </div>
      </div>

      <button class="toggle-btn" type="button" @click="toggleConsole">
        {{ isExpanded ? '收起明细' : '展开明细' }}
      </button>
    </div>

    <div class="terminal-summary">
      <div class="summary-chip">
        <span>原始帧缓存</span>
        <strong>{{ store.rawStream.length }}</strong>
      </div>
      <div class="summary-chip">
        <span>最近更新时间</span>
        <strong>{{ latestFrameTime }}</strong>
      </div>
      <div class="summary-chip">
        <span>显示方式</span>
        <strong>{{ isExpanded ? '嵌入展开' : '点击查看' }}</strong>
      </div>
    </div>

    <transition name="console">
      <div v-if="isExpanded" class="terminal-shell">
        <div class="terminal-toolbar">
          <span>最近 12 条原始转发数据</span>
          <span>{{ latestFrameTime }}</span>
        </div>

        <div class="terminal-body" ref="terminalRef">
          <div v-if="recentFrames.length === 0" class="no-data">
            [SYS] 等待 TCP 数据帧接入...
          </div>
          <div v-for="frame in recentFrames" :key="frame.id" class="code-line">
            <span class="time">[{{ frame.time }}]</span>
            <span class="json">{{ JSON.stringify(frame.data).slice(0, 180) }}</span>
          </div>
        </div>
      </div>
    </transition>
  </section>
</template>

<style scoped>
.raw-data-terminal {
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
  padding: 1.05rem;
  border-radius: 22px;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(56, 189, 248, 0.2);
  box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.35);
}

.terminal-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 0.28rem;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  color: rgba(148, 163, 184, 0.8);
  text-transform: uppercase;
}

.console-title {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  color: #f8fafc;
}

.console-title strong {
  font-size: 1.05rem;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background-color: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 10px #10b981;
  animation: pulse 1.5s infinite;
}

.toggle-btn {
  min-width: 108px;
  padding: 0.6rem 0.9rem;
  border-radius: 12px;
  border: 1px solid rgba(56, 189, 248, 0.18);
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd;
  font-size: 0.88rem;
}

.terminal-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}

.summary-chip {
  padding: 0.82rem 0.9rem;
  border-radius: 14px;
  background: rgba(30, 41, 59, 0.58);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.summary-chip span {
  display: block;
  margin-bottom: 0.28rem;
  font-size: 0.75rem;
  color: #94a3b8;
}

.summary-chip strong {
  color: #f8fafc;
  font-size: 0.98rem;
}

.terminal-shell {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(59, 130, 246, 0.18);
  background: rgba(2, 6, 23, 0.78);
  font-family: 'Courier New', Courier, monospace;
}

.terminal-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 0.95rem;
  background: rgba(15, 23, 42, 0.82);
  color: #10b981;
  font-size: 0.8rem;
  border-bottom: 1px solid rgba(59, 130, 246, 0.14);
}

.terminal-body {
  max-height: 240px;
  overflow-y: auto;
  padding: 0.8rem 0.95rem;
}

.code-line {
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 0.45rem;
  word-break: break-all;
}

.time {
  color: #a78bfa;
  margin-right: 8px;
}

.json {
  color: #94a3b8;
}

.no-data {
  color: #64748b;
  font-style: italic;
}

.console-enter-active,
.console-leave-active {
  transition: all 0.22s ease;
}

.console-enter-from,
.console-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.3; }
  100% { opacity: 1; }
}

@media (max-width: 900px) {
  .terminal-summary {
    grid-template-columns: 1fr;
  }

  .terminal-header,
  .terminal-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
