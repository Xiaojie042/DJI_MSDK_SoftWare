<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()

const moduleStatus = computed(() => (store.isConnected ? '待接入' : '离线'))
const advisory = computed(() => {
  if (!store.isConnected) {
    return '当前未接入飞行链路，建议先恢复地面站连接后再联动气象设备。'
  }

  if (store.droneState.position.altitude > 120) {
    return '当前飞行高度较高，建议重点关注侧风、能见度与降水变化。'
  }

  return '气象设备暂未接入，建议结合现场观测和飞控告警进行放飞判断。'
})

const weatherMetrics = [
  { label: '风速', value: '--', unit: 'm/s', hint: '待接入气象站' },
  { label: '风向', value: '--', unit: '', hint: '待接入风向数据' },
  { label: '能见度', value: '--', unit: 'km', hint: '待接入环境感知' },
  { label: '降水', value: '--', unit: 'mm/h', hint: '待接入降水监测' }
]
</script>

<template>
  <section class="weather-panel glass-panel">
    <header class="panel-header">
      <div>
        <p class="eyebrow">气象监测</p>
        <h3>飞行环境观测</h3>
      </div>
      <div class="module-badge" :class="store.isConnected ? 'pending' : 'offline'">{{ moduleStatus }}</div>
    </header>

    <div class="weather-status">
      <div class="status-ring">
        <span>WX</span>
      </div>
      <div class="status-copy">
        <strong>外部气象站暂未接入</strong>
        <p>模块已调整至右侧预留区，后续可直接接入风速、风向、温湿度和雨量数据。</p>
      </div>
    </div>

    <div class="metric-grid">
      <div v-for="item in weatherMetrics" :key="item.label" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}<small>{{ item.unit }}</small></strong>
        <p>{{ item.hint }}</p>
      </div>
    </div>

    <div class="advisory-card">
      <span>飞行建议</span>
      <p>{{ advisory }}</p>
    </div>
  </section>
</template>

<style scoped>
.weather-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
  padding: 1.1rem;
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.84)),
    rgba(15, 23, 42, 0.9);
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
  font-size: 1.2rem;
}

.module-badge {
  padding: 0.4rem 0.78rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.module-badge.pending {
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.module-badge.offline {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.weather-status {
  display: flex;
  gap: 1rem;
  align-items: center;
  padding: 1rem;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.14), rgba(59, 130, 246, 0.08));
  border: 1px solid rgba(56, 189, 248, 0.16);
}

.status-ring {
  width: 72px;
  height: 72px;
  flex-shrink: 0;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #38bdf8;
  font-weight: 800;
  letter-spacing: 0.1em;
  background:
    radial-gradient(circle at center, rgba(15, 23, 42, 0.94) 54%, transparent 55%),
    conic-gradient(#38bdf8 0deg 90deg, rgba(30, 41, 59, 0.6) 90deg 360deg);
}

.status-copy strong {
  display: block;
  margin-bottom: 0.35rem;
  color: #f8fafc;
}

.status-copy p,
.metric-card p,
.advisory-card p {
  margin: 0;
  color: #94a3b8;
  line-height: 1.55;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.metric-card,
.advisory-card {
  padding: 0.95rem;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.metric-card span,
.advisory-card span {
  display: block;
  margin-bottom: 0.45rem;
  font-size: 0.8rem;
  color: #94a3b8;
}

.metric-card strong {
  display: block;
  margin-bottom: 0.35rem;
  color: #f8fafc;
  font-size: 1.15rem;
}

.metric-card small {
  margin-left: 0.2rem;
  font-size: 0.78rem;
  color: #94a3b8;
}

.advisory-card {
  margin-top: auto;
  background: rgba(15, 23, 42, 0.72);
}

@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
