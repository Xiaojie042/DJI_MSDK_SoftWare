<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()
const terminalRef = ref(null)
const isExpanded = ref(false)

const recentFrames = computed(() => store.rawStream.slice(-12))
const latestFrameTime = computed(() => recentFrames.value.at(-1)?.time || '--:--:--')
const formatFrame = (payload) => JSON.stringify(payload, null, 2)
const formatInlineFrame = (payload) =>
  JSON.stringify(payload ?? {}).replace(/\s+/g, ' ').slice(0, 180) || '{}'

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
  <section class="raw-data-terminal glass-panel">
    <div class="terminal-mini">
      <div class="terminal-mini__copy">
        <p class="eyebrow">嵌入式界面</p>
        <div class="console-title">
          <span class="pulse-dot"></span>
          <strong>实时链路控制台</strong>
        </div>
        <div class="terminal-preview">
          <span class="preview-time">[{{ latestFrameTime }}]</span>
          <code class="preview-json">{{ formatInlineFrame(recentFrames.at(-1)?.data) }}</code>
        </div>
      </div>

      <button class="toggle-btn" type="button" @click="toggleConsole">
        {{ isExpanded ? '关闭原始数据明细' : '展开原始数据明细' }}
      </button>
    </div>

    <div class="terminal-strip">
      <span>缓存 {{ store.rawStream.length }} 条</span>
      <span>最近更新 {{ latestFrameTime }}</span>
    </div>

    <Teleport to="body">
      <div v-if="isExpanded" class="terminal-overlay" @click.self="toggleConsole">
        <div class="terminal-modal glass-panel">
          <div class="terminal-modal__header">
            <div class="terminal-modal__title">
              <p class="eyebrow">原始数据浮窗</p>
              <strong>完整 JSON 明细</strong>
            </div>

            <button class="modal-close" type="button" @click="toggleConsole" aria-label="关闭">
              &times;
            </button>
          </div>

          <div class="terminal-toolbar">
            <span>最近 12 条原始转发数据</span>
            <span>{{ latestFrameTime }}</span>
          </div>

          <div class="terminal-body" ref="terminalRef">
            <div v-if="recentFrames.length === 0" class="no-data">
              [SYS] 等待 TCP 数据帧接入...
            </div>
            <article v-for="frame in recentFrames" :key="frame.id" class="code-line">
              <div class="line-header">
                <span class="time">[{{ frame.time }}]</span>
                <span class="tag">RAW JSON</span>
              </div>
              <pre class="json">{{ formatFrame(frame.data) }}</pre>
            </article>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.raw-data-terminal {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.5rem;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0.65rem 0.75rem;
  border-radius: 22px;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(56, 189, 248, 0.2);
  box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.35);
}

.terminal-mini {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  min-height: 0;
}

.terminal-mini__copy {
  min-width: 0;
  flex: 1 1 auto;
}

.eyebrow {
  margin: 0 0 0.22rem;
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  color: rgba(148, 163, 184, 0.8);
  text-transform: uppercase;
}

.console-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  color: #f8fafc;
}

.console-title strong {
  font-size: 0.9rem;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background-color: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 10px #10b981;
  animation: pulse 1.5s infinite;
}

.terminal-preview {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin-top: 0.45rem;
  min-width: 0;
  padding: 0.55rem 0.68rem;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.68);
  border: 1px solid rgba(59, 130, 246, 0.18);
}

.preview-time {
  flex-shrink: 0;
  color: #a78bfa;
  font-size: 0.72rem;
}

.preview-json {
  min-width: 0;
  overflow: hidden;
  color: #94a3b8;
  font-size: 0.72rem;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.toggle-btn {
  flex-shrink: 0;
  min-width: 124px;
  padding: 0.52rem 0.8rem;
  border-radius: 12px;
  border: 1px solid rgba(56, 189, 248, 0.18);
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd;
  font-size: 0.78rem;
}

.terminal-strip {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
  padding: 0.48rem 0.68rem;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.46);
  border: 1px solid rgba(148, 163, 184, 0.12);
  color: #94a3b8;
  font-size: 0.72rem;
}

.terminal-overlay {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  z-index: 9999;
  width: min(800px, calc(100vw - 2rem));
  height: min(500px, calc(100vh - 2rem));
}

.terminal-modal {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 24px 60px rgba(2, 6, 23, 0.48);
}

.terminal-modal__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1rem 0.75rem;
}

.terminal-modal__title strong {
  color: #f8fafc;
  font-size: 1.08rem;
}

.modal-close {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(30, 41, 59, 0.8);
  color: #f8fafc;
  font-size: 1.35rem;
  line-height: 1;
}

.terminal-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.72rem 1rem;
  background: rgba(15, 23, 42, 0.82);
  color: #10b981;
  font-size: 0.78rem;
  border-top: 1px solid rgba(59, 130, 246, 0.14);
  border-bottom: 1px solid rgba(59, 130, 246, 0.14);
}

.terminal-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 0.85rem 1rem 1rem;
  scrollbar-width: thin;
}

.code-line {
  margin-bottom: 0.8rem;
  padding: 0.8rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.line-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.55rem;
}

.time {
  color: #a78bfa;
}

.tag {
  color: #22d3ee;
  font-size: 11px;
  letter-spacing: 0.08em;
}

.json {
  margin: 0;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.no-data {
  color: #64748b;
  font-style: italic;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.3; }
  100% { opacity: 1; }
}

@media (max-width: 900px) {
  .terminal-mini,
  .terminal-toolbar,
  .terminal-strip {
    flex-direction: column;
    align-items: stretch;
  }

  .terminal-overlay {
    left: 0.75rem;
    right: 0.75rem;
    bottom: 0.75rem;
    width: auto;
    height: min(500px, calc(100vh - 1.5rem));
  }

  .terminal-modal {
    height: 100%;
  }
}
</style>
