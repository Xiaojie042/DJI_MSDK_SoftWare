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

const trackDistanceText = computed(() =>
  store.trackDistanceMeters >= 1000
    ? `${(store.trackDistanceMeters / 1000).toFixed(2)} km`
    : `${store.trackDistanceMeters.toFixed(0)} m`
)

const batteryScoreText = computed(() =>
  store.batteryHealth.score === null ? '--' : `${store.batteryHealth.score}`
)
</script>

<template>
  <section class="telemetry-panel glass-panel">
    <header class="panel-header">
      <div>
        <p class="eyebrow">安全与调试</p>
        <h3>飞控状态总览</h3>
      </div>
      <div class="policy-badge" :class="safetyTone">{{ store.safetyPolicy.badge }}</div>
    </header>

    <div class="panel-grid">
      <article class="status-card safety-card" :class="safetyTone">
        <span class="card-label">安全策略</span>
        <strong>{{ store.safetyPolicy.title }}</strong>
        <p>{{ store.safetyPolicy.description }}</p>
        <small>{{ store.safetyPolicy.action }}</small>
      </article>

      <article class="status-card battery-card" :class="healthTone">
        <div class="battery-topline">
          <span class="card-label">电池健康度</span>
          <div class="health-chip">{{ batteryScoreText }}</div>
        </div>
        <strong>{{ store.batteryHealth.label }}</strong>
        <p>{{ store.batteryHealth.summary }}</p>
        <div class="health-metrics">
          <div>
            <span>电压</span>
            <strong>{{ (store.droneState.battery.voltage || 0).toFixed(1) }} V</strong>
          </div>
          <div>
            <span>温度</span>
            <strong>{{ (store.droneState.battery.temperature || 0).toFixed(1) }} °C</strong>
          </div>
          <div>
            <span>累计航迹</span>
            <strong>{{ trackDistanceText }}</strong>
          </div>
        </div>
      </article>

      <article class="status-card debug-card">
        <span class="card-label">调试信息</span>
        <div class="debug-grid">
          <div v-for="item in debugItems" :key="item.label" class="debug-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
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
  gap: 1rem;
  padding: 1.1rem;
  border-radius: 22px;
  min-height: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 0.25rem;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  color: rgba(148, 163, 184, 0.8);
  text-transform: uppercase;
}

h3 {
  margin: 0;
  color: #f8fafc;
  font-size: 1.18rem;
}

.policy-badge {
  padding: 0.45rem 0.82rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 700;
  border: 1px solid transparent;
}

.panel-grid {
  display: grid;
  grid-template-columns: 1.05fr 1.15fr 1.35fr;
  gap: 0.95rem;
  min-height: 0;
}

.status-card {
  min-height: 0;
  border-radius: 18px;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.68);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.card-label {
  display: block;
  margin-bottom: 0.45rem;
  color: #94a3b8;
  font-size: 0.78rem;
}

.status-card strong {
  display: block;
  margin-bottom: 0.45rem;
  color: #f8fafc;
  font-size: 1.08rem;
}

.status-card p,
.status-card small {
  display: block;
  margin: 0;
  color: #94a3b8;
  line-height: 1.55;
}

.status-card small {
  margin-top: 0.8rem;
}

.battery-topline {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.health-chip {
  min-width: 54px;
  text-align: center;
  padding: 0.3rem 0.55rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.9);
  color: #f8fafc;
  font-weight: 700;
}

.health-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 0.9rem;
}

.health-metrics div,
.debug-item {
  padding: 0.72rem 0.8rem;
  border-radius: 14px;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.health-metrics span,
.debug-item span {
  display: block;
  margin-bottom: 0.3rem;
  color: #94a3b8;
  font-size: 0.75rem;
}

.health-metrics strong,
.debug-item strong {
  margin-bottom: 0;
  font-size: 0.95rem;
}

.debug-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
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
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.12), rgba(15, 23, 42, 0.7));
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
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.12), rgba(15, 23, 42, 0.7));
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
  background: linear-gradient(180deg, rgba(239, 68, 68, 0.12), rgba(15, 23, 42, 0.7));
}

.tone-offline {
  border-color: rgba(148, 163, 184, 0.24);
}

.tone-offline.policy-badge {
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
}

.tone-offline.safety-card {
  background: linear-gradient(180deg, rgba(148, 163, 184, 0.12), rgba(15, 23, 42, 0.7));
}

.tone-neutral {
  border-color: rgba(56, 189, 248, 0.18);
}

.tone-neutral .health-chip {
  background: rgba(56, 189, 248, 0.12);
  color: #7dd3fc;
}

.tone-neutral.battery-card {
  background: linear-gradient(180deg, rgba(56, 189, 248, 0.1), rgba(15, 23, 42, 0.7));
}

@media (max-width: 1320px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .debug-grid,
  .health-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .debug-grid,
  .health-metrics {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
