<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import ConnectionConfigEntry from '@/components/dashboard/ConnectionConfigEntry.vue'

const store = useDroneStore()
const displayDroneState = computed(() => store.currentDroneState)
const displayFlightPayload = computed(() => store.currentFlightPayload)

const FLIGHT_MODE_LABELS = {
  DISCONNECTED: '未连接',
  UNKNOWN: '状态未知',
  TAKE_OFF_READY: '起飞准备',
  AUTO_TAKE_OFF: '自动起飞',
  GPS: 'GPS 飞行',
  GPS_NORMAL: 'GPS 正常飞行',
  'P-GPS': 'GPS 定位飞行',
  HOVER: '悬停',
  GO_HOME: '返航中',
  AUTO_LANDING: '自动降落',
  ATTI: '姿态模式',
  LOW_BATTERY_PREPARE_RTH: '低电量返航准备',
  BATTERY_DIAGNOSIS_PROTECT: '电池保护'
}

const LINK_QUALITY_LABELS = ['无信号', '很弱', '较弱', '一般', '良好', '很强']

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

const translateFlightMode = (value, isFlying = false) => {
  const rawMode = String(value || '').trim()
  if (!rawMode) {
    return isFlying ? '飞行中' : '待命'
  }

  const normalizedMode = rawMode.toUpperCase()
  return FLIGHT_MODE_LABELS[normalizedMode] || FLIGHT_MODE_LABELS[rawMode] || rawMode.replace(/_/g, ' ')
}

const flightStatus = computed(() => ({
  raw: displayDroneState.value.flight_mode || '',
  isFlying: displayDroneState.value.is_flying || false,
  text: translateFlightMode(displayDroneState.value.flight_mode, displayDroneState.value.is_flying || false)
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

    <div class="top-bar__center">
      <ConnectionConfigEntry />
    </div>

    <div class="status-bar">
      <div class="status-item">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span class="value" :class="{ active: flightStatus.isFlying }" :title="flightStatus.raw || flightStatus.text">
          {{ flightStatus.text }}
        </span>
      </div>

      <div class="status-item" :class="linkQuality.status">
        <span class="emoji-icon">📶</span>
        <span class="value">{{ linkQuality.text }}</span>
      </div>

      <div class="status-item" :class="satelliteInfo.status">
        <span class="emoji-icon">🛰️</span>
        <span class="value">{{ satelliteInfo.text }}</span>
      </div>

      <div class="status-item" :class="rcSignal.status">
        <span class="emoji-icon">🎮</span>
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
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px minmax(0, 1fr);
  align-items: center;
  gap: 0.85rem;
  padding: 0.24rem 1.1rem;
  min-height: 55px;
  border-radius: 22px;
  flex-shrink: 0;
}

.logo {
  min-width: 0;
  justify-self: start;
}

.eyebrow {
  margin: 0 0 0.06rem;
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  color: rgba(148, 163, 184, 0.8);
  text-transform: uppercase;
}

.logo h1 {
  margin: 0;
  font-size: 1.42rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.top-bar__center {
  min-width: 0;
  width: 100%;
  max-width: 300px;
  display: flex;
  justify-content: center;
  justify-self: center;
}

.top-bar__center > * {
  width: 100%;
  max-width: 300px;
}

.status-bar {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  justify-self: end;
  gap: 0.7rem;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 38px;
  padding: 0 0.82rem;
  background: var(--bg-panel);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 12px;
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  transition: all 0.2s ease;
}

.icon {
  width: 17px;
  height: 17px;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: color 0.2s ease;
}

.emoji-icon {
  font-size: 0.82rem;
  line-height: 1;
  flex-shrink: 0;
  opacity: 0.82;
  transition: opacity 0.2s ease, filter 0.2s ease;
}

.value {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-muted);
  white-space: nowrap;
  transition: color 0.2s ease;
}

.value.active {
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
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.36);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
  }
}

@media (max-width: 1280px) {
  .top-bar {
    grid-template-columns: minmax(0, 1fr) 300px;
  }

  .status-bar {
    grid-column: 1 / -1;
    justify-self: stretch;
    justify-content: flex-start;
  }
}

@media (max-width: 900px) {
  .top-bar {
    grid-template-columns: 1fr;
    padding: 1rem;
  }

  .top-bar__center {
    justify-self: start;
  }

  .top-bar__center,
  .status-bar {
    justify-content: stretch;
  }

  .status-item {
    flex: 1 1 140px;
    justify-content: center;
  }
}
</style>
