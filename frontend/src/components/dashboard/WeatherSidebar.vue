<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()
const INVALID_MARKER = '///'

const displayDroneState = computed(() => store.currentDroneState)
const latestWeatherFrame = computed(() => store.currentWeatherFrame)
const latestVisibilityFrame = computed(() => store.currentVisibilityFrame)
const latestFlightFrame = computed(() => store.currentFlightPayload)

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

const readMetricValue = (...values) => {
  for (const value of values) {
    if (value === INVALID_MARKER || value === '/' || value === null || value === undefined || value === '') {
      continue
    }

    const numeric = Number(value)
    if (Number.isFinite(numeric)) {
      return numeric
    }
  }

  return null
}

const formatMetric = (value, digits = 1, unit = '') => {
  if (!Number.isFinite(value)) {
    return '/'
  }

  return `${value.toFixed(digits)}${unit}`
}

const weatherPayload = computed(() => latestWeatherFrame.value?.parsed_data || {})
const visibilityPayload = computed(() => latestVisibilityFrame.value?.parsed_data || {})

const weather = computed(() => {
  const windDirection = readMetricValue(
    weatherPayload.value.true_wind_direction_deg,
    weatherPayload.value.relative_wind_direction_deg
  )
  const windSpeed = readMetricValue(
    weatherPayload.value.true_wind_speed_ms,
    weatherPayload.value.relative_wind_speed_ms
  )
  const temperature = readMetricValue(weatherPayload.value.temperature_c)
  const humidity = readMetricValue(weatherPayload.value.humidity_percent)
  const pressure = readMetricValue(weatherPayload.value.pressure_hpa)
  const visibility = readMetricValue(
    visibilityPayload.value.visibility_10s_m,
    visibilityPayload.value.visibility_1min_m,
    visibilityPayload.value.visibility_10min_m
  )
  const altitude = readMetricValue(
    readPath(latestFlightFrame.value, 'location.altitude'),
    readPath(latestFlightFrame.value, 'aircraft_status.aircraft_location.altitude'),
    readPath(latestFlightFrame.value, 'position.altitude'),
    latestFlightFrame.value?.altitude,
    displayDroneState.value?.position?.altitude
  )

  return {
    windSpeed,
    windDirection,
    temperature,
    humidity,
    pressure,
    altitude,
    visibility,
    compassAngle: Number.isFinite(windDirection) ? windDirection : 0,
    visibilityPercent: Number.isFinite(visibility) ? Math.min((visibility / 10000) * 100, 100) : 0
  }
})

const detailRows = computed(() => [
  {
    label: '风向',
    value: formatMetric(weather.value.windDirection, 0, '°')
  },
  {
    label: '温度',
    value: formatMetric(weather.value.temperature, 1, ' °C')
  },
  {
    label: '湿度',
    value: formatMetric(weather.value.humidity, 1, ' %')
  },
  {
    label: '气压',
    value: formatMetric(weather.value.pressure, 1, ' hPa')
  },
  {
    label: '海拔高度',
    value: formatMetric(weather.value.altitude, 1, ' m')
  }
])

const visibilityDisplay = computed(() => {
  if (!Number.isFinite(weather.value.visibility)) {
    return '/'
  }

  return `${Math.round(weather.value.visibility)} m`
})
</script>

<template>
  <section class="weather-sidebar glass-panel">
    <div class="compass-section">
      <div class="compass-circle">
        <svg viewBox="0 0 280 280" class="compass-svg" aria-hidden="true">
          <g transform="translate(140, 140)">
            <line
              v-for="tick in 72"
              :key="tick"
              x1="0"
              y1="-135"
              x2="0"
              :y2="tick % 6 === 0 ? -118 : -126"
              :stroke="tick % 6 === 0 ? 'rgba(248,250,252,0.78)' : 'rgba(148,163,184,0.28)'"
              :stroke-width="tick % 6 === 0 ? 2 : 1"
              :transform="`rotate(${tick * 5})`"
            />

            <text x="0" y="-104" text-anchor="middle" fill="var(--primary)" font-size="18" font-weight="700">0</text>
            <text x="0" y="-84" text-anchor="middle" fill="var(--text-muted)" font-size="14">北</text>

            <text x="107" y="6" text-anchor="middle" fill="var(--text-main)" font-size="18" font-weight="700">90</text>
            <text x="84" y="6" text-anchor="middle" fill="var(--text-muted)" font-size="14">东</text>

            <text x="0" y="121" text-anchor="middle" fill="var(--text-main)" font-size="18" font-weight="700">180</text>
            <text x="0" y="98" text-anchor="middle" fill="var(--text-muted)" font-size="14">南</text>

            <text x="-108" y="6" text-anchor="middle" fill="var(--text-main)" font-size="18" font-weight="700">270</text>
            <text x="-84" y="6" text-anchor="middle" fill="var(--text-muted)" font-size="14">西</text>
          </g>
        </svg>

        <div class="needle-wrapper" :style="{ transform: `rotate(${weather.compassAngle}deg)` }">
          <div class="needle-main"></div>
          <div class="needle-tail"></div>
        </div>

        <div class="center-hub">
          <div class="speed-value" :class="{ 'text-danger': Number.isFinite(weather.windSpeed) && weather.windSpeed > 10 }">
            {{ Number.isFinite(weather.windSpeed) ? weather.windSpeed.toFixed(1) : '/' }}
          </div>
          <div class="speed-unit">m/s</div>
        </div>
      </div>
    </div>

    <div class="env-section">
      <div v-for="item in detailRows" :key="item.label" class="data-row">
        <span class="label">{{ item.label }}</span>
        <span class="value">{{ item.value }}</span>
      </div>
    </div>

    <div class="visibility-section">
      <div class="data-row">
        <span class="label">能见度</span>
        <span class="value" :class="{ 'text-danger': Number.isFinite(weather.visibility) && weather.visibility < 1000 }">
          {{ visibilityDisplay }}
        </span>
      </div>
      <div class="progress-container">
        <div
          class="progress-bar"
          :class="{ 'bar-danger': Number.isFinite(weather.visibility) && weather.visibility < 1000 }"
          :style="{ width: `${weather.visibilityPercent}%` }"
        ></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.weather-sidebar {
  --sidebar-height: 596px;
  --compass-size: 232px;

  width: 300px;
  height: var(--sidebar-height);
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-sizing: border-box;
  color: var(--text-main);
  background: var(--bg-panel);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 22px;
  box-shadow: 0 24px 48px rgba(2, 6, 23, 0.3);
}

.compass-section {
  flex: 0 0 238px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.compass-circle {
  position: relative;
  width: var(--compass-size);
  height: var(--compass-size);
  border-radius: 50%;
  background:
    radial-gradient(circle at center, rgba(30, 41, 59, 0.92) 0%, rgba(15, 23, 42, 0.68) 66%, rgba(15, 23, 42, 0.94) 100%);
  box-shadow:
    inset 0 0 20px rgba(15, 23, 42, 0.9),
    0 12px 28px rgba(2, 6, 23, 0.28);
}

.compass-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.needle-wrapper {
  position: absolute;
  inset: 0;
  transition: transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.needle-main {
  position: absolute;
  bottom: 50%;
  left: calc(50% - 2px);
  width: 4px;
  height: 104px;
  border-radius: 999px 999px 0 0;
  background: linear-gradient(180deg, #60a5fa 0%, var(--primary) 100%);
}

.needle-main::after {
  content: '';
  position: absolute;
  top: -12px;
  left: -5px;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-bottom: 14px solid #60a5fa;
}

.needle-tail {
  position: absolute;
  top: 50%;
  left: calc(50% - 1.5px);
  width: 3px;
  height: 80px;
  border-radius: 0 0 999px 999px;
  background: rgba(148, 163, 184, 0.38);
}

.center-hub {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 72px;
  height: 72px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.22);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 2;
  box-shadow: inset 0 0 16px rgba(0, 0, 0, 0.6);
}

.speed-value {
  font-size: 24px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.speed-unit {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.env-section {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  padding: 8px 4px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.data-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.label {
  color: var(--text-muted);
  font-size: 14px;
  letter-spacing: 0.12em;
}

.value {
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.visibility-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 2px;
}

.progress-container {
  width: 100%;
  height: 8px;
  background: rgba(15, 23, 42, 0.56);
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #38bdf8 0%, var(--info) 100%);
  transition: width 0.4s ease;
}

.text-danger {
  color: var(--danger) !important;
}

.bar-danger {
  background: linear-gradient(90deg, #f97316 0%, var(--danger) 100%) !important;
}
</style>
