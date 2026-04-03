<script setup>
import { onMounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useDroneStore } from '@/stores/droneStore'
import DroneMap from '@/components/map/DroneMap.vue'
import RawDataTerminal from '@/components/dashboard/RawDataTerminal.vue'

const store = useDroneStore()
const { socket } = useWebSocket() // Start WS connection
</script>

<template>
  <div class="monitor-layout">
    <!-- Header -->
    <header class="top-bar glass-panel">
      <div class="logo">
        <h1 class="text-gradient">DJI 飞行指挥中心</h1>
      </div>
      <div class="status-indicators">
        <div class="indicator" :class="{ connected: store.isConnected }">
          <span class="dot"></span>
          {{ store.isConnected ? '指挥台已连接' : '指挥台未连接' }}
        </div>
        <div class="indicator" :class="{ connected: store.droneState.is_flying }">
          <span class="dot"></span>
          {{ store.droneState.is_flying ? '飞行中' : '已降落' }}
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Full Map Area -->
      <section class="map-container glass-panel">
        <DroneMap />
      </section>
    </main>

    <!-- Bottom Panels -->
    <footer class="bottom-panels">
      <!-- Raw Data Feed Terminal -->
      <div class="panel-section terminal-wrapper">
        <RawDataTerminal />
      </div>
      
      <!-- Reserved Weather Station Wrapper -->
      <div class="panel-section weather-reserved glass-panel">
        <div class="reserved-content">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="weather-icon">
            <path d="M17.5 19C19.9853 19 22 16.9853 22 14.5C22 12.1332 20.1834 10.2031 17.8687 10.0223C17.4385 6.6433 14.5768 4 11 4C7.13401 4 4 7.13401 4 11C4 11.2335 4.01139 11.4645 4.03352 11.692C1.7828 12.1583 0 14.1202 0 16.5C0 19.5376 2.46243 22 5.5 22H16"></path>
          </svg>
          <h3>气象监测模块</h3>
          <p class="coming-soon">设备未接入 (模块位预留)</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.monitor-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 1rem;
  gap: 1rem;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 2rem;
  height: 70px;
  border-radius: 20px;
  flex-shrink: 0;
}

.logo h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: 1px;
}

.status-indicators {
  display: flex;
  gap: 1.5rem;
}

.indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-muted);
  font-weight: 500;
  background: var(--bg-card);
  padding: 0.5rem 1rem;
  border-radius: 50px;
  transition: all 0.3s ease;
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

.main-content {
  display: flex;
  flex: 1;
  min-height: 0;
}

.map-container {
  flex: 1;
  border-radius: 24px;
  overflow: hidden;
  position: relative;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.bottom-panels {
  display: flex;
  height: 220px; /* Fixed height for bottom panels */
  gap: 1rem;
  flex-shrink: 0;
}

.terminal-wrapper {
  flex: 2; /* 2/3 width */
  min-width: 0;
}

.weather-reserved {
  flex: 1; /* 1/3 width */
  border-radius: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
  background: rgba(30, 41, 59, 0.4);
  border: 1px dashed rgba(148, 163, 184, 0.3);
}

.reserved-content {
  text-align: center;
  color: var(--text-muted);
}

.weather-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 10px;
  opacity: 0.5;
}

h3 {
  margin: 0 0 5px 0;
  font-size: 1.1rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
}

.coming-soon {
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.6;
}
</style>
