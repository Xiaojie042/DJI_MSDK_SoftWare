<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const store = useDroneStore()

const records = computed(() => store.flightSessions)
const selectedIds = computed(() => new Set(store.selectedFlightSessionIds))
const selectedCount = computed(() => store.selectedFlightSessionIds.length)
const replayFlightId = computed(() => store.flightReplay.activeFlightId)
const replayStatus = computed(() => store.flightReplay.status)

const formatDateTime = (timestamp) => {
  if (timestamp === null || timestamp === undefined) {
    return '--'
  }

  const date = new Date(Number(timestamp) * 1000)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }

  return date.toLocaleString('zh-CN', { hour12: false })
}

const formatDistance = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '--'
  }

  return numeric >= 1000 ? `${(numeric / 1000).toFixed(2)} km` : `${numeric.toFixed(0)} m`
}

const formatAltitude = (value) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)} m` : '--'
}

const isSelected = (flightId) => selectedIds.value.has(flightId)
const isDeleting = (flightId) => store.flightSessionsDeletingIds.includes(flightId)

const handleToggle = async (flightId) => {
  try {
    await store.toggleFlightSessionSelection(flightId)
  } catch (error) {
    store.flightSessionsError = '历史轨迹加载失败'
    console.warn(`Failed to toggle flight session ${flightId}:`, error)
  }
}

const handleRefresh = async () => {
  await store.fetchFlightSessions(true)
}

const handleDelete = async (flightId, fileName) => {
  const confirmed = window.confirm(`确认删除历史架次 ${fileName || flightId} 吗？`)
  if (!confirmed) {
    return
  }

  await store.deleteFlightSession(flightId)
}

const handleDeleteSelected = async () => {
  if (!selectedCount.value) {
    return
  }

  const confirmed = window.confirm(`确认删除已选中的 ${selectedCount.value} 个历史架次吗？`)
  if (!confirmed) {
    return
  }

  await store.deleteSelectedFlightSessions()
}

const handleShowSelected = () => {
  if (!selectedCount.value) {
    return
  }

  store.closeFlightHistoryPanel()
}

const isReplayTarget = (flightId) => replayFlightId.value === flightId

const replayButtonText = (flightId) => {
  if (!isReplayTarget(flightId)) {
    return '开始回放'
  }

  if (replayStatus.value === 'playing') {
    return '回放中'
  }

  if (replayStatus.value === 'paused') {
    return '继续回放'
  }

  if (replayStatus.value === 'completed') {
    return '重新回放'
  }

  return '开始回放'
}

const handleReplay = async (flightId) => {
  try {
    if (isReplayTarget(flightId) && replayStatus.value === 'playing') {
      store.pauseFlightReplay()
      return
    }

    if (isReplayTarget(flightId) && ['paused', 'completed'].includes(replayStatus.value)) {
      store.resumeFlightReplay()
    } else {
      await store.startFlightReplay(flightId)
    }

    store.closeFlightHistoryPanel()
  } catch (error) {
    store.flightSessionsError = '历史架次回放启动失败'
    console.warn(`Failed to start replay for flight session ${flightId}:`, error)
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="store.flightHistoryPanelOpen"
      class="history-overlay"
      @click.self="store.closeFlightHistoryPanel()"
    >
      <section class="history-modal glass-panel">
        <header class="history-header">
          <div class="history-header__copy">
            <p class="history-eyebrow">航迹管理</p>
            <strong>历史架次面板</strong>
            <span>点击卡片可叠加显示历史轨迹，支持多选与删除。</span>
          </div>

          <button
            type="button"
            class="history-close"
            @click="store.closeFlightHistoryPanel()"
            aria-label="关闭历史架次面板"
          >
            &times;
          </button>
        </header>

        <div class="history-toolbar">
          <div class="history-toolbar__meta">
            <span>历史架次 {{ records.length }} 条</span>
            <span>已选中 {{ selectedCount }} 条</span>
            <span v-if="replayFlightId">回放目标 {{ replayFlightId }}</span>
          </div>

          <div class="history-toolbar__actions">
            <button type="button" class="toolbar-btn" @click="handleRefresh" :disabled="store.flightSessionsLoading">
              刷新列表
            </button>
            <button
              type="button"
              class="toolbar-btn"
              @click="store.clearSelectedFlightSessions()"
              :disabled="selectedCount === 0"
            >
              取消选中
            </button>
            <button
              type="button"
              class="toolbar-btn toolbar-btn--accent"
              @click="handleShowSelected"
              :disabled="selectedCount === 0"
            >
              显示选中的航迹
            </button>
            <button
              type="button"
              class="toolbar-btn toolbar-btn--danger"
              @click="handleDeleteSelected"
              :disabled="selectedCount === 0"
            >
              删除选中
            </button>
            <button
              type="button"
              class="toolbar-btn toolbar-btn--accent"
              @click="store.stopFlightReplay()"
              :disabled="!replayFlightId"
            >
              停止回放
            </button>
          </div>
        </div>

        <p v-if="store.flightSessionsError" class="history-error">
          {{ store.flightSessionsError }}
        </p>

        <div class="history-body">
          <div v-if="store.flightSessionsLoading" class="history-empty">
            正在加载历史架次...
          </div>

          <div v-else-if="records.length === 0" class="history-empty">
            暂无历史架次数据
          </div>

          <div v-else class="history-list">
            <article
              v-for="record in records"
              :key="record.flight_id"
              class="history-card"
              :class="{ 'history-card--selected': isSelected(record.flight_id) }"
              @click="handleToggle(record.flight_id)"
            >
              <label class="history-card__check" @click.stop>
                <input
                  type="checkbox"
                  :checked="isSelected(record.flight_id)"
                  @change="handleToggle(record.flight_id)"
                />
                <span></span>
              </label>

              <div class="history-card__content">
                <div class="history-card__header">
                  <div class="history-card__title">
                    <strong>{{ record.file_name }}</strong>
                    <span>{{ record.drone_id || '未知无人机' }}</span>
                  </div>

                  <div class="history-card__actions">
                    <button
                      type="button"
                      class="history-card__replay"
                      :class="{ 'history-card__replay--active': isReplayTarget(record.flight_id) }"
                      @click.stop="handleReplay(record.flight_id)"
                    >
                      {{ replayButtonText(record.flight_id) }}
                    </button>
                    <button
                      type="button"
                      class="history-card__delete"
                      :disabled="isDeleting(record.flight_id)"
                      @click.stop="handleDelete(record.flight_id, record.file_name)"
                    >
                      {{ isDeleting(record.flight_id) ? '删除中...' : '删除' }}
                    </button>
                  </div>
                </div>

                <div class="history-card__metrics">
                  <div class="metric">
                    <span>起飞时间</span>
                    <strong>{{ formatDateTime(record.takeoff_time) }}</strong>
                  </div>
                  <div class="metric">
                    <span>降落时间</span>
                    <strong>{{ formatDateTime(record.landing_time) }}</strong>
                  </div>
                  <div class="metric">
                    <span>总里程</span>
                    <strong>{{ formatDistance(record.total_distance_m) }}</strong>
                  </div>
                  <div class="metric">
                    <span>最大高度</span>
                    <strong>{{ formatAltitude(record.max_altitude_m) }}</strong>
                  </div>
                </div>

                <div class="history-card__devices">
                  <span class="devices-label">气象设备</span>
                  <div v-if="record.attached_weather_devices.length" class="device-tags">
                    <span
                      v-for="device in record.attached_weather_devices"
                      :key="`${record.flight_id}-${device.payload_index}-${device.device_type}`"
                      class="device-tag"
                    >
                      {{ device.payload_index }} / {{ device.device_type }}
                    </span>
                  </div>
                  <span v-else class="device-empty">无</span>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.history-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
  background: rgba(2, 6, 23, 0.46);
  backdrop-filter: blur(10px);
}

.history-modal {
  width: min(960px, calc(100vw - 2.5rem));
  height: min(78vh, 760px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 24px;
  background: var(--bg-panel);
  backdrop-filter: var(--glass-blur);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 24px 60px rgba(2, 6, 23, 0.44);
}

.history-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.2rem 1.25rem 1rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.history-header__copy {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.history-header__copy strong {
  color: #f8fafc;
  font-size: 1.08rem;
}

.history-header__copy span {
  color: #94a3b8;
  font-size: 0.78rem;
}

.history-eyebrow {
  margin: 0;
  color: #7dd3fc;
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.history-close {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(30, 41, 59, 0.82);
  color: #f8fafc;
  font-size: 1.4rem;
  line-height: 1;
}

.history-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(15, 23, 42, 0.34);
}

.history-toolbar__meta,
.history-toolbar__actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.history-toolbar__meta span {
  color: #94a3b8;
  font-size: 0.78rem;
}

.toolbar-btn {
  min-height: 34px;
  padding: 0 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(125, 211, 252, 0.2);
  background: rgba(14, 165, 233, 0.12);
  color: #e0f2fe;
  font-size: 0.78rem;
  font-weight: 600;
}

.toolbar-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.toolbar-btn--danger {
  border-color: rgba(248, 113, 113, 0.2);
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
}

.toolbar-btn--accent {
  border-color: rgba(167, 139, 250, 0.2);
  background: rgba(129, 140, 248, 0.16);
  color: #e9d5ff;
}

.history-error {
  margin: 0;
  padding: 0.7rem 1.25rem 0;
  color: #fca5a5;
  font-size: 0.78rem;
}

.history-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 1rem 1.25rem 1.25rem;
}

.history-empty {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  border: 1px dashed rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.2);
  color: #94a3b8;
  font-size: 0.86rem;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.history-card {
  display: flex;
  gap: 0.9rem;
  padding: 0.95rem 1rem;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(15, 23, 42, 0.36);
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.history-card:hover {
  border-color: rgba(125, 211, 252, 0.28);
  background: rgba(15, 23, 42, 0.5);
}

.history-card--selected {
  border-color: rgba(56, 189, 248, 0.34);
  background: linear-gradient(180deg, rgba(56, 189, 248, 0.14), rgba(15, 23, 42, 0.34));
}

.history-card__check {
  display: flex;
  align-items: flex-start;
  padding-top: 0.2rem;
}

.history-card__check input {
  width: 16px;
  height: 16px;
  accent-color: #38bdf8;
}

.history-card__content {
  min-width: 0;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-card__header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
}

.history-card__actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.history-card__title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.history-card__title strong {
  color: #f8fafc;
  font-size: 0.96rem;
  word-break: break-all;
}

.history-card__title span {
  color: #94a3b8;
  font-size: 0.74rem;
}

.history-card__delete {
  min-height: 32px;
  padding: 0 0.82rem;
  border-radius: 10px;
  border: 1px solid rgba(248, 113, 113, 0.18);
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
  font-size: 0.74rem;
}

.history-card__replay {
  min-height: 32px;
  padding: 0 0.82rem;
  border-radius: 10px;
  border: 1px solid rgba(251, 191, 36, 0.2);
  background: rgba(245, 158, 11, 0.14);
  color: #fef3c7;
  font-size: 0.74rem;
}

.history-card__replay--active {
  border-color: rgba(56, 189, 248, 0.22);
  background: rgba(56, 189, 248, 0.14);
  color: #bae6fd;
}

.history-card__delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.history-card__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.6rem;
}

.metric,
.history-card__devices {
  padding: 0.65rem 0.72rem;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.metric span,
.devices-label {
  display: block;
  margin-bottom: 0.18rem;
  color: #94a3b8;
  font-size: 0.68rem;
}

.metric strong {
  color: #f8fafc;
  font-size: 0.78rem;
}

.device-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.device-tag {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 0.58rem;
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd;
  font-size: 0.7rem;
}

.device-empty {
  color: #64748b;
  font-size: 0.72rem;
}

@media (max-width: 900px) {
  .history-overlay {
    padding: 0.75rem;
  }

  .history-modal {
    width: 100%;
    height: min(88vh, 760px);
  }

  .history-header,
  .history-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .history-toolbar__meta,
  .history-toolbar__actions {
    flex-wrap: wrap;
  }

  .history-card__header,
  .history-card__metrics {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>
