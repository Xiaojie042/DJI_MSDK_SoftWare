<script setup>
import { useDroneStore } from '@/stores/droneStore'
const store = useDroneStore()
</script>

<template>
  <div class="telemetry-panel glass-panel">
    <h3>Telemetry Data</h3>
    
    <div class="data-grid">
      <div class="data-item">
        <div class="label">Altitude</div>
        <div class="val text-gradient">{{ store.droneState.position.altitude?.toFixed(1) || '0.0' }} <span class="unit">m</span></div>
      </div>
      
      <div class="data-item">
        <div class="label">Speed (H/V)</div>
        <div class="val">{{ store.droneState.velocity.horizontal?.toFixed(1) || '0.0' }} / {{ store.droneState.velocity.vertical?.toFixed(1) || '0.0' }} <span class="unit">m/s</span></div>
      </div>

      <div class="data-item">
        <div class="label">Distance</div>
        <div class="val">{{ store.droneState.home_distance?.toFixed(1) || '0.0' }} <span class="unit">m</span></div>
      </div>

      <div class="data-item battery">
        <div class="label">Battery</div>
        <div class="val flex-center">
          <div class="battery-bar-container">
            <div class="battery-bar" 
                 :style="{ width: `${store.droneState.battery.percent || 0}%`, 
                           backgroundColor: store.droneState.battery.percent > 20 ? 'var(--success)' : 'var(--danger)' }">
            </div>
          </div>
          <span style="font-size: 1.2rem; font-weight: 600; margin-left: 0.8rem;">{{ store.droneState.battery.percent || 0 }}%</span>
        </div>
      </div>

      <div class="data-item">
        <div class="label">Mode</div>
        <div class="val status-pill">{{ store.droneState.flight_mode || 'UNKNOWN' }}</div>
      </div>
      
      <div class="data-item">
        <div class="label">GPS Signal</div>
        <div class="val flex-center">
          <div class="signal-bars">
            <span v-for="i in 5" :key="i" class="bar" :class="{ active: i <= (store.droneState.gps_signal || 0) }"></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.telemetry-panel {
  padding: 1.5rem;
  border-radius: 20px;
  flex: 1;
}

h3 {
  margin-top: 0;
  margin-bottom: 1.5rem;
  font-size: 1.2rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
}

.data-item {
  background: var(--bg-card);
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.data-item.battery {
  grid-column: span 2;
}

.label {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.val {
  font-size: 1.4rem;
  font-weight: bold;
  color: var(--text-main);
}

.unit {
  font-size: 0.9rem;
  font-weight: normal;
  color: var(--text-muted);
}

.flex-center {
  display: flex;
  align-items: center;
}

.battery-bar-container {
  flex: 1;
  height: 16px;
  background: rgba(0,0,0,0.3);
  border-radius: 8px;
  border: 2px solid var(--border-color);
  overflow: hidden;
  position: relative;
}

.battery-bar {
  height: 100%;
  border-radius: 6px;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.status-pill {
  display: inline-block;
  padding: 2px 10px;
  background: rgba(59, 130, 246, 0.2);
  color: var(--primary);
  border-radius: 50px;
  font-size: 1rem;
  border: 1px solid rgba(59, 130, 246, 0.5);
}

.signal-bars {
  display: flex;
  gap: 3px;
  align-items: flex-end;
  height: 20px;
}

.signal-bars .bar {
  width: 6px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
}
.signal-bars .bar:nth-child(1) { height: 6px; }
.signal-bars .bar:nth-child(2) { height: 9px; }
.signal-bars .bar:nth-child(3) { height: 12px; }
.signal-bars .bar:nth-child(4) { height: 16px; }
.signal-bars .bar:nth-child(5) { height: 20px; }

.signal-bars .bar.active {
  background: var(--info);
  box-shadow: 0 0 5px var(--info);
}
</style>
