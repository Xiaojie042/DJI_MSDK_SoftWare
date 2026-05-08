<script setup>
import { useWebSocket } from '@/composables/useWebSocket'
import TopBar from '@/components/dashboard/TopBar.vue'
import RawDataTerminal from '@/components/dashboard/RawDataTerminal.vue'
import TelemetryPanel from '@/components/dashboard/TelemetryPanel.vue'
import WeatherSidebar from '@/components/dashboard/WeatherSidebar.vue'
import LiveForwardPanel from '@/components/dashboard/LiveForwardPanel.vue'
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

        <aside class="live-forward-floating">
          <LiveForwardPanel />
        </aside>
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
</style>
