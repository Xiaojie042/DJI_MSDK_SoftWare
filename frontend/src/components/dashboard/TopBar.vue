<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()

const flightStatus = computed(() => ({
  isFlying: store.droneState.is_flying || false,
  text: store.droneState.is_flying ? store.droneState.flight_mode || '飞行中' : '待命'
}))

// GPS 卫星数 - 只显示数量
const gpsSignal = computed(() => ({
  value: store.droneState.gps_signal ?? 0
}))

// 图传信号 - 1格红色，2格黄色，3-5格绿色
const linkQuality = computed(() => {
  if (store.droneState.rc_signal === null || store.droneState.rc_signal === undefined) {
    return {
      text: '--',
      level: 0,
      status: 'normal'
    }
  }

  const quality = Math.max(0, Math.min(5, Math.round(store.droneState.rc_signal / 20)))
  let status = 'success' // 绿色
  if (quality === 1) {
    status = 'danger' // 红色
  } else if (quality === 2) {
    status = 'warning' // 黄色
  }

  return {
    text: `${quality}/5`,
    level: quality,
    status
  }
})

// 遥控器电量 - >50%绿色，20-50%黄色，<20%红色
const rcSignal = computed(() => {
  const value = store.droneState.rc_signal
  if (value === null || value === undefined) {
    return {
      text: '--',
      status: 'normal'
    }
  }

  let status = 'success' // 绿色
  if (value < 20) {
    status = 'danger' // 红色
  } else if (value < 50) {
    status = 'warning' // 黄色
  }

  return {
    text: `${value}%`,
    status
  }
})

// 无人机电池 - >50%绿色，20-50%黄色，<20%红色
const droneBattery = computed(() => {
  const value = store.droneState.battery.percent || 0
  let status = 'success' // 绿色
  if (value < 20) {
    status = 'danger' // 红色
  } else if (value < 50) {
    status = 'warning' // 黄色
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
      <!-- 飞行状态 -->
      <div class="status-item">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span class="value" :class="{ active: flightStatus.isFlying }">
          {{ flightStatus.text }}
        </span>
      </div>

      <!-- 图传信号 -->
      <div class="status-item" :class="linkQuality.status">
        <span class="emoji-icon">📶</span>
        <span class="value">{{ linkQuality.text }}</span>
      </div>

      <!-- GPS 卫星 -->
      <div class="status-item">
        <span class="emoji-icon">🛰️</span>
        <span class="value">{{ gpsSignal.value }}</span>
      </div>

      <!-- 遥控器信号 -->
      <div class="status-item" :class="rcSignal.status">
        <span class="emoji-icon">🎮</span>
        <span class="value">{{ rcSignal.text }}</span>
      </div>

      <!-- 无人机电池 -->
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
  font-size: 18px;
  line-height: 1;
  flex-shrink: 0;
  opacity: 0.7;
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

/* 成功状态 - 绿色 */
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

/* 警告状态 - 黄色 */
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

/* 危险状态 - 红色 */
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
