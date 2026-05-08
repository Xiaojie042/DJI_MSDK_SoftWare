<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  unit: {
    type: String,
    default: ''
  },
  points: {
    type: Array,
    default: () => []
  },
  metricKey: {
    type: String,
    required: true
  },
  color: {
    type: String,
    default: '#38bdf8'
  },
  min: {
    type: Number,
    default: null
  },
  max: {
    type: Number,
    default: null
  },
  digits: {
    type: Number,
    default: 1
  },
  clearAfter: {
    type: Number,
    default: 0
  }
})

defineEmits(['clear'])

const CHART_WIDTH = 640
const CHART_HEIGHT = 220
const PADDING = {
  top: 18,
  right: 18,
  bottom: 28,
  left: 46
}

const chartWidth = CHART_WIDTH - PADDING.left - PADDING.right
const chartHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom

const series = computed(() =>
  props.points
    .map((point) => ({
      id: point.id || `${point.timestamp}-${props.metricKey}`,
      timestamp: Number(point.timestamp),
      value: Number(point[props.metricKey]),
      timeLabel: point.timeLabel || ''
    }))
    .filter((point) =>
      Number.isFinite(point.timestamp) &&
      Number.isFinite(point.value) &&
      point.timestamp >= props.clearAfter
    )
    .sort((left, right) => left.timestamp - right.timestamp)
)

const latestPoint = computed(() => series.value[series.value.length - 1] || null)
const hasData = computed(() => series.value.length > 0)

const xRange = computed(() => {
  if (!hasData.value) {
    return [0, 1]
  }

  const first = series.value[0].timestamp
  const last = series.value[series.value.length - 1].timestamp
  return first === last ? [first - 30, last + 30] : [first, last]
})

const yRange = computed(() => {
  if (!hasData.value) {
    return [0, 1]
  }

  const values = series.value.map((point) => point.value)
  let min = props.min ?? Math.min(...values)
  let max = props.max ?? Math.max(...values)

  if (min === max) {
    min -= 1
    max += 1
  } else if (props.min === null || props.max === null) {
    const padding = (max - min) * 0.12
    min = props.min ?? min - padding
    max = props.max ?? max + padding
  }

  return [min, max]
})

const toX = (timestamp) => {
  const [min, max] = xRange.value
  return PADDING.left + ((timestamp - min) / (max - min)) * chartWidth
}

const toY = (value) => {
  const [min, max] = yRange.value
  return PADDING.top + (1 - (value - min) / (max - min)) * chartHeight
}

const linePath = computed(() => {
  if (!hasData.value) {
    return ''
  }

  return series.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${toX(point.timestamp).toFixed(2)} ${toY(point.value).toFixed(2)}`)
    .join(' ')
})

const areaPath = computed(() => {
  if (!linePath.value || !series.value.length) {
    return ''
  }

  const first = series.value[0]
  const last = series.value[series.value.length - 1]
  const baseY = PADDING.top + chartHeight
  return `${linePath.value} L ${toX(last.timestamp).toFixed(2)} ${baseY} L ${toX(first.timestamp).toFixed(2)} ${baseY} Z`
})

const gridLines = computed(() => {
  const [min, max] = yRange.value
  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = max - (max - min) * ratio
    const y = PADDING.top + chartHeight * ratio
    return {
      y,
      label: formatNumber(value)
    }
  })
})

const xLabels = computed(() => {
  if (!hasData.value) {
    return []
  }

  const first = series.value[0]
  const last = series.value[series.value.length - 1]
  if (first.timestamp === last.timestamp) {
    return [{ x: PADDING.left + chartWidth / 2, label: first.timeLabel }]
  }

  return [
    { x: PADDING.left, label: first.timeLabel },
    { x: PADDING.left + chartWidth, label: last.timeLabel }
  ]
})

function formatNumber(value) {
  return Number.isFinite(value) ? value.toFixed(props.digits) : '--'
}

const latestText = computed(() => {
  if (!latestPoint.value) {
    return '--'
  }

  return `${formatNumber(latestPoint.value.value)}${props.unit}`
})
</script>

<template>
  <article class="chart-card">
    <header class="chart-card__header">
      <div>
        <span>{{ title }}</span>
        <strong>{{ latestText }}</strong>
      </div>

      <div class="chart-card__tools">
        <em>{{ series.length }} 点</em>
        <button
          class="chart-card__clear"
          type="button"
          :disabled="!hasData"
          title="清除当前曲线"
          aria-label="清除当前曲线"
          @click="$emit('clear')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M16.7 3.9 21 8.2 10.2 19H4.9L3 17.1 16.7 3.9Z" />
            <path d="M13.7 6.9 18 11.2" />
            <path d="M4.9 19H21" />
          </svg>
        </button>
      </div>
    </header>

    <div class="chart-card__canvas">
      <svg :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`" preserveAspectRatio="none" role="img">
        <defs>
          <linearGradient :id="`${metricKey}-area`" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" :stop-color="color" stop-opacity="0.26" />
            <stop offset="100%" :stop-color="color" stop-opacity="0.02" />
          </linearGradient>
        </defs>

        <g class="chart-grid">
          <line
            v-for="line in gridLines"
            :key="line.y"
            :x1="PADDING.left"
            :x2="CHART_WIDTH - PADDING.right"
            :y1="line.y"
            :y2="line.y"
          />
          <text
            v-for="line in gridLines"
            :key="`${line.y}-label`"
            :x="PADDING.left - 10"
            :y="line.y + 4"
            text-anchor="end"
          >
            {{ line.label }}
          </text>
        </g>

        <path v-if="areaPath" :d="areaPath" :fill="`url(#${metricKey}-area)`" />
        <path v-if="linePath" :d="linePath" class="chart-line" :stroke="color" />
        <circle
          v-if="latestPoint"
          :cx="toX(latestPoint.timestamp)"
          :cy="toY(latestPoint.value)"
          r="4"
          :fill="color"
        />

        <g class="chart-axis">
          <line :x1="PADDING.left" :x2="CHART_WIDTH - PADDING.right" :y1="CHART_HEIGHT - PADDING.bottom" :y2="CHART_HEIGHT - PADDING.bottom" />
          <text
            v-for="label in xLabels"
            :key="label.x"
            :x="label.x"
            :y="CHART_HEIGHT - 8"
            :text-anchor="label.x === PADDING.left ? 'start' : label.x === PADDING.left + chartWidth ? 'end' : 'middle'"
          >
            {{ label.label }}
          </text>
        </g>
      </svg>

      <div v-if="!hasData" class="chart-card__empty">
        暂无数据
      </div>
    </div>
  </article>
</template>

<style scoped>
.chart-card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.72);
  overflow: hidden;
}

.chart-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.9rem 1rem 0.2rem;
}

.chart-card__header > div:first-child {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.16rem;
}

.chart-card__header span,
.chart-card__header em {
  color: #94a3b8;
  font-size: 0.74rem;
  font-style: normal;
}

.chart-card__header strong {
  color: #f8fafc;
  font-size: 1.18rem;
  font-variant-numeric: tabular-nums;
}

.chart-card__tools {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 0.45rem;
  flex: 0 0 auto;
}

.chart-card__clear {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.5);
  color: #cbd5e1;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease,
    opacity 0.2s ease;
}

.chart-card__clear:hover:not(:disabled) {
  border-color: rgba(125, 211, 252, 0.34);
  background: rgba(14, 165, 233, 0.16);
  color: #e0f2fe;
}

.chart-card__clear:disabled {
  cursor: not-allowed;
  opacity: 0.38;
}

.chart-card__clear svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-card__canvas {
  position: relative;
  min-height: 210px;
  padding: 0.2rem 0.65rem 0.65rem;
}

.chart-card__canvas svg {
  width: 100%;
  height: 220px;
  display: block;
}

.chart-grid line,
.chart-axis line {
  stroke: rgba(148, 163, 184, 0.14);
  stroke-width: 1;
}

.chart-grid text,
.chart-axis text {
  fill: #64748b;
  font-size: 11px;
}

.chart-line {
  fill: none;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-card__empty {
  position: absolute;
  inset: 0.2rem 0.65rem 0.65rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 0.82rem;
}
</style>
