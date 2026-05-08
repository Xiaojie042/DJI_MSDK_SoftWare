<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import { useDroneStore } from '@/stores/droneStore'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'
import DroneMap from '@/components/map/DroneMap.vue'

useWebSocket()

const store = useDroneStore()

const charts = [
  {
    key: 'temperature',
    title: '温度',
    unit: ' °C',
    color: '#f97316',
    digits: 1
  },
  {
    key: 'humidity',
    title: '湿度',
    unit: ' %',
    color: '#38bdf8',
    min: 0,
    max: 100,
    digits: 1
  },
  {
    key: 'windDirection',
    title: '风向',
    unit: '°',
    color: '#a78bfa',
    min: 0,
    max: 360,
    digits: 0
  },
  {
    key: 'windSpeed',
    title: '风速',
    unit: ' m/s',
    color: '#22c55e',
    digits: 1
  },
  {
    key: 'visibility',
    title: '能见度',
    unit: ' m',
    color: '#60a5fa',
    min: 0,
    digits: 0
  },
  {
    key: 'pressure',
    title: '气压',
    unit: ' hPa',
    color: '#facc15',
    digits: 1
  }
]

const visibleCharts = reactive(Object.fromEntries(charts.map((chart) => [chart.key, true])))
const clearedAtByMetric = reactive(Object.fromEntries(charts.map((chart) => [chart.key, 0])))
const filterOpen = ref(false)
const layoutMode = ref('default')
const splitLayoutRef = ref(null)
const chartPanelRef = ref(null)
const splitPanelWidthPx = ref(null)
const splitPanelLeftPx = ref(null)
const splitPanelTopPx = ref(null)
const isResizing = ref(false)
const isDragging = ref(false)
const series = computed(() => store.weatherTimeSeries)
let dragOffsetX = 0
let dragOffsetY = 0

const latestUpdateText = computed(() => {
  const latest = series.value[series.value.length - 1]
  if (!latest?.timestamp) {
    return '--'
  }

  return new Date(latest.timestamp * 1000).toLocaleString('zh-CN', { hour12: false })
})

const activeMetricCount = computed(() => {
  const latest = [...series.value].reverse()
  const keys = charts.map((chart) => chart.key)
  return keys.filter((key) => latest.some((point) => Number.isFinite(Number(point[key])))).length
})

const visibleMetricCount = computed(() => charts.filter((chart) => visibleCharts[chart.key]).length)
const isSplitMode = computed(() => layoutMode.value === 'split')
const splitPanelStyle = computed(() => ({
  '--chart-panel-width': splitPanelWidthPx.value ? `${splitPanelWidthPx.value}px` : '52%',
  '--chart-panel-left': splitPanelLeftPx.value === null ? 'auto' : `${splitPanelLeftPx.value}px`,
  '--chart-panel-right': splitPanelLeftPx.value === null ? '1rem' : 'auto',
  '--chart-panel-top': splitPanelTopPx.value === null ? '1rem' : `${splitPanelTopPx.value}px`
}))

function setLayoutMode(mode) {
  layoutMode.value = mode
  filterOpen.value = false
}

function getLatestMetricTimestamp(metricKey) {
  for (let index = series.value.length - 1; index >= 0; index -= 1) {
    const point = series.value[index]
    const timestamp = Number(point?.timestamp)
    const value = Number(point?.[metricKey])

    if (Number.isFinite(timestamp) && Number.isFinite(value)) {
      return timestamp
    }
  }

  return null
}

function clearChart(metricKey) {
  // 只重置当前图表的显示窗口，实时数据源和其它物理量曲线继续保持。
  clearedAtByMetric[metricKey] = (getLatestMetricTimestamp(metricKey) ?? Date.now() / 1000) + 0.001
}

function clampPanelWidth(width, containerWidth) {
  const minWidth = Math.min(520, containerWidth - 16)
  return Math.min(Math.max(width, minWidth), containerWidth * 0.72)
}

function getPanelWidth(containerWidth) {
  return splitPanelWidthPx.value ?? clampPanelWidth(containerWidth * 0.52, containerWidth)
}

function clampPanelPosition(left, top, panelWidth, panelHeight, containerWidth, containerHeight) {
  return {
    left: Math.min(Math.max(left, 8), Math.max(8, containerWidth - panelWidth - 8)),
    top: Math.min(Math.max(top, 8), Math.max(8, containerHeight - panelHeight - 8))
  }
}

function updatePanelWidth(event) {
  const container = splitLayoutRef.value
  if (!container) {
    return
  }

  const rect = container.getBoundingClientRect()
  const pointerX = event.clientX - rect.left
  const currentWidth = getPanelWidth(rect.width)
  const panelRight = splitPanelLeftPx.value === null
    ? rect.width - 16
    : splitPanelLeftPx.value + currentWidth
  const nextWidth = clampPanelWidth(panelRight - pointerX, rect.width)

  splitPanelWidthPx.value = nextWidth
  if (splitPanelLeftPx.value !== null) {
    splitPanelLeftPx.value = clampPanelPosition(
      panelRight - nextWidth,
      splitPanelTopPx.value ?? 16,
      nextWidth,
      chartPanelRef.value?.offsetHeight ?? 0,
      rect.width,
      rect.height
    ).left
  }
}

function stopPanelResize() {
  if (!isResizing.value) {
    return
  }

  isResizing.value = false
  window.removeEventListener('pointermove', updatePanelWidth)
  window.removeEventListener('pointerup', stopPanelResize)
}

function startPanelResize(event) {
  if (!isSplitMode.value) {
    return
  }

  event.preventDefault()
  filterOpen.value = false
  isResizing.value = true
  updatePanelWidth(event)
  window.addEventListener('pointermove', updatePanelWidth)
  window.addEventListener('pointerup', stopPanelResize)
}

function updatePanelPosition(event) {
  const container = splitLayoutRef.value
  const panel = chartPanelRef.value
  if (!container || !panel) {
    return
  }

  const rect = container.getBoundingClientRect()
  const panelWidth = panel.offsetWidth
  const panelHeight = panel.offsetHeight
  const nextPosition = clampPanelPosition(
    event.clientX - rect.left - dragOffsetX,
    event.clientY - rect.top - dragOffsetY,
    panelWidth,
    panelHeight,
    rect.width,
    rect.height
  )

  splitPanelLeftPx.value = nextPosition.left
  splitPanelTopPx.value = nextPosition.top
}

function stopPanelDrag() {
  if (!isDragging.value) {
    return
  }

  isDragging.value = false
  window.removeEventListener('pointermove', updatePanelPosition)
  window.removeEventListener('pointerup', stopPanelDrag)
}

function startPanelDrag(event) {
  if (!isSplitMode.value) {
    return
  }

  const interactiveTarget = event.target.closest('button, a, input, label, .metric-filter__menu, .split-resizer')
  if (interactiveTarget) {
    return
  }

  const container = splitLayoutRef.value
  const panel = chartPanelRef.value
  if (!container || !panel) {
    return
  }

  event.preventDefault()
  filterOpen.value = false
  isDragging.value = true

  const rect = container.getBoundingClientRect()
  const currentWidth = panel.offsetWidth
  const currentHeight = panel.offsetHeight
  const currentLeft = splitPanelLeftPx.value ?? rect.width - currentWidth - 16
  const currentTop = splitPanelTopPx.value ?? 16
  const currentPosition = clampPanelPosition(currentLeft, currentTop, currentWidth, currentHeight, rect.width, rect.height)

  splitPanelLeftPx.value = currentPosition.left
  splitPanelTopPx.value = currentPosition.top
  dragOffsetX = event.clientX - rect.left - currentPosition.left
  dragOffsetY = event.clientY - rect.top - currentPosition.top

  window.addEventListener('pointermove', updatePanelPosition)
  window.addEventListener('pointerup', stopPanelDrag)
}

onBeforeUnmount(() => {
  stopPanelResize()
  stopPanelDrag()
})
</script>

<template>
  <main
    class="weather-charts-page"
    :class="{ 'is-split': isSplitMode, 'is-resizing': isResizing, 'is-dragging': isDragging }"
  >
    <header v-if="!isSplitMode" class="weather-toolbar glass-panel">
      <div class="weather-toolbar__copy">
        <span>Weather telemetry</span>
        <strong>气象数据图表</strong>
      </div>

      <div class="metric-switches-inline" aria-label="图表显示控制">
        <label
          v-for="chart in charts"
          :key="`${chart.key}-inline-toggle`"
          class="metric-switch metric-switch--inline"
          :class="{ 'is-active': visibleCharts[chart.key] }"
          :style="{ '--metric-color': chart.color }"
        >
          <input v-model="visibleCharts[chart.key]" type="checkbox" />
          <span class="metric-switch__track" aria-hidden="true">
            <span class="metric-switch__thumb"></span>
          </span>
          <span>{{ chart.title }}</span>
        </label>
      </div>

      <div class="weather-toolbar__status">
        <div>
          <span>连接</span>
          <strong :class="{ online: store.isConnected }">{{ store.isConnected ? '在线' : '离线' }}</strong>
        </div>
        <div>
          <span>物理量</span>
          <strong>{{ activeMetricCount }}/6</strong>
        </div>
        <div>
          <span>显示</span>
          <strong>{{ visibleMetricCount }}/6</strong>
        </div>
        <div>
          <span>最近更新</span>
          <strong>{{ latestUpdateText }}</strong>
        </div>
      </div>

      <div class="weather-toolbar__actions">
        <div class="layout-segment" aria-label="布局模式切换">
          <button
            type="button"
            :class="{ active: !isSplitMode }"
            @click="setLayoutMode('default')"
          >
            默认
          </button>
          <button
            type="button"
            :class="{ active: isSplitMode }"
            @click="setLayoutMode('split')"
          >
            滑窗
          </button>
        </div>

        <RouterLink class="back-link" to="/">返回地图</RouterLink>
      </div>
    </header>

    <section ref="splitLayoutRef" class="weather-content" :style="splitPanelStyle">
      <section v-if="isSplitMode" class="weather-map-stage glass-panel">
        <DroneMap />
      </section>

      <section
        ref="chartPanelRef"
        class="chart-panel"
        :class="{ 'glass-panel': isSplitMode }"
      >
        <header v-if="isSplitMode" class="weather-toolbar weather-toolbar--panel" @pointerdown="startPanelDrag">
          <div class="weather-toolbar__copy">
            <span>Weather telemetry</span>
            <strong>气象数据图表</strong>
          </div>

          <div class="weather-toolbar__status">
            <div>
              <span>连接</span>
              <strong :class="{ online: store.isConnected }">{{ store.isConnected ? '在线' : '离线' }}</strong>
            </div>
            <div>
              <span>物理量</span>
              <strong>{{ activeMetricCount }}/6</strong>
            </div>
            <div>
              <span>显示</span>
              <strong>{{ visibleMetricCount }}/6</strong>
            </div>
            <div>
              <span>最近更新</span>
              <strong>{{ latestUpdateText }}</strong>
            </div>
          </div>

          <div class="weather-toolbar__actions" @pointerdown.stop>
            <div class="metric-filter" :class="{ 'is-open': filterOpen }">
              <button class="toolbar-button" type="button" @click="filterOpen = !filterOpen">
                图表筛选 {{ visibleMetricCount }}/6
              </button>

              <div v-if="filterOpen" class="metric-filter__menu" @keyup.esc="filterOpen = false">
                <label
                  v-for="chart in charts"
                  :key="`${chart.key}-panel-toggle`"
                  class="metric-switch"
                  :class="{ 'is-active': visibleCharts[chart.key] }"
                  :style="{ '--metric-color': chart.color }"
                >
                  <input v-model="visibleCharts[chart.key]" type="checkbox" />
                  <span class="metric-switch__track" aria-hidden="true">
                    <span class="metric-switch__thumb"></span>
                  </span>
                  <span>{{ chart.title }}</span>
                </label>
              </div>
            </div>

            <div class="layout-segment" aria-label="布局模式切换">
              <button
                type="button"
                :class="{ active: !isSplitMode }"
                @click="setLayoutMode('default')"
              >
                默认
              </button>
              <button
                type="button"
                :class="{ active: isSplitMode }"
                @click="setLayoutMode('split')"
              >
                滑窗
              </button>
            </div>

            <RouterLink class="back-link" to="/">返回地图</RouterLink>
          </div>
        </header>

        <div
          v-if="isSplitMode"
          class="split-resizer"
          role="separator"
          aria-label="调整图表滑窗宽度"
          aria-orientation="vertical"
          @pointerdown.stop="startPanelResize"
        ></div>

        <div class="chart-grid">
          <TimeSeriesChart
            v-for="chart in charts"
            :key="chart.key"
            v-show="visibleCharts[chart.key]"
            :title="chart.title"
            :unit="chart.unit"
            :metric-key="chart.key"
            :points="series"
            :color="chart.color"
            :min="chart.min ?? null"
            :max="chart.max ?? null"
            :digits="chart.digits"
            :clear-after="clearedAtByMetric[chart.key]"
            @clear="clearChart(chart.key)"
          />
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped>
.weather-charts-page {
  --chart-panel-width: 40%;
  --chart-panel-left: auto;
  --chart-panel-right: 1rem;
  --chart-panel-top: 1rem;

  height: 100vh;
  min-height: 0;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.1), transparent 28%),
    radial-gradient(circle at top right, rgba(34, 197, 94, 0.08), transparent 25%),
    #020617;
}

.weather-charts-page.is-split {
  padding: 0;
  gap: 0;
  overflow: hidden;
}

.weather-charts-page.is-resizing {
  cursor: col-resize;
  user-select: none;
}

.weather-charts-page.is-dragging {
  cursor: move;
  user-select: none;
}

.weather-toolbar {
  position: relative;
  flex: 0 0 auto;
  min-height: 72px;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 18px;
}

.weather-toolbar__copy {
  flex: 1 1 220px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
}

.weather-toolbar__copy span,
.weather-toolbar__status span {
  color: #94a3b8;
  font-size: 0.72rem;
}

.weather-toolbar__copy strong {
  color: #f8fafc;
  font-size: 1.28rem;
}

.weather-toolbar__status {
  flex: 0 1 auto;
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.weather-toolbar__status div {
  min-width: 82px;
  padding: 0.48rem 0.65rem;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.54);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.weather-toolbar__status strong {
  display: block;
  margin-top: 0.12rem;
  color: #e2e8f0;
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
}

.weather-toolbar__status strong.online {
  color: #86efac;
}

.weather-toolbar--panel {
  min-height: 0;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 0.7rem;
  padding: 0.2rem 0.2rem 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 0;
  cursor: move;
}

.weather-toolbar--panel .weather-toolbar__copy {
  flex: 1 1 180px;
}

.weather-toolbar--panel .weather-toolbar__copy strong {
  font-size: 1.08rem;
}

.weather-toolbar--panel .weather-toolbar__status {
  order: 3;
  width: 100%;
  flex-wrap: wrap;
}

.weather-toolbar--panel .weather-toolbar__status div {
  min-width: 76px;
  flex: 1 1 88px;
  padding: 0.42rem 0.55rem;
}

.weather-toolbar__actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.55rem;
}

.toolbar-button,
.back-link,
.layout-segment button {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 0.82rem;
  font-weight: 700;
  white-space: nowrap;
}

.toolbar-button {
  padding: 0 0.9rem;
  border: 1px solid rgba(125, 211, 252, 0.2);
  background: rgba(15, 23, 42, 0.58);
  color: #e0f2fe;
}

.toolbar-button:hover {
  border-color: rgba(125, 211, 252, 0.36);
  background: rgba(14, 165, 233, 0.15);
}

.back-link {
  padding: 0 0.9rem;
  border-radius: 8px;
  border: 1px solid rgba(125, 211, 252, 0.24);
  background: rgba(14, 165, 233, 0.14);
  color: #e0f2fe;
  text-decoration: none;
}

.layout-segment {
  height: 36px;
  display: flex;
  padding: 3px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.56);
}

.layout-segment button {
  min-height: 28px;
  padding: 0 0.68rem;
  border: 0;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
}

.layout-segment button.active {
  background: rgba(14, 165, 233, 0.18);
  color: #e0f2fe;
}

.metric-filter {
  position: relative;
}

.metric-switches-inline {
  flex: 0 0 344px;
  display: grid;
  grid-template-columns: repeat(3, minmax(92px, 1fr));
  gap: 0.38rem;
}

.metric-filter__menu {
  position: absolute;
  top: calc(100% + 0.5rem);
  right: 0;
  z-index: 20;
  width: min(320px, calc(100vw - 2rem));
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.48rem;
  padding: 0.65rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.96);
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.45);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.metric-switch {
  --metric-color: #38bdf8;

  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.35rem 0.58rem;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.46);
  color: #cbd5e1;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease;
}

.metric-switch--inline {
  min-height: 28px;
  gap: 0.35rem;
  padding: 0.24rem 0.42rem;
  font-size: 0.72rem;
}

.metric-switch--inline .metric-switch__track {
  width: 30px;
  height: 16px;
  flex-basis: 30px;
}

.metric-switch--inline .metric-switch__thumb {
  width: 10px;
  height: 10px;
}

.metric-switch--inline.is-active .metric-switch__thumb {
  transform: translateX(14px);
}

.metric-switch input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.metric-switch:focus-within {
  outline: 2px solid rgba(125, 211, 252, 0.32);
  outline-offset: 2px;
}

.metric-switch.is-active {
  border-color: color-mix(in srgb, var(--metric-color) 54%, rgba(148, 163, 184, 0.18));
  background: rgba(15, 23, 42, 0.62);
  color: #f8fafc;
}

.metric-switch__track {
  position: relative;
  width: 34px;
  height: 18px;
  flex: 0 0 34px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(30, 41, 59, 0.9);
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
}

.metric-switch__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: #94a3b8;
  transition:
    transform 0.2s ease,
    background 0.2s ease;
}

.metric-switch.is-active .metric-switch__track {
  border-color: color-mix(in srgb, var(--metric-color) 72%, transparent);
  background: rgba(14, 165, 233, 0.16);
}

.metric-switch.is-active .metric-switch__thumb {
  transform: translateX(16px);
  background: var(--metric-color);
}

.weather-content {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  transition:
    grid-template-columns 0.28s ease,
    opacity 0.2s ease;
}

.weather-charts-page:not(.is-split) .weather-content {
  display: block;
}

.weather-charts-page.is-split .weather-content {
  display: block;
  overflow: hidden;
}

.weather-map-stage {
  position: absolute;
  inset: 0;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border-radius: 0;
  border-color: rgba(59, 130, 246, 0.2);
}

.split-resizer {
  position: absolute;
  top: 0;
  left: -8px;
  bottom: 0;
  z-index: 18;
  min-width: 12px;
  width: 12px;
  cursor: col-resize;
  touch-action: none;
}

.split-resizer::before {
  content: '';
  position: absolute;
  top: 16px;
  bottom: 16px;
  left: 50%;
  width: 2px;
  transform: translateX(-50%);
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.22);
  transition:
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.split-resizer:hover::before,
.weather-charts-page.is-resizing .split-resizer::before {
  background: rgba(125, 211, 252, 0.65);
  box-shadow: 0 0 18px rgba(14, 165, 233, 0.28);
}

.chart-panel {
  min-width: 0;
  min-height: 0;
}

.weather-charts-page.is-split .chart-panel {
  position: absolute;
  top: var(--chart-panel-top);
  left: var(--chart-panel-left);
  right: var(--chart-panel-right);
  z-index: 16;
  width: var(--chart-panel-width);
  height: min(760px, calc(100% - 2rem));
  min-width: 520px;
  max-width: 72%;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  overflow: visible;
  border-radius: 18px;
  box-shadow: 0 22px 54px rgba(2, 6, 23, 0.46);
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 1rem;
  padding-bottom: 0.25rem;
}

.weather-charts-page.is-split .chart-grid {
  flex: 1 1 auto;
  grid-template-columns: minmax(0, 1fr);
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.75rem 0.15rem 0.2rem 0;
}

.weather-charts-page:not(.is-split) .chart-grid {
  max-width: 1360px;
  margin: 0 auto;
}

@media (max-width: 1320px) {
  .weather-toolbar {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .metric-switches-inline {
    order: 3;
    flex: 0 1 420px;
  }

  .weather-toolbar__status {
    flex-wrap: wrap;
  }
}

@media (max-width: 1100px) {
  .weather-toolbar {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .weather-toolbar__status {
    order: 4;
    width: 100%;
    flex-wrap: wrap;
  }

  .weather-toolbar__actions {
    margin-left: auto;
  }
}

@media (max-width: 920px) {
  .weather-charts-page.is-split {
    padding: 0.75rem;
    overflow-y: auto;
  }

  .weather-charts-page.is-split .weather-content {
    display: block;
    overflow: visible;
  }

  .weather-map-stage {
    position: relative;
    min-height: 260px;
    border-radius: 18px;
  }

  .split-resizer {
    display: none;
  }

  .weather-charts-page.is-split .chart-panel {
    position: relative;
    width: auto;
    min-width: 0;
    max-width: none;
    height: auto;
    top: auto;
    left: auto;
    right: auto;
    margin-top: 1rem;
    overflow: visible;
    border-radius: 18px;
  }

  .weather-toolbar--panel {
    cursor: default;
  }

  .weather-charts-page.is-split .chart-grid {
    overflow: visible;
  }
}

@media (max-width: 820px) {
  .weather-charts-page {
    padding: 0.75rem;
  }

  .weather-toolbar__actions {
    width: 100%;
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .metric-filter {
    flex: 1 1 180px;
  }

  .metric-switches-inline {
    width: 100%;
    flex: 1 1 100%;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .toolbar-button {
    width: 100%;
  }

  .weather-toolbar__status div {
    flex: 1 1 130px;
  }

  .chart-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .metric-filter__menu {
    left: 0;
    right: auto;
  }

  .layout-segment {
    flex: 1 1 150px;
  }

  .layout-segment button {
    flex: 1 1 50%;
  }
}
</style>
