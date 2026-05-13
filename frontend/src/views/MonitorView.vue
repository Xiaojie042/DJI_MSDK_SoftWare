<script setup>
import { ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import TopBar from '@/components/dashboard/TopBar.vue'
import RawDataTerminal from '@/components/dashboard/RawDataTerminal.vue'
import TelemetryPanel from '@/components/dashboard/TelemetryPanel.vue'
import WeatherSidebar from '@/components/dashboard/WeatherSidebar.vue'
import LiveForwardPanel from '@/components/dashboard/LiveForwardPanel.vue'
import DroneMap from '@/components/map/DroneMap.vue'
import config from '@/utils/config'
import logger from '@/utils/logger'

useWebSocket()

const showDebugPanel = ref(false)
</script>

<template>
  <div class="monitor-layout">
    <TopBar />

    <main class="workspace">
      <section class="map-stage glass-panel">
        <DroneMap />

        <aside class="weather-floating">
          <WeatherSidebar />
        </aside>

        <aside class="live-forward-floating">
          <LiveForwardPanel />
        </aside>
      </section>
    </main>

    <section class="bottom-deck">
      <TelemetryPanel />
      <RawDataTerminal />
    </section>

    <div class="debug-toggle" @click="showDebugPanel = !showDebugPanel" title="调试面板">
      🛠️
    </div>

    <div v-if="showDebugPanel" class="debug-panel glass-panel">
      <div class="debug-panel__header">
        <strong>调试面板</strong>
        <button @click="showDebugPanel = false">×</button>
      </div>
      <div class="debug-panel__body">
        <div class="debug-row">
          <span>日志缓冲:</span>
          <strong>{{ logger.bufferSize() }} 条</strong>
        </div>
        <div class="debug-row">
          <span>待发送:</span>
          <strong>{{ logger.pendingCount() }} 条</strong>
        </div>
        <div class="debug-actions">
          <button class="debug-btn" @click="logger.flushToBackend()">立即同步到后端</button>
          <button class="debug-btn debug-btn--danger" @click="logger.clearLogs()">清除日志</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitor-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 1rem;
  gap: 1rem;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.08), transparent 26%),
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.08), transparent 24%);
}

.workspace {
  flex: 1 1 auto;
  min-height: 0;
}

.map-stage {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border-radius: 26px;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.weather-floating {
  position: absolute;
  top: 0.7rem;
  right: 0.7rem;
  z-index: 460;
  width: 300px;
  height: 596px;
  pointer-events: auto;
}

.live-forward-floating {
  position: absolute;
  left: 0.7rem;
  bottom: 0.7rem;
  z-index: 470;
  pointer-events: auto;
}

.bottom-deck {
  flex: 0 0 104px;
  height: 104px;
  max-height: 104px;
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(340px, 0.95fr);
  gap: 0.8rem;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
}

.bottom-deck::-webkit-scrollbar {
  display: none;
}

.bottom-deck > * {
  min-height: 0;
  height: 104px;
}

@media (max-width: 1100px) {
  .weather-floating {
    top: 0.65rem;
    right: 0.65rem;
    transform: scale(0.92);
    transform-origin: top right;
  }

  .live-forward-floating {
    transform: scale(0.94);
    transform-origin: bottom left;
  }
}

@media (max-width: 900px) {
  .monitor-layout {
    padding: 0.75rem;
    height: auto;
    min-height: 100vh;
    overflow-y: auto;
  }

  .map-stage {
    min-height: 520px;
  }

  .weather-floating {
    display: none;
  }

  .live-forward-floating {
    position: fixed;
    left: 0.75rem;
    right: 0.75rem;
    bottom: 0.75rem;
    z-index: 9998;
  }
}

.debug-toggle {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  z-index: 9999;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.25);
  cursor: pointer;
  font-size: 1.1rem;
  opacity: 0.6;
  transition: opacity 0.2s ease;
  backdrop-filter: blur(8px);
}

.debug-toggle:hover {
  opacity: 1;
}

.debug-panel {
  position: fixed;
  bottom: 3.5rem;
  right: 1rem;
  z-index: 9999;
  width: 320px;
  padding: 0.75rem;
  border-radius: 14px;
  border: 1px solid rgba(125, 211, 252, 0.2);
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.5);
}

.debug-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.debug-panel__header strong {
  color: #f8fafc;
  font-size: 0.9rem;
}

.debug-panel__header button {
  width: 26px;
  height: 26px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 1rem;
}

.debug-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0;
  color: #94a3b8;
  font-size: 0.78rem;
}

.debug-row strong {
  color: #e2e8f0;
}

.debug-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.debug-btn {
  min-height: 30px;
  padding: 0 0.7rem;
  border-radius: 8px;
  border: 1px solid rgba(125, 211, 252, 0.2);
  background: rgba(14, 165, 233, 0.1);
  color: #e0f2fe;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.debug-btn:hover {
  background: rgba(14, 165, 233, 0.2);
}

.debug-btn--danger {
  border-color: rgba(239, 68, 68, 0.25);
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
}

.debug-btn--danger:hover {
  background: rgba(239, 68, 68, 0.2);
}
</style>
