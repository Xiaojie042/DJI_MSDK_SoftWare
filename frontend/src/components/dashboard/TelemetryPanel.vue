<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()

const safetyTone = computed(() => `tone-${store.safetyPolicy.level}`)
const healthTone = computed(() => `tone-${store.batteryHealth.tone}`)

const localSavedTime = computed(() => {
  if (!store.localCacheMeta.lastSavedAt) {
    return '等待首次保存'
  }

  return new Date(store.localCacheMeta.lastSavedAt).toLocaleTimeString('zh-CN', {
    hour12: false
  })
})

const debugItems = computed(() => [
  {
    label: 'GPS 信号',
    value: `${store.droneState.gps_signal || 0} / 5`
  },
  {
    label: '遥控信号',
    value: store.droneState.rc_signal !== null ? `${store.droneState.rc_signal}%` : '--'
  },
  {
    label: '云台俯仰',
    value: `${(store.droneState.gimbal_pitch || 0).toFixed(1)}°`
  },
  {
    label: '返航距离',
    value: `${(store.droneState.home_distance || 0).toFixed(1)} m`
  },
  {
    label: '垂直速度',
    value: `${(store.droneState.velocity.vertical || 0).toFixed(1)} m/s`
  },
  {
    label: '原始帧缓存',
    value: `${store.rawStream.length} 条`
  },
  {
    label: '本地归档',
    value: `${store.localArchiveCount} 条`
  },
  {
    label: '最近保存',
    value: localSavedTime.value
  }
])

const batteryScoreText = computed(() =>
  store.batteryHealth.score === null ? '--' : `${store.batteryHealth.score}`
)

const hasValue = (value) => value !== undefined && value !== null && value !== ''

const readPath = (source, path) => {
  if (!source || typeof source !== 'object') {
    return undefined
  }

  if (Object.prototype.hasOwnProperty.call(source, path)) {
    return source[path]
  }

  return path.split('.').reduce((current, segment) => {
    if (!current || typeof current !== 'object') {
      return undefined
    }

    return current[segment]
  }, source)
}

const latestFlightPayload = () => {
  for (let index = store.rawStream.length - 1; index >= 0; index -= 1) {
    const candidate = store.rawStream[index]?.data

    if (candidate && typeof candidate === 'object' && candidate.type !== 'psdk_data') {
      return candidate
    }
  }

  return null
}

const readFlightValue = (paths, fallback = null) => {
  const payload = latestFlightPayload()

  if (!payload) {
    return fallback
  }

  for (const path of paths) {
    const value = readPath(payload, path)
    if (hasValue(value)) {
      return value
    }
  }

  return fallback
}

const formatIntegerMetric = (value, suffix = '') => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${Math.round(numeric)}${suffix}` : '--'
}

const formatFailsafeAction = () => {
  const value = readFlightValue(['failsafe_action'], null)
  return hasValue(value) ? String(value).replace(/_/g, ' ') : '--'
}

const formatDistanceLimit = () => {
  const enabled = readFlightValue(['distance_limit_enabled'], null)
  const limit = readFlightValue(['distance_limit'], null)
  const hasLimit = Number.isFinite(Number(limit))

  if (enabled === false && hasLimit) {
    return `OFF / ${Math.round(Number(limit))} m`
  }

  if (enabled === false) {
    return 'OFF'
  }

  return hasLimit ? `${Math.round(Number(limit))} m` : '--'
}
</script>

<template>
  <section class="telemetry-panel glass-panel">
    <div class="panel-grid">
      <article class="status-card safety-card" :class="safetyTone">
        <div class="card-topline">
          <span class="card-label">安全策略</span>
          <div class="policy-badge" :class="safetyTone">{{ store.safetyPolicy.badge }}</div>
        </div>
        <strong>{{ store.safetyPolicy.title }}</strong>
        <p class="clamp-two">{{ store.safetyPolicy.description }}</p>
        <small class="clamp-one">{{ store.safetyPolicy.action }}</small>
        <button type="button" class="track-clear-button" @click="store.clearCurrentTrack">
          清除当前轨迹
        </button>
      </article>

      <article class="status-card battery-card" :class="healthTone">
        <div class="card-topline">
          <span class="card-label">电池与状态</span>
          <div class="health-chip">{{ batteryScoreText }}</div>
        </div>
        <strong>{{ store.batteryHealth.label }}</strong>
        <p class="clamp-two">{{ store.batteryHealth.summary }}</p>

        <div class="health-metrics">
          <div>
            <span>电压</span>
            <strong>{{ (store.droneState.battery.voltage || 0).toFixed(1) }} V</strong>
          </div>
          <div>
            <span>温度</span>
            <strong>{{ (store.droneState.battery.temperature || 0).toFixed(1) }} °C</strong>
          </div>
        </div>

        <small class="status-footnote">最近保存 {{ localSavedTime }}</small>
      </article>

      <article class="status-card limits-card">
        <div class="card-topline">
          <span class="card-label">安全与限制</span>
          <strong class="limits-title">2x2</strong>
        </div>

        <div class="limits-grid">
          <div class="limit-item">
            <span>返航高度 (RTH)</span>
            <strong>{{ formatIntegerMetric(readFlightValue(['go_home_height'], null), ' m') }}</strong>
          </div>
          <div class="limit-item">
            <span>限高 (H-LIM)</span>
            <strong>{{ formatIntegerMetric(readFlightValue(['height_limit'], null), ' m') }}</strong>
          </div>
          <div class="limit-item">
            <span>限远 (D-LIM)</span>
            <strong>{{ formatDistanceLimit() }}</strong>
          </div>
          <div class="limit-item">
            <span>失控动作 (F-SAFE)</span>
            <strong>{{ formatFailsafeAction() }}</strong>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.telemetry-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0.35rem 0.75rem;
  border-radius: 22px;
}

.panel-grid {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  align-items: stretch;
  gap: 0;
}

.status-card {
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
  padding: 0.45rem 0.9rem;
  background: transparent;
  border: none;
  border-radius: 0;
  overflow: hidden;
}

.status-card + .status-card {
  border-left: 1px solid rgba(148, 163, 184, 0.18);
}

.card-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.card-label {
  display: block;
  color: #94a3b8;
  font-size: 0.64rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.status-card strong {
  display: block;
  margin-bottom: 0;
  color: #f8fafc;
  font-size: 0.88rem;
}

.status-card p,
.status-card small {
  display: block;
  margin: 0;
  color: #94a3b8;
  line-height: 1.28;
  font-size: 0.72rem;
}

.clamp-one,
.clamp-two {
  display: -webkit-box !important;
  overflow: hidden;
  -webkit-box-orient: vertical;
}

.clamp-one {
  -webkit-line-clamp: 1;
}

.clamp-two {
  -webkit-line-clamp: 2;
}

.policy-badge {
  padding: 0.24rem 0.55rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  border: 1px solid transparent;
}

.health-chip {
  min-width: 42px;
  text-align: center;
  padding: 0.18rem 0.42rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.9);
  color: #f8fafc;
  font-weight: 700;
  font-size: 0.72rem;
}

.health-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.4rem;
  margin-top: auto;
}

.health-metrics div,
.limit-item {
  padding: 0.42rem 0.5rem;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.46);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.health-metrics span,
.limit-item span {
  display: block;
  margin-bottom: 0.15rem;
  color: #94a3b8;
  font-size: 0.62rem;
  line-height: 1.2;
}

.health-metrics strong,
.limit-item strong {
  margin-bottom: 0;
  font-size: 0.75rem;
  line-height: 1.2;
}

.status-footnote {
  margin-top: 0.42rem;
}

.track-clear-button {
  margin-top: auto;
  width: 100%;
  min-height: 34px;
  border: 1px solid rgba(125, 211, 252, 0.28);
  border-radius: 10px;
  background: rgba(14, 165, 233, 0.12);
  color: #e0f2fe;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

.track-clear-button:hover {
  background: rgba(14, 165, 233, 0.2);
  border-color: rgba(125, 211, 252, 0.42);
}

.track-clear-button:active {
  transform: translateY(1px);
}

.limits-card {
  justify-content: space-between;
}

.limits-title {
  color: #7dd3fc;
  font-size: 0.72rem;
  font-weight: 700;
}

.limits-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: auto;
}

.tone-good {
  border-color: rgba(34, 197, 94, 0.24);
}

.tone-good.policy-badge,
.tone-good .health-chip {
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
}

.tone-good.safety-card,
.tone-good.battery-card {
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.12), rgba(15, 23, 42, 0.08));
}

.tone-warning {
  border-color: rgba(245, 158, 11, 0.24);
}

.tone-warning.policy-badge,
.tone-warning .health-chip {
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
}

.tone-warning.safety-card,
.tone-warning.battery-card {
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.12), rgba(15, 23, 42, 0.08));
}

.tone-danger {
  border-color: rgba(239, 68, 68, 0.24);
}

.tone-danger.policy-badge,
.tone-danger .health-chip {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}

.tone-danger.safety-card,
.tone-danger.battery-card {
  background: linear-gradient(180deg, rgba(239, 68, 68, 0.12), rgba(15, 23, 42, 0.08));
}

.tone-offline {
  border-color: rgba(148, 163, 184, 0.24);
}

.tone-offline.policy-badge {
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
}

.tone-offline.safety-card {
  background: linear-gradient(180deg, rgba(148, 163, 184, 0.12), rgba(15, 23, 42, 0.08));
}

.tone-neutral {
  border-color: rgba(56, 189, 248, 0.18);
}

.tone-neutral .health-chip {
  background: rgba(56, 189, 248, 0.12);
  color: #7dd3fc;
}

.tone-neutral.battery-card {
  background: linear-gradient(180deg, rgba(56, 189, 248, 0.1), rgba(15, 23, 42, 0.08));
}

@media (max-width: 1320px) {
  .panel-grid {
    flex-direction: column;
  }

  .status-card + .status-card {
    border-left: none;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
  }
}
</style>
