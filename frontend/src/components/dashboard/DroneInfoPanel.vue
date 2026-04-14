<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()

const panelWidth = ref(360)
const panelHeight = ref(360)

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)
const formatNumber = (value, digits = 1, unit = '') =>
  Number.isFinite(value) ? `${value.toFixed(digits)}${unit}` : `--${unit}`

const connectionLabel = computed(() => (store.isConnected ? '链路在线' : '链路离线'))
const connectionTone = computed(() => (store.isConnected ? 'good' : 'danger'))
const batteryPercent = computed(() => Math.round(store.droneState.battery.percent || 0))
const batteryColor = computed(() => {
  if (batteryPercent.value <= 20) {
    return '#ef4444'
  }

  if (batteryPercent.value <= 45) {
    return '#f59e0b'
  }

  return '#22c55e'
})

const batteryGaugeStyle = computed(() => ({
  background: `conic-gradient(${batteryColor.value} ${batteryPercent.value * 3.6}deg, rgba(15, 23, 42, 0.78) 0deg)`
}))

const lastUpdate = computed(() => {
  if (!store.droneState.timestamp) {
    return '--:--:--'
  }

  return new Date(store.droneState.timestamp * 1000).toLocaleTimeString('zh-CN', {
    hour12: false
  })
})

const panelStyle = computed(() => ({
  width: `${panelWidth.value}px`,
  height: `${panelHeight.value}px`
}))

let startX = 0
let startY = 0
let startWidth = panelWidth.value
let startHeight = panelHeight.value

const stopResize = () => {
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
}

const onResize = (event) => {
  const maxWidth = Math.min(window.innerWidth - 96, 560)
  const maxHeight = Math.min(window.innerHeight - 180, 560)

  panelWidth.value = clamp(startWidth + (event.clientX - startX), 300, maxWidth)
  panelHeight.value = clamp(startHeight + (event.clientY - startY), 280, maxHeight)
}

const startResize = (event) => {
  event.preventDefault()

  startX = event.clientX
  startY = event.clientY
  startWidth = panelWidth.value
  startHeight = panelHeight.value

  window.addEventListener('mousemove', onResize)
  window.addEventListener('mouseup', stopResize)
}

onBeforeUnmount(() => {
  stopResize()
})
</script>

<template>
  <section class="drone-info-panel glass-panel" :style="panelStyle">
    <header class="panel-header">
      <div>
        <p class="eyebrow">无人机信息</p>
        <h2>{{ store.droneState.drone_id }}</h2>
      </div>
      <div class="state-pill" :class="connectionTone">{{ connectionLabel }}</div>
    </header>

    <div class="hero-grid">
      <div class="battery-hero">
        <div class="battery-gauge" :style="batteryGaugeStyle">
          <div class="battery-core">
            <strong>{{ batteryPercent }}%</strong>
            <span>剩余电量</span>
          </div>
        </div>
      </div>

      <div class="hero-status">
        <div class="hero-card">
          <span>飞行模式</span>
          <strong>{{ store.droneState.flight_mode || 'UNKNOWN' }}</strong>
        </div>
        <div class="hero-card">
          <span>飞行状态</span>
          <strong>{{ store.droneState.is_flying ? '飞行中' : '地面待命' }}</strong>
        </div>
        <div class="hero-card">
          <span>航迹长度</span>
          <strong>
            {{ store.trackDistanceMeters >= 1000 ? `${(store.trackDistanceMeters / 1000).toFixed(2)} km` : `${store.trackDistanceMeters.toFixed(0)} m` }}
          </strong>
        </div>
        <div class="hero-card">
          <span>更新时间</span>
          <strong>{{ lastUpdate }}</strong>
        </div>
      </div>
    </div>

    <div class="metrics-grid">
      <div class="metric-card">
        <span>高度</span>
        <strong>{{ formatNumber(store.droneState.position.altitude, 1, ' m') }}</strong>
      </div>
      <div class="metric-card">
        <span>航向角</span>
        <strong>{{ formatNumber(store.droneState.heading, 0, '°') }}</strong>
      </div>
      <div class="metric-card">
        <span>水平速度</span>
        <strong>{{ formatNumber(store.droneState.velocity.horizontal, 1, ' m/s') }}</strong>
      </div>
      <div class="metric-card">
        <span>垂直速度</span>
        <strong>{{ formatNumber(store.droneState.velocity.vertical, 1, ' m/s') }}</strong>
      </div>
      <div class="metric-card">
        <span>返航距离</span>
        <strong>{{ formatNumber(store.droneState.home_distance, 1, ' m') }}</strong>
      </div>
      <div class="metric-card">
        <span>卫星 / 遥控</span>
        <strong>{{ store.droneState.gps_signal || 0 }} / {{ store.droneState.rc_signal ?? '--' }}</strong>
      </div>
      <div class="metric-card full">
        <span>实时坐标</span>
        <strong>
          {{ Number.isFinite(store.droneState.position.latitude) ? store.droneState.position.latitude.toFixed(6) : '--' }},
          {{ Number.isFinite(store.droneState.position.longitude) ? store.droneState.position.longitude.toFixed(6) : '--' }}
        </strong>
      </div>
    </div>

    <footer class="panel-footer">
      <span>拖拽右下角可调整显示框大小</span>
      <span>航迹点 {{ store.flightTrack.length }}</span>
    </footer>

    <button class="resize-handle" type="button" aria-label="调整显示框大小" @mousedown="startResize">
      <span></span>
      <span></span>
      <span></span>
    </button>
  </section>
</template>

<style scoped>
.drone-info-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem 1rem 1.15rem;
  border-radius: 20px;
  overflow: hidden;
  background:
    linear-gradient(160deg, rgba(15, 23, 42, 0.92), rgba(15, 23, 42, 0.78)),
    rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(56, 189, 248, 0.22);
  box-shadow: 0 22px 40px rgba(2, 8, 23, 0.35);
  backdrop-filter: blur(14px);
}

.drone-info-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top right, rgba(56, 189, 248, 0.14), transparent 38%);
  pointer-events: none;
}

.panel-header,
.hero-grid,
.metrics-grid,
.panel-footer {
  position: relative;
  z-index: 1;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.eyebrow {
  margin: 0 0 0.25rem;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  color: rgba(148, 163, 184, 0.8);
  text-transform: uppercase;
}

h2 {
  margin: 0;
  font-size: 1.25rem;
  color: #f8fafc;
}

.state-pill {
  padding: 0.45rem 0.8rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  border: 1px solid transparent;
}

.state-pill.good {
  color: #86efac;
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.24);
}

.state-pill.danger {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.24);
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(128px, 148px) minmax(0, 1fr);
  gap: 1rem;
  align-items: center;
}

.battery-hero {
  display: flex;
  justify-content: center;
}

.battery-gauge {
  width: 132px;
  height: 132px;
  padding: 10px;
  border-radius: 50%;
  box-shadow: inset 0 0 24px rgba(14, 165, 233, 0.12);
}

.battery-core {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.battery-core strong {
  font-size: 1.75rem;
  line-height: 1;
  color: #f8fafc;
}

.battery-core span {
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: #94a3b8;
}

.hero-status {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.hero-card,
.metric-card {
  background: rgba(30, 41, 59, 0.58);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  padding: 0.8rem 0.9rem;
}

.hero-card span,
.metric-card span {
  display: block;
  font-size: 0.76rem;
  color: #94a3b8;
  margin-bottom: 0.25rem;
}

.hero-card strong,
.metric-card strong {
  color: #f8fafc;
  font-size: 0.96rem;
  font-weight: 600;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  min-height: 0;
}

.metric-card.full {
  grid-column: 1 / -1;
}

.panel-footer {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  font-size: 0.76rem;
  color: rgba(148, 163, 184, 0.88);
}

.resize-handle {
  position: absolute;
  right: 0.45rem;
  bottom: 0.45rem;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 3px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: nwse-resize;
}

.resize-handle span {
  width: 4px;
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.85);
}

.resize-handle span:nth-child(1) {
  height: 10px;
}

.resize-handle span:nth-child(2) {
  height: 16px;
}

.resize-handle span:nth-child(3) {
  height: 22px;
}

@media (max-width: 900px) {
  .drone-info-panel {
    width: min(100%, 100%) !important;
    height: auto !important;
    min-height: 320px;
  }

  .hero-grid {
    grid-template-columns: 1fr;
  }

  .hero-status {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .resize-handle {
    display: none;
  }
}
</style>
