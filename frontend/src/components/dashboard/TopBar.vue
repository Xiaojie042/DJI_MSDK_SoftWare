<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()
const displayDroneState = computed(() => store.currentDroneState)
const displayFlightPayload = computed(() => store.currentFlightPayload)

const readPath = (source, path) => {
  if (!source || typeof source !== 'object') {
    return undefined
  }

  return path.split('.').reduce((current, segment) => {
    if (!current || typeof current !== 'object') {
      return undefined
    }

    return current[segment]
  }, source)
}

const flightStatus = computed(() => ({
  isFlying: displayDroneState.value.is_flying || false,
  text: displayDroneState.value.is_flying ? displayDroneState.value.flight_mode || '飞行中' : '待命'
}))

const satelliteInfo = computed(() => {
  const value = Number(
    readPath(displayFlightPayload.value, 'gps_satellite_count') ??
      readPath(displayFlightPayload.value, 'satellite_count') ??
      readPath(displayFlightPayload.value, 'satelliteCount')
  )

  if (!Number.isFinite(value)) {
    return {
      text: '--',
      status: 'normal'
    }
  }

  let status = 'success'
  if (value < 6) {
    status = 'danger'
  } else if (value <= 10) {
    status = 'warning'
  }

  return {
    text: `${Math.round(value)}`,
    status
  }
})

const linkQuality = computed(() => {
  if (displayDroneState.value.rc_signal === null || displayDroneState.value.rc_signal === undefined) {
    return {
      text: '--',
      level: 0,
      status: 'normal'
    }
  }

  const quality = Math.max(0, Math.min(5, Math.round(displayDroneState.value.rc_signal / 20)))
  let status = 'success'
  if (quality === 1) {
    status = 'danger'
  } else if (quality === 2) {
    status = 'warning'
  }

  return {
    text: `${quality}/5`,
    level: quality,
    status
  }
})

const rcSignal = computed(() => {
  const value = displayDroneState.value.rc_signal
  if (value === null || value === undefined) {
    return {
      text: '--',
      status: 'normal'
    }
  }

  let status = 'success'
  if (value < 20) {
    status = 'danger'
  } else if (value < 50) {
    status = 'warning'
  }

  return {
    text: `${value}%`,
    status
  }
})

const droneBattery = computed(() => {
  const value = displayDroneState.value.battery.percent || 0
  let status = 'success'
  if (value < 20) {
    status = 'danger'
  } else if (value < 50) {
    status = 'warning'
  }

  return {
    value,
    status
  }
})
</script>

<template>
  <header class="top-bar glass-panel">
    <div class="logo">
      <p class="eyebrow">Flight Command Center</p>
      <h1 class="text-gradient">DJI 飞行指挥中心</h1>
    </div>

    <div class="status-bar">
      <div class="status-item">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span class="value" :class="{ active: flightStatus.isFlying }">
          {{ flightStatus.text }}
        </span>
      </div>

      <div class="status-item" :class="linkQuality.status">
        <span class="emoji-icon">链路</span>
        <span class="value">{{ linkQuality.text }}</span>
      </div>

      <div class="status-item" :class="satelliteInfo.status">
        <span class="emoji-icon">卫星</span>
        <span class="value">{{ satelliteInfo.text }}</span>
      </div>

      <div class="status-item" :class="rcSignal.status">
        <span class="emoji-icon">遥控</span>
        <span class="value">{{ rcSignal.text }}</span>
      </div>

      <div class="status-item" :class="droneBattery.status">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <rect x="2" y="7" width="18" height="10" rx="2" stroke-width="2" />
          <path d="M20 10h2v4h-2" stroke-width="2" stroke-linecap="round" />
          <rect x="4" y="9" width="14" height="6" rx="1" fill="currentColor" opacity="0.6" />
        </svg>
        <span class="value">{{ droneBattery.value }}%</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
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

.status-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 50%;
  justify-content: flex-end;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1rem;
  background: var(--bg-panel);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 12px;
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  transition: all 0.2s ease;
}

.status-item .icon {
  width: 18px;
  height: 18px;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: color 0.2s ease;
}

.status-item .emoji-icon {
  font-size: 0.82rem;
  line-height: 1;
  flex-shrink: 0;
  opacity: 0.82;
  transition: opacity 0.2s ease, filter 0.2s ease;
}

.status-item .value {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-muted);
  white-space: nowrap;
  transition: color 0.2s ease;
}

.status-item .value.active {
  color: var(--success);
}

.status-item.success .icon,
.status-item.success .value {
  color: var(--success);
}

.status-item.success .emoji-icon {
  opacity: 1;
  filter: drop-shadow(0 0 4px rgba(16, 185, 129, 0.6));
}

.status-item.success {
  border-color: rgba(16, 185, 129, 0.3);
  background: rgba(16, 185, 129, 0.08);
}

.status-item.warning .icon,
.status-item.warning .value {
  color: var(--warning);
}

.status-item.warning .emoji-icon {
  opacity: 1;
  filter: drop-shadow(0 0 4px rgba(245, 158, 11, 0.6));
}

.status-item.warning {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.08);
}

.status-item.danger .icon,
.status-item.danger .value {
  color: var(--danger);
}

.status-item.danger .emoji-icon {
  opacity: 1;
  filter: drop-shadow(0 0 6px rgba(239, 68, 68, 0.8));
}

.status-item.danger {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.12);
  animation: pulse-danger 2s ease-in-out infinite;
}

@keyframes pulse-danger {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
  }
}

@media (max-width: 1100px) {
  .status-bar {
    width: 100%;
    flex-wrap: wrap;
  }
}

@media (max-width: 900px) {
  .top-bar {
    flex-direction: column;
    align-items: flex-start;
    padding: 1rem;
  }

  .status-bar {
    width: 100%;
    justify-content: flex-start;
  }

  .status-item {
    flex: 1;
    min-width: 0;
    justify-content: center;
  }
}
</style>
