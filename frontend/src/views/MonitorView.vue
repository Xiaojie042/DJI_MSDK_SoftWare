<script setup>
import { onMounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useDroneStore } from '@/stores/droneStore'
import DroneMap from '@/components/map/DroneMap.vue'
import TelemetryPanel from '@/components/dashboard/TelemetryPanel.vue'
import AlertPanel from '@/components/alerts/AlertPanel.vue'

const store = useDroneStore()
const { socket } = useWebSocket() // Start WS connection
</script>

<template>
  <div class="monitor-layout">
    <!-- Header -->
    <header class="top-bar glass-panel">
      <div class="logo">
        <h1 class="text-gradient">DJI Command Center</h1>
      </div>
      <div class="status-indicators">
        <div class="indicator" :class="{ connected: store.isConnected }">
          <span class="dot"></span>
          {{ store.isConnected ? 'Server Connected' : 'Server Disconnected' }}
        </div>
        <div class="indicator" :class="{ connected: store.droneState.is_flying }">
          <span class="dot"></span>
          {{ store.droneState.is_flying ? 'Flying' : 'Landed' }}
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Left Panel: Map -->
      <section class="map-container glass-panel">
        <DroneMap />
      </section>

      <!-- Right Panel: Dashboard elements -->
      <aside class="dashboard-sidebar">
        <TelemetryPanel class="mb-4" />
        <AlertPanel />
      </aside>
    </main>
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
  border-radius: 100px;
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
  gap: 1rem;
  flex: 1;
  min-height: 0;
}

.map-container {
  flex: 3;
  border-radius: 24px;
  overflow: hidden;
  position: relative;
}

.dashboard-sidebar {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 350px;
  max-width: 400px;
}

.mb-4 {
  margin-bottom: 1rem;
}
</style>
