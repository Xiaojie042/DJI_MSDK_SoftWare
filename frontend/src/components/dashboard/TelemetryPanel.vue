<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import FlightHistoryPanel from '@/components/dashboard/FlightHistoryPanel.vue'

const store = useDroneStore()

const safetyTone = computed(() => `tone-${store.safetyPolicy.level}`)
const healthTone = computed(() => `tone-${store.batteryHealth.tone}`)

const batteryScoreText = computed(() =>
  store.batteryHealth.score === null ? '--' : `${store.batteryHealth.score}`
)
const latestFlightPayload = computed(() => store.latestLiveFlightPayload)
const canRecenterDrone = computed(() => {
  const position = store.currentDroneState?.position || {}
  return Number.isFinite(position.latitude) &&
    Number.isFinite(position.longitude) &&
    (position.latitude !== 0 || position.longitude !== 0)
})
const FAILSAFE_ACTION_LABELS = {
  GOHOME: '返航',
  GO_HOME: '返航',
  LAND: '降落',
  HOVER: '悬停',
  NONE: '无'
}

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

const readFlightValue = (paths, fallback = null) => {
  const payload = latestFlightPayload.value

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
  if (!hasValue(value)) {
    return '--'
  }

  const normalized = String(value).replace(/\s+/g, '_').toUpperCase()
  return FAILSAFE_ACTION_LABELS[normalized] || String(value).replace(/_/g, ' ')
}

const formatDistanceLimit = () => {
  const enabled = readFlightValue(['distance_limit_enabled'], null)
  const limit = readFlightValue(['distance_limit'], null)
  const hasLimit = Number.isFinite(Number(limit))

  if (enabled === false && hasLimit) {
    return `关闭 / ${Math.round(Number(limit))} m`
  }

  if (enabled === false) {
    return '关闭'
  }

  return hasLimit ? `${Math.round(Number(limit))} m` : '--'
}
</script>

<template>
  <section class="telemetry-panel glass-panel">
    <div class="panel-grid">
      <article class="status-card track-card">
        <div class="card-topline">
          <span class="card-label">航迹管理</span>
          <div class="policy-badge track-chip">{{ store.flightTrack.length }} 点</div>
        </div>
        <strong>当前航迹</strong>
        <div class="track-actions">
          <button type="button" class="track-action-button track-action-button--primary" @click="store.clearCurrentTrack">
            清除轨迹
          </button>
          <button
            type="button"
            class="track-action-button track-action-button--secondary"
            @click="store.openFlightHistoryPanel()"
          >
            历史架次
          </button>
          <button
            type="button"
            class="track-action-button track-action-button--recenter"
            :disabled="!canRecenterDrone"
            @click="store.requestDroneRecenter()"
          >
            无人机回正
          </button>
        </div>

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
          <div class="health-metric--policy">
            <span>安全策略</span>
            <strong :class="['policy-inline', safetyTone]">{{ store.safetyPolicy.title }}</strong>
          </div>
        </div>

      </article>

      <article class="status-card limits-card">
        <div class="card-topline">
          <span class="card-label">安全与限制</span>
        </div>

        <div class="limits-grid">
          <div class="limit-item">
            <span>返航高度</span>
            <strong>{{ formatIntegerMetric(readFlightValue(['go_home_height'], null), ' m') }}</strong>
          </div>
          <div class="limit-item">
            <span>限高</span>
            <strong>{{ formatIntegerMetric(readFlightValue(['height_limit'], null), ' m') }}</strong>
          </div>
          <div class="limit-item">
            <span>限远</span>
            <strong>{{ formatDistanceLimit() }}</strong>
          </div>
          <div class="limit-item">
            <span>失控动作</span>
            <strong>{{ formatFailsafeAction() }}</strong>
          </div>
        </div>
      </article>
    </div>

    <FlightHistoryPanel />
  </section>
</template>

<style scoped>
.telemetry-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0.24rem 0.62rem;
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
  gap: 0.28rem;
  padding: 0.28rem 0.72rem;
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
  font-size: 0.6rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.status-card strong {
  display: block;
  margin-bottom: 0;
  color: #f8fafc;
  font-size: 0.82rem;
}

.status-card p,
.status-card small {
  display: block;
  margin: 0;
  color: #94a3b8;
  line-height: 1.2;
  font-size: 0.68rem;
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

.track-card {
  background: linear-gradient(180deg, rgba(56, 189, 248, 0.1), rgba(15, 23, 42, 0.08));
}

.track-chip {
  background: rgba(56, 189, 248, 0.12);
  color: #7dd3fc;
  border-color: rgba(125, 211, 252, 0.18);
}

.track-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.34rem;
  margin-top: auto;
}

.track-action-button {
  min-height: 28px;
  padding: 0 0.35rem;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.46);
  color: #94a3b8;
  font-size: 0.66rem;
  font-weight: 600;
  cursor: not-allowed;
}

.track-action-button--primary,
.track-action-button--secondary,
.track-action-button--recenter {
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

.track-action-button--primary {
  border-color: rgba(125, 211, 252, 0.28);
  background: rgba(14, 165, 233, 0.12);
  color: #e0f2fe;
}

.track-action-button--primary:hover {
  background: rgba(14, 165, 233, 0.2);
  border-color: rgba(125, 211, 252, 0.42);
}

.track-action-button--secondary {
  border-color: rgba(148, 163, 184, 0.18);
  background: rgba(51, 65, 85, 0.7);
  color: #e2e8f0;
}

.track-action-button--secondary:hover {
  background: rgba(71, 85, 105, 0.84);
  border-color: rgba(148, 163, 184, 0.28);
}

.track-action-button--recenter {
  border-color: rgba(167, 139, 250, 0.22);
  background: rgba(129, 140, 248, 0.16);
  color: #e9d5ff;
}

.track-action-button--recenter:hover:not(:disabled) {
  background: rgba(129, 140, 248, 0.26);
  border-color: rgba(196, 181, 253, 0.4);
}

.track-action-button--recenter:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.track-action-button--primary:active,
.track-action-button--secondary:active,
.track-action-button--recenter:active {
  transform: translateY(1px);
}

.health-chip {
  min-width: 42px;
  text-align: center;
  padding: 0.14rem 0.38rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.9);
  color: #f8fafc;
  font-weight: 700;
  font-size: 0.68rem;
}

.health-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.32rem;
  margin-top: auto;
}

.health-metrics div,
.limit-item {
  padding: 0.34rem 0.46rem;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.46);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.health-metrics span,
.limit-item span {
  display: block;
  margin-bottom: 0.08rem;
  color: #94a3b8;
  font-size: 0.58rem;
  line-height: 1.2;
}

.health-metrics strong,
.limit-item strong {
  margin-bottom: 0;
  font-size: 0.7rem;
  line-height: 1.2;
}

.policy-inline {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.policy-inline.tone-good {
  color: #86efac;
}

.policy-inline.tone-warning {
  color: #fcd34d;
}

.policy-inline.tone-danger {
  color: #fca5a5;
}

.policy-inline.tone-offline,
.policy-inline.tone-neutral {
  color: #7dd3fc;
}

.limits-card {
  justify-content: space-between;
}

.limits-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: auto;
}

.limit-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem;
}

.limit-item span,
.limit-item strong {
  display: inline;
  margin: 0;
}

.limit-item strong {
  white-space: nowrap;
}

.tone-good .health-chip {
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
}

.tone-good.battery-card {
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.12), rgba(15, 23, 42, 0.08));
}

.tone-warning .health-chip {
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
}

.tone-warning.battery-card {
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.12), rgba(15, 23, 42, 0.08));
}

.tone-danger .health-chip {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}

.tone-danger.battery-card {
  background: linear-gradient(180deg, rgba(239, 68, 68, 0.12), rgba(15, 23, 42, 0.08));
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
