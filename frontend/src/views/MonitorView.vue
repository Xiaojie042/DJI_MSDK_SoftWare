<script setup>
import { useWebSocket } from '@/composables/useWebSocket'
import TopBar from '@/components/dashboard/TopBar.vue'
import RawDataTerminal from '@/components/dashboard/RawDataTerminal.vue'
import TelemetryPanel from '@/components/dashboard/TelemetryPanel.vue'
import WeatherSidebar from '@/components/dashboard/WeatherSidebar.vue'
import DroneMap from '@/components/map/DroneMap.vue'

useWebSocket()
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

        <div class="map-caption glass-panel">
          <span class="caption-dot"></span>
          <strong>飞行轨迹已启用</strong>
          <span>点击地图中的无人机箭头可查看跟随明细弹窗</span>
        </div>
      </section>
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
  height: 608px;
  pointer-events: auto;
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

.bottom-deck {
  flex: 0 0 150px;
  height: 150px;
  max-height: 150px;
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(340px, 0.95fr);
  gap: 1rem;
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
  height: 150px;
}

@media (max-width: 1100px) {
  .weather-floating {
    top: 0.65rem;
    right: 0.65rem;
    transform: scale(0.92);
    transform-origin: top right;
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

  .map-caption {
    left: 0.75rem;
    right: 0.75rem;
    bottom: 0.75rem;
    justify-content: center;
  }
}
</style>
