<script setup>
import { computed, ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useDroneStore } from '@/stores/droneStore'
import RawDataTerminal from '@/components/dashboard/RawDataTerminal.vue'
import TelemetryPanel from '@/components/dashboard/TelemetryPanel.vue'
import DroneInfoPanel from '@/components/dashboard/DroneInfoPanel.vue'
import WeatherPanel from '@/components/dashboard/WeatherPanel.vue'
import DroneMap from '@/components/map/DroneMap.vue'

const store = useDroneStore()
const isDroneInfoVisible = ref(false)

useWebSocket()

const flightStateText = computed(() => (store.droneState.is_flying ? '飞行中' : '地面待命'))
const trackDistanceText = computed(() =>
  store.trackDistanceMeters >= 1000
    ? `${(store.trackDistanceMeters / 1000).toFixed(2)} km`
    : `${store.trackDistanceMeters.toFixed(0)} m`
)

const showDroneInfo = () => {
  isDroneInfoVisible.value = true
}

const hideDroneInfo = () => {
  isDroneInfoVisible.value = false
}
</script>

<template>
  <div class="monitor-layout">
    <header class="top-bar glass-panel">
      <div class="logo">
        <p class="eyebrow">Flight Command Center</p>
        <h1 class="text-gradient">DJI 飞行指挥中心</h1>
      </div>

      <div class="status-indicators">
        <div class="indicator" :class="{ connected: store.isConnected }">
          <span class="dot"></span>
          {{ store.isConnected ? '地面站已连接' : '地面站未连接' }}
        </div>
        <div class="indicator" :class="{ connected: store.droneState.is_flying }">
          <span class="dot"></span>
          {{ flightStateText }}
        </div>
        <div class="indicator connected accent">
          <span class="dot"></span>
          航迹长度 {{ trackDistanceText }}
        </div>
      </div>
    </header>

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

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  padding: 0 1.4rem;
  min-height: 74px;
  border-radius: 22px;
  flex-shrink: 0;
}

.eyebrow {
  margin: 0 0 0.2rem;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  color: rgba(148, 163, 184, 0.8);
  text-transform: uppercase;
}

.logo h1 {
  margin: 0;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.status-indicators {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.8rem;
}

.indicator {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.88rem;
  color: var(--text-muted);
  font-weight: 600;
  background: rgba(30, 41, 59, 0.56);
  padding: 0.6rem 1rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger);
  box-shadow: 0 0 8px var(--danger);
}

.indicator.connected .dot {
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}

.indicator.connected {
  color: var(--text-main);
}

.indicator.accent .dot {
  background: var(--info);
  box-shadow: 0 0 8px var(--info);
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

  .top-bar {
    flex-direction: column;
    align-items: flex-start;
    padding: 1rem;
  }

  .status-indicators {
    width: 100%;
    justify-content: flex-start;
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
