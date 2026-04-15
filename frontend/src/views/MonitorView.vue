<script setup>
import { ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useDroneStore } from '@/stores/droneStore'
import TopBar from '@/components/dashboard/TopBar.vue'
import RawDataTerminal from '@/components/dashboard/RawDataTerminal.vue'
import TelemetryPanel from '@/components/dashboard/TelemetryPanel.vue'
import DroneInfoPanel from '@/components/dashboard/DroneInfoPanel.vue'
import WeatherPanel from '@/components/dashboard/WeatherPanel.vue'
import DroneMap from '@/components/map/DroneMap.vue'

const store = useDroneStore()
const isDroneInfoVisible = ref(false)

useWebSocket()

const showDroneInfo = () => {
  isDroneInfoVisible.value = true
}

const hideDroneInfo = () => {
  isDroneInfoVisible.value = false
}
</script>

<template>
  <div class="monitor-layout">
    <TopBar />

    <main class="workspace">
      <section class="map-stage glass-panel">
        <DroneMap @drone-click="showDroneInfo" />

        <transition name="panel-fade">
          <DroneInfoPanel
            v-if="isDroneInfoVisible && store.flightTrack.length > 0"
            class="drone-overlay"
            @close="hideDroneInfo"
          />
        </transition>

        <div class="map-caption glass-panel">
          <span class="caption-dot"></span>
          <strong>飞行轨迹已启用</strong>
          <span>点击无人机图标查看详情</span>
        </div>
      </section>

      <aside class="right-sidebar">
        <WeatherPanel />
      </aside>
    </main>

    <section class="bottom-deck">
      <TelemetryPanel />
      <RawDataTerminal />
    </section>
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
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 330px;
  gap: 1rem;
}

.map-stage {
  position: relative;
  min-height: 0;
  overflow: hidden;
  border-radius: 26px;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.drone-overlay {
  position: absolute;
  top: 1rem;
  left: 1rem;
  z-index: 500;
}

.map-caption {
  position: absolute;
  left: 1rem;
  bottom: 1rem;
  z-index: 450;
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.75rem 1rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.78);
}

.caption-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 14px rgba(34, 211, 238, 0.7);
}

.map-caption strong {
  color: #f8fafc;
  font-size: 0.92rem;
}

.map-caption span:last-child {
  color: #94a3b8;
  font-size: 0.82rem;
}

.right-sidebar {
  min-height: 0;
}

.bottom-deck {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(340px, 0.95fr);
  gap: 1rem;
  min-height: 0;
}

.panel-fade-enter-active,
.panel-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.panel-fade-enter-from,
.panel-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 1380px) {
  .workspace {
    grid-template-columns: minmax(0, 1fr) 300px;
  }

  .bottom-deck {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1100px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .right-sidebar {
    min-height: 340px;
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

  .drone-overlay {
    position: absolute;
    top: 0.75rem;
    left: 0.75rem;
    right: 0.75rem;
    margin: 0;
    width: auto !important;
  }

  .map-caption {
    left: 0.75rem;
    right: 0.75rem;
    bottom: 0.75rem;
    justify-content: center;
  }
}
</style>
