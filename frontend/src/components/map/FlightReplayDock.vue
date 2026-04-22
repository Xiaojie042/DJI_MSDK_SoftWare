<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()
const SEEK_THROTTLE_MS = 80

const sliderValue = ref(0)
const isSeeking = ref(false)
const resumeAfterSeek = ref(false)
const pendingSeekValue = ref(null)
let seekTimer = null

const replayFrame = computed(() => store.activeFlightReplayFrame)
const replayFrames = computed(() => store.activeFlightReplayFrames)
const replayFlight = computed(() => {
  const flightId = store.flightReplay.activeFlightId
  if (!flightId) {
    return null
  }

  return (
    store.flightSessions.find((item) => item.flight_id === flightId) ||
    store.flightSessionDetails[flightId] ||
    null
  )
})

const replayStatusText = computed(() => {
  if (store.flightReplay.status === 'playing') {
    return '播放中'
  }

  if (store.flightReplay.status === 'paused') {
    return '已暂停'
  }

  if (store.flightReplay.status === 'completed') {
    return '已完成'
  }

  return '待播放'
})

const replayActionText = computed(() => {
  if (store.flightReplay.status === 'playing') {
    return '暂停'
  }

  if (store.flightReplay.status === 'completed') {
    return '重播'
  }

  return '播放'
})

const progressMax = computed(() => Math.max(replayFrames.value.length - 1, 0))
const speedOptions = [0.5, 1, 2, 4]

const normalizeSeekValue = (value) => {
  const numeric = Math.round(Number(value) || 0)
  return Math.min(Math.max(numeric, 0), progressMax.value)
}

const syncSliderValue = () => {
  sliderValue.value = normalizeSeekValue(store.flightReplay.frameIndex)
}

const clearSeekTimer = () => {
  if (seekTimer !== null) {
    window.clearTimeout(seekTimer)
    seekTimer = null
  }
}

const commitSeek = (value) => {
  const nextValue = normalizeSeekValue(value)
  pendingSeekValue.value = null
  sliderValue.value = nextValue
  store.seekFlightReplay(nextValue)
}

const flushPendingSeek = () => {
  clearSeekTimer()

  if (pendingSeekValue.value === null) {
    return
  }

  commitSeek(pendingSeekValue.value)
}

const scheduleSeek = (value) => {
  pendingSeekValue.value = normalizeSeekValue(value)

  if (seekTimer !== null) {
    return
  }

  seekTimer = window.setTimeout(() => {
    seekTimer = null
    flushPendingSeek()
  }, SEEK_THROTTLE_MS)
}

watch(
  () => [store.flightReplay.activeFlightId, store.flightReplay.frameIndex, progressMax.value],
  () => {
    if (!isSeeking.value) {
      syncSliderValue()
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  clearSeekTimer()
})

const formatDateTime = (timestamp) => {
  const numeric = Number(timestamp)
  if (!Number.isFinite(numeric)) {
    return '--'
  }

  return new Date(numeric * 1000).toLocaleString('zh-CN', { hour12: false })
}

const formatMetric = (value, digits = 1, unit = '') => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${numeric.toFixed(digits)}${unit}` : `--${unit}`
}

const handleTogglePlay = () => {
  if (!store.flightReplay.activeFlightId) {
    return
  }

  if (store.flightReplay.status === 'playing') {
    store.pauseFlightReplay()
    return
  }

  store.resumeFlightReplay()
}

const handleSeekStart = () => {
  if (isSeeking.value) {
    return
  }

  isSeeking.value = true
  resumeAfterSeek.value = store.flightReplay.status === 'playing'

  if (resumeAfterSeek.value) {
    store.pauseFlightReplay()
  }
}

const handleSeek = (event) => {
  const nextValue = normalizeSeekValue(event.target.value)
  sliderValue.value = nextValue

  if (!isSeeking.value) {
    handleSeekStart()
  }

  scheduleSeek(nextValue)
}

const handleSeekEnd = (event) => {
  const nextValue = normalizeSeekValue(event.target.value)
  pendingSeekValue.value = nextValue
  flushPendingSeek()
  isSeeking.value = false

  if (resumeAfterSeek.value && nextValue < progressMax.value) {
    store.resumeFlightReplay()
  }

  resumeAfterSeek.value = false
}

const handleSpeedChange = (event) => {
  store.setFlightReplaySpeed(event.target.value)
}

const handleCloseReplay = () => {
  clearSeekTimer()
  pendingSeekValue.value = null
  isSeeking.value = false
  resumeAfterSeek.value = false
  sliderValue.value = 0
  store.stopFlightReplay()
}
</script>

<template>
  <section v-if="store.flightReplay.activeFlightId" class="replay-dock glass-panel">
    <header class="replay-dock__header">
      <div class="replay-dock__title">
        <p>数据回放</p>
        <strong>{{ replayFlight?.file_name || store.flightReplay.activeFlightId }}</strong>
      </div>

      <div class="replay-dock__header-actions">
        <div class="replay-status" :class="`replay-status--${store.flightReplay.status}`">
          {{ replayStatusText }}
        </div>

        <button type="button" class="replay-close-btn" @click="handleCloseReplay" aria-label="关闭回放面板">
          &times;
        </button>
      </div>
    </header>

    <p v-if="store.flightReplay.error" class="replay-error">
      {{ store.flightReplay.error }}
    </p>

    <div class="replay-dock__metrics">
      <div>
        <span>时间</span>
        <strong>{{ formatDateTime(replayFrame?.timestamp) }}</strong>
      </div>
      <div>
        <span>高度</span>
        <strong>{{ formatMetric(replayFrame?.position?.altitude, 1, ' m') }}</strong>
      </div>
      <div>
        <span>速度</span>
        <strong>{{ formatMetric(replayFrame?.velocity?.horizontal, 1, ' m/s') }}</strong>
      </div>
    </div>

    <div class="replay-slider">
      <input
        type="range"
        min="0"
        :max="progressMax"
        :value="sliderValue"
        :disabled="progressMax === 0"
        @mousedown="handleSeekStart"
        @touchstart.passive="handleSeekStart"
        @input="handleSeek"
        @change="handleSeekEnd"
      />
      <div class="replay-slider__meta">
        <span>{{ store.activeFlightReplayProgress }}%</span>
        <span>{{ store.flightReplay.frameIndex + 1 }} / {{ replayFrames.length || 0 }}</span>
      </div>
    </div>

    <div class="replay-dock__controls">
      <button type="button" class="replay-btn replay-btn--primary" @click="handleTogglePlay">
        {{ replayActionText }}
      </button>

      <label class="replay-speed">
        <span>倍速</span>
        <select :value="store.flightReplay.speed" @change="handleSpeedChange">
          <option v-for="speed in speedOptions" :key="speed" :value="speed">
            {{ speed }}x
          </option>
        </select>
      </label>
    </div>
  </section>
</template>

<style scoped>
.replay-dock {
  position: absolute;
  left: 1rem;
  bottom: 1rem;
  z-index: 520;
  width: min(420px, calc(100% - 2rem));
  padding: 0.9rem 1rem;
  border-radius: 18px;
  border: 1px solid rgba(251, 191, 36, 0.24);
  background: rgba(15, 23, 42, 0.86);
  backdrop-filter: blur(12px);
  box-shadow: 0 20px 40px rgba(2, 6, 23, 0.28);
}

.replay-dock__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.replay-dock__header-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.replay-dock__title {
  min-width: 0;
}

.replay-dock__title p {
  margin: 0 0 0.18rem;
  color: #fbbf24;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.replay-dock__title strong {
  display: block;
  color: #f8fafc;
  font-size: 0.92rem;
  word-break: break-all;
}

.replay-status {
  min-height: 28px;
  padding: 0 0.7rem;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
}

.replay-close-btn {
  width: 30px;
  height: 30px;
  cursor: pointer;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  background: rgba(30, 41, 59, 0.58);
  color: #cbd5e1;
  font-size: 1rem;
  line-height: 1;
}

.replay-close-btn:hover {
  color: #f8fafc;
  border-color: rgba(248, 250, 252, 0.28);
}

.replay-status--playing {
  background: rgba(34, 197, 94, 0.14);
  color: #86efac;
}

.replay-status--paused,
.replay-status--idle {
  background: rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}

.replay-status--completed {
  background: rgba(56, 189, 248, 0.14);
  color: #7dd3fc;
}

.replay-error {
  margin: 0.6rem 0 0;
  color: #fca5a5;
  font-size: 0.76rem;
}

.replay-dock__metrics {
  margin-top: 0.8rem;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.6rem;
}

.replay-dock__metrics div {
  padding: 0.58rem 0.65rem;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.replay-dock__metrics span,
.replay-speed span {
  display: block;
  margin-bottom: 0.16rem;
  color: #94a3b8;
  font-size: 0.66rem;
}

.replay-dock__metrics strong {
  color: #f8fafc;
  font-size: 0.78rem;
}

.replay-slider {
  margin-top: 0.85rem;
}

.replay-slider input {
  width: 100%;
  accent-color: #fbbf24;
}

.replay-slider__meta {
  margin-top: 0.22rem;
  display: flex;
  justify-content: space-between;
  color: #94a3b8;
  font-size: 0.72rem;
}

.replay-dock__controls {
  margin-top: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.replay-btn,
.replay-speed select {
  min-height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(30, 41, 59, 0.58);
  color: #e2e8f0;
  font-size: 0.76rem;
  font-weight: 600;
}

.replay-btn {
  padding: 0 0.9rem;
}

.replay-btn--primary {
  border-color: rgba(251, 191, 36, 0.3);
  background: rgba(245, 158, 11, 0.16);
  color: #fef3c7;
}

.replay-speed {
  margin-left: auto;
}

.replay-speed select {
  min-width: 74px;
  padding: 0 0.65rem;
}

@media (max-width: 720px) {
  .replay-dock {
    left: 0.75rem;
    right: 0.75rem;
    bottom: 0.75rem;
    width: auto;
  }

  .replay-dock__metrics {
    grid-template-columns: 1fr;
  }

  .replay-dock__controls {
    flex-wrap: wrap;
  }

  .replay-speed {
    margin-left: 0;
    width: 100%;
  }

  .replay-speed select {
    width: 100%;
  }
}
</style>
