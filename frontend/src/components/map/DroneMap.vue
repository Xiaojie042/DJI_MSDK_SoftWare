<script setup>
import { computed, ref, watch } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import FlightReplayDock from '@/components/map/FlightReplayDock.vue'
import { LCircleMarker, LMap, LMarker, LPolyline, LPopup, LTileLayer } from '@vue-leaflet/vue-leaflet'
import L from 'leaflet'

const DEGREE_SYMBOL = '\u00B0'
const LIVE_TRACK_RENDER_LIMIT = 900
const LIVE_TRACK_POINT_RENDER_LIMIT = 180
const HISTORY_TRACK_RENDER_LIMIT = 1200

const store = useDroneStore()
const zoom = ref(16)
const DEFAULT_MAP_CENTER = [31.2304, 121.4737]
const mapCenter = ref([...DEFAULT_MAP_CENTER])
const mapRef = ref(null)
const liveAutoFollowEnabled = ref(true)
const mapOptions = {
  preferCanvas: true
}
const tileLayerOptions = {
  subdomains: ['1', '2', '3', '4'],
  keepBuffer: 8,
  crossOrigin: 'anonymous'
}

const popupOptions = {
  autoClose: false,
  closeOnClick: false,
  keepInView: true,
  className: 'drone-telemetry-popup',
  offset: [0, -20],
  minWidth: 340,
  maxWidth: 400
}

const historyTrackPopupOptions = {
  autoClose: true,
  closeButton: true,
  closeOnClick: false,
  className: 'history-track-popup',
  minWidth: 200,
  maxWidth: 220,
  offset: [0, -6],
}

const currentDroneState = computed(() => store.currentDroneState)
const hasLivePosition = computed(() =>
  Number.isFinite(store.droneState.position.latitude) &&
  Number.isFinite(store.droneState.position.longitude) &&
  (store.droneState.position.latitude !== 0 || store.droneState.position.longitude !== 0)
)

const replayFrame = computed(() => store.activeFlightReplayFrame)
const replayPosition = computed(() => {
  const frame = replayFrame.value
  if (
    Number.isFinite(frame?.position?.latitude) &&
    Number.isFinite(frame?.position?.longitude) &&
    (frame.position.latitude !== 0 || frame.position.longitude !== 0)
  ) {
    return [frame.position.latitude, frame.position.longitude]
  }

  return null
})

const trackPoints = computed(() => store.flightTrack)
const replayFrames = computed(() => store.activeFlightReplayFrames)
const sampleTrackPoints = (points, maxPoints, { excludeLast = false } = {}) => {
  if (!Array.isArray(points) || points.length === 0 || maxPoints <= 0) {
    return []
  }

  const lastAvailableIndex = points.length - (excludeLast ? 2 : 1)
  if (lastAvailableIndex < 0) {
    return []
  }

  const candidateCount = lastAvailableIndex + 1
  if (candidateCount <= maxPoints) {
    return points.slice(0, lastAvailableIndex + 1)
  }

  if (maxPoints === 1) {
    return [points[0]]
  }

  const sampled = []
  const denominator = maxPoints - 1
  let previousIndex = -1

  for (let sampleIndex = 0; sampleIndex < maxPoints; sampleIndex += 1) {
    const pointIndex = Math.round((sampleIndex * lastAvailableIndex) / denominator)
    if (pointIndex === previousIndex) {
      continue
    }

    sampled.push(points[pointIndex])
    previousIndex = pointIndex
  }

  return sampled
}

const sampleReplayTrackPoints = (frames, frameIndex, maxPoints, { excludeLast = false } = {}) => {
  if (!Array.isArray(frames) || frames.length === 0 || maxPoints <= 0) {
    return []
  }

  const safeFrameIndex = Math.max(Math.min(Math.round(Number(frameIndex) || 0), frames.length - 1), 0)
  const lastAvailableIndex = safeFrameIndex - (excludeLast ? 1 : 0)
  if (lastAvailableIndex < 0) {
    return []
  }

  const candidateCount = lastAvailableIndex + 1
  if (candidateCount <= maxPoints) {
    const sampled = []
    for (let index = 0; index <= lastAvailableIndex; index += 1) {
      const point = frames[index]?.trackPoint
      if (point) {
        sampled.push(point)
      }
    }
    return sampled
  }

  if (maxPoints === 1) {
    const firstPoint = frames[0]?.trackPoint
    return firstPoint ? [firstPoint] : []
  }

  const sampled = []
  const denominator = maxPoints - 1
  let previousIndex = -1

  for (let sampleIndex = 0; sampleIndex < maxPoints; sampleIndex += 1) {
    const currentIndex = Math.round((sampleIndex * lastAvailableIndex) / denominator)
    if (currentIndex === previousIndex) {
      continue
    }

    const point = frames[currentIndex]?.trackPoint
    if (point) {
      sampled.push(point)
    }
    previousIndex = currentIndex
  }

  return sampled
}

const sampledTrackPoints = computed(() => sampleTrackPoints(trackPoints.value, LIVE_TRACK_RENDER_LIMIT))
const liveTrackMarkerPoints = computed(() =>
  sampleTrackPoints(trackPoints.value, LIVE_TRACK_POINT_RENDER_LIMIT, { excludeLast: true })
)
const isReplayActive = computed(() => Boolean(store.flightReplay.activeFlightId && replayFrames.value.length))
const pathCoords = computed(() => sampledTrackPoints.value.map((point) => [point.lat, point.lng]))
const replayTrackCoords = computed(() =>
  sampleReplayTrackPoints(replayFrames.value, store.flightReplay.frameIndex, LIVE_TRACK_RENDER_LIMIT)
    .map((point) => [point.lat, point.lng])
)
const replayTrackMarkerPoints = computed(() =>
  sampleReplayTrackPoints(replayFrames.value, store.flightReplay.frameIndex, LIVE_TRACK_POINT_RENDER_LIMIT, {
    excludeLast: true
  })
)
const takeoffPoint = computed(() => {
  if (isReplayActive.value) {
    return null
  }

  const firstPoint = trackPoints.value[0]
  return firstPoint ? [firstPoint.lat, firstPoint.lng] : null
})

const getHistoricalTrackColor = (flightId) => {
  const source = String(flightId || 'history-track')
  let hash = 0

  for (const char of source) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }

  const hue = hash % 360
  const saturation = 62 + (hash % 14)
  const lightness = 58 + ((hash >>> 4) % 8)
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`
}

const historicalTracks = computed(() => {
  return store.historicalTracks
    .filter((track) => !isReplayActive.value || track.flight_id !== store.flightReplay.activeFlightId)
    .map((track) => ({
    ...track,
    latLngs: sampleTrackPoints(track.points, HISTORY_TRACK_RENDER_LIMIT).map((point) => [point.lat, point.lng]),
    options: {
      color: getHistoricalTrackColor(track.flight_id),
      weight: 4,
      opacity: 0.72,
      dashArray: '12 10',
      lineCap: 'round',
      smoothFactor: 1.3
    }
  }))
})
const dronePosition = computed(() =>
  isReplayActive.value
    ? null
    : hasLivePosition.value
      ? [store.droneState.position.latitude, store.droneState.position.longitude]
      : null
)

const hasSamePosition = (left, right) =>
  Array.isArray(left) &&
  Array.isArray(right) &&
  left.length === right.length &&
  left.every((value, index) => value === right[index])

const syncMapCenter = (nextPosition) => {
  if (!nextPosition || hasSamePosition(mapCenter.value, nextPosition)) {
    return
  }

  mapCenter.value = [...nextPosition]
}

const centerMapOnPosition = (nextPosition) => {
  if (!nextPosition) {
    return
  }

  const targetZoom = Math.max(Number(zoom.value) || 16, 16)
  zoom.value = targetZoom
  mapCenter.value = [...nextPosition]

  const leafletMap = mapRef.value?.leafletObject
  if (leafletMap?.setView) {
    leafletMap.setView(nextPosition, targetZoom, {
      animate: true,
      duration: 0.35
    })
  }
}

const recenterDrone = () => {
  const targetPosition = isReplayActive.value ? replayPosition.value : dronePosition.value
  if (!targetPosition) {
    return
  }

  if (!isReplayActive.value) {
    liveAutoFollowEnabled.value = true
  }

  centerMapOnPosition(targetPosition)
}

watch(
  dronePosition,
  (nextPosition) => {
    if (!nextPosition || isReplayActive.value || !liveAutoFollowEnabled.value) {
      return
    }

    syncMapCenter(nextPosition)
  },
  { immediate: true }
)

watch(
  replayPosition,
  (nextPosition) => {
    if (!nextPosition || !isReplayActive.value) {
      return
    }

    syncMapCenter(nextPosition)
  },
  { immediate: true }
)

watch(
  isReplayActive,
  (active) => {
    if (active) {
      if (replayPosition.value) {
        syncMapCenter(replayPosition.value)
      }
      return
    }

    if (dronePosition.value && liveAutoFollowEnabled.value) {
      syncMapCenter(dronePosition.value)
    }
  },
  { immediate: true }
)

watch(
  () => store.droneRecenterRequestId,
  () => {
    recenterDrone()
  }
)

const handleMapDragStart = () => {
  if (!isReplayActive.value) {
    liveAutoFollowEnabled.value = false
  }
}

const hasValue = (value) => value !== undefined && value !== null && value !== ''
const toNumber = (value, fallback = 0) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

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

const readFirstValue = (source, paths, fallback = undefined) => {
  for (const path of paths) {
    const value = readPath(source, path)
    if (hasValue(value)) {
      return value
    }
  }

  return fallback
}

const latestFlightRawData = computed(() => store.currentFlightPayload)

const normalizeModelName = (value) => {
  if (!hasValue(value)) {
    return 'M400'
  }

  const text = String(value).trim()
  const normalized = text.toUpperCase()

  if (normalized.includes('400')) {
    return 'M400'
  }

  if (normalized.includes('350')) {
    return 'M350'
  }

  if (normalized.includes('300')) {
    return 'M300'
  }

  return text
    .replace(/DJI_/gi, '')
    .replace(/MATRICE/gi, 'M')
    .replace(/_/g, ' ')
    .trim()
}

const popupTelemetry = computed(() => {
  const source = latestFlightRawData.value || {}
  const position = currentDroneState.value.position || {}

  const pitch = toNumber(readFirstValue(source, ['attitude.pitch']), 0)
  const roll = toNumber(readFirstValue(source, ['attitude.roll']), 0)
  const heading = toNumber(
    readFirstValue(source, ['heading', 'aircraft_heading'], currentDroneState.value.heading),
    currentDroneState.value.heading
  )
  const yaw = toNumber(readFirstValue(source, ['attitude.yaw'], heading), heading)
  const latitude = toNumber(
    readFirstValue(
      source,
      ['location.latitude', 'aircraft_status.aircraft_location.latitude', 'position.latitude', 'latitude'],
      position.latitude
    ),
    position.latitude
  )
  const longitude = toNumber(
    readFirstValue(
      source,
      [
        'location.longitude',
        'aircraft_status.aircraft_location.longitude',
        'position.longitude',
        'longitude',
        'lng'
      ],
      position.longitude
    ),
    position.longitude
  )
  const horizontalSpeed = toNumber(
    readFirstValue(source, ['horizontal_speed', 'speed.horizontal'], 0),
    0
  )
  const trueAltitude = toNumber(
    readFirstValue(
      source,
      ['relative_altitude', 'altitude.relative', 'position.altitude', 'altitude'],
      position.altitude
    ),
    position.altitude
  )
  const seaLevelAltitude = toNumber(
    readFirstValue(
      source,
      [
        'location.altitude',
        'aircraft_status.aircraft_location.altitude',
        'position.altitude',
        'altitude'
      ],
      position.altitude
    ),
    position.altitude
  )
  const modelName = normalizeModelName(readFirstValue(source, ['aircraft_name', 'product_type'], 'M400'))
  const verticalSpeed = toNumber(readFirstValue(source, ['speed.vertical', 'vertical_speed'], 0), 0)
  return {
    pitch,
    roll,
    yaw,
    heading,
    latitude,
    longitude,
    trueAltitude,
    seaLevelAltitude,
    horizontalSpeed,
    verticalSpeed,
    modelName
  }
})

const formatAngle = (value) => `${toNumber(value, 0).toFixed(1)}${DEGREE_SYMBOL}`
const formatAltitude = (value) => `${toNumber(value, 0).toFixed(1)} m`
const formatCoordinate = (value) => toNumber(value, 0).toFixed(5)
const formatSpeed = (value) => `${toNumber(value, 0).toFixed(1)} m/s`
const formatVerticalSpeed = (value) => `${toNumber(value, 0).toFixed(1)} m/s`

const popupStatsPaired = computed(() => [
  [
    { label: '俯仰角', value: formatAngle(popupTelemetry.value.pitch) },
    { label: '横滚角', value: formatAngle(popupTelemetry.value.roll) }
  ],
  [
    { label: '飞行速度', value: formatSpeed(popupTelemetry.value.horizontalSpeed) },
    { label: '航向角', value: formatAngle(popupTelemetry.value.heading) }
  ],
  [
    {
      label: '真实高度',
      value: formatAltitude(popupTelemetry.value.trueAltitude),
      danger: popupTelemetry.value.trueAltitude > 120
    },
    { label: '垂直速度', value: formatVerticalSpeed(popupTelemetry.value.verticalSpeed) }
  ]
])

const popupCoordinates = computed(() => ({
  latitude: formatCoordinate(popupTelemetry.value.latitude),
  longitude: formatCoordinate(popupTelemetry.value.longitude)
}))

const attitudeVisualStyle = computed(() => {
  const pitchOffset = Math.max(Math.min(-popupTelemetry.value.pitch * 0.48, 18), -18)

  return {
    '--attitude-roll': `${popupTelemetry.value.roll}deg`,
    '--attitude-pitch-offset': `${pitchOffset}px`
  }
})

const droneIcon = computed(() => {
  const batteryPercent = currentDroneState.value.battery.percent || 0
  const accentColor =
    isReplayActive.value
      ? '#f59e0b'
      : batteryPercent <= 20
        ? '#ef4444'
        : batteryPercent <= 45
          ? '#f59e0b'
          : '#22c55e'

  return L.divIcon({
    className: 'custom-drone-icon',
    html: `
      <div class="drone-marker" style="--accent:${accentColor};">
        <svg viewBox="0 0 56 56" fill="none" aria-hidden="true">
          <g transform="rotate(${popupTelemetry.value.heading} 28 28)">
            <line x1="28" y1="28" x2="28" y2="6.5" stroke="#020617" stroke-width="4.1" stroke-linecap="round" />
            <path d="M28 1.8L36.4 15.6H19.6L28 1.8Z" fill="#020617" />
          </g>
          <circle cx="28" cy="28" r="14" fill="rgba(15, 23, 42, 0.92)" stroke="var(--accent)" stroke-width="2.6" />
          <circle cx="28" cy="28" r="6.2" fill="var(--accent)" />
          <path d="M18 20L11 13M38 20L45 13M18 36L11 43M38 36L45 43" stroke="#38bdf8" stroke-width="2.6" stroke-linecap="round" />
          <circle cx="18" cy="20" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
          <circle cx="38" cy="20" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
          <circle cx="18" cy="36" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
          <circle cx="38" cy="36" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
        </svg>
      </div>
    `,
    iconSize: [60, 60],
    iconAnchor: [30, 30],
    popupAnchor: [0, -24]
  })
})

</script>

<template>
  <div class="map-shell">
    <l-map
      ref="mapRef"
      v-model:center="mapCenter"
      v-model:zoom="zoom"
      :options="mapOptions"
      :useGlobalLeaflet="false"
      :zoom-control="false"
      @dragstart="handleMapDragStart"
    >
      <l-tile-layer
        url="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
        layer-type="base"
        name="GaodeMap"
        :options="tileLayerOptions"
        attribution="&copy; 高德地图"
      />

      <l-polyline
        v-for="historyTrack in historicalTracks"
        :key="historyTrack.flight_id"
        v-show="historyTrack.latLngs.length > 1"
        :lat-lngs="historyTrack.latLngs"
        :options="historyTrack.options"
      >
        <l-popup :options="historyTrackPopupOptions">
          <article class="history-track-popup-card">
            <strong>{{ historyTrack.file_name }}</strong>
            <span>{{ historyTrack.has_weather_devices ? '含气象设备' : '无气象设备' }}</span>
          </article>
        </l-popup>
      </l-polyline>

      <l-polyline
        v-if="!isReplayActive && pathCoords.length > 1"
        :lat-lngs="pathCoords"
        color="#38bdf8"
        :weight="4"
        :opacity="0.78"
        :smooth-factor="1.2"
      />

      <l-circle-marker
        v-for="trackPoint in liveTrackMarkerPoints"
        :key="`live-track-${trackPoint.timestamp}-${trackPoint.lat}-${trackPoint.lng}`"
        v-show="!isReplayActive"
        :lat-lng="[trackPoint.lat, trackPoint.lng]"
        :radius="3"
        color="#e0f2fe"
        fill-color="#38bdf8"
        :fill-opacity="0.92"
        :opacity="0.95"
        :weight="1"
      />

      <l-circle-marker
        v-if="takeoffPoint"
        :lat-lng="takeoffPoint"
        :radius="6"
        color="#22c55e"
        fill-color="#86efac"
        :fill-opacity="0.9"
      />

      <l-polyline
        v-if="replayTrackCoords.length > 1"
        :lat-lngs="replayTrackCoords"
        color="#f59e0b"
        :weight="5"
        :opacity="0.9"
        :smooth-factor="1.2"
      />

      <l-circle-marker
        v-for="trackPoint in replayTrackMarkerPoints"
        :key="`replay-track-${trackPoint.timestamp}-${trackPoint.lat}-${trackPoint.lng}`"
        :lat-lng="[trackPoint.lat, trackPoint.lng]"
        :radius="3"
        color="#fef3c7"
        fill-color="#f59e0b"
        :fill-opacity="0.9"
        :opacity="0.95"
        :weight="1"
      />

      <l-marker
        v-if="replayPosition"
        :lat-lng="replayPosition"
        :icon="droneIcon"
      >
        <l-popup :options="historyTrackPopupOptions">
          <article class="history-track-popup-card history-track-popup-card--replay">
            <strong>{{ store.flightSessionDetails[store.flightReplay.activeFlightId]?.file_name || '回放架次' }}</strong>
            <span>时间 {{ replayFrame?.timeLabel || '--' }}</span>
            <span>高度 {{ formatAltitude(replayFrame?.position?.altitude) }}</span>
            <span>速度 {{ formatSpeed(replayFrame?.velocity?.horizontal) }}</span>
          </article>
        </l-popup>
      </l-marker>

      <l-marker v-if="dronePosition" :lat-lng="dronePosition" :icon="droneIcon">
        <l-popup :options="popupOptions">
          <article class="drone-popup-shell">
            <header class="drone-popup-header">
              <div class="drone-popup-attitude-compact">
                <div class="drone-popup-attitude__frame">
                  <div class="drone-popup-attitude__disc" :style="attitudeVisualStyle">
                    <span class="drone-popup-attitude__sky"></span>
                    <span class="drone-popup-attitude__ground"></span>
                    <span class="drone-popup-attitude__horizon"></span>
                    <span class="drone-popup-attitude__tick drone-popup-attitude__tick--top-large"></span>
                    <span class="drone-popup-attitude__tick drone-popup-attitude__tick--top-medium"></span>
                    <span class="drone-popup-attitude__tick drone-popup-attitude__tick--bottom-medium"></span>
                    <span class="drone-popup-attitude__tick drone-popup-attitude__tick--bottom-large"></span>
                  </div>

                  <div class="drone-popup-attitude__symbol">
                    <span class="drone-popup-attitude__symbol-wing drone-popup-attitude__symbol-wing--left"></span>
                    <span class="drone-popup-attitude__symbol-post"></span>
                    <span class="drone-popup-attitude__symbol-wing drone-popup-attitude__symbol-wing--right"></span>
                  </div>
                </div>
              </div>

              <strong class="drone-model">{{ popupTelemetry.modelName }}</strong>
            </header>

            <div class="drone-popup-content">
              <div class="drone-popup-details">
                <div v-for="(pair, index) in popupStatsPaired" :key="index" class="drone-popup-row">
                  <div
                    v-for="item in pair"
                    :key="item.label"
                    class="drone-popup-stat"
                    :class="{ 'drone-popup-stat--danger': item.danger }"
                  >
                    <span>{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </div>

                <div class="drone-popup-coordinates">
                  <div class="drone-popup-stat">
                    <span>纬度</span>
                    <strong>{{ popupCoordinates.latitude }}</strong>
                  </div>
                  <div class="drone-popup-stat">
                    <span>经度</span>
                    <strong>{{ popupCoordinates.longitude }}</strong>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </l-popup>
      </l-marker>
    </l-map>

    <FlightReplayDock />
  </div>
</template>

<style>
.map-shell {
  position: relative;
  width: 100%;
  height: 100%;
}

.map-shell .leaflet-container {
  width: 100%;
  height: 100%;
  background: #0f172a;
}

.map-shell canvas {
  backface-visibility: hidden;
  will-change: transform;
}

.custom-drone-icon {
  background: transparent;
  border: none;
}

.custom-drone-icon .drone-marker {
  width: 60px;
  height: 60px;
  cursor: pointer;
  filter: drop-shadow(0 8px 16px rgba(14, 165, 233, 0.3));
}

.custom-drone-icon svg {
  width: 100%;
  height: 100%;
  display: block;
}

.leaflet-popup.drone-telemetry-popup .leaflet-popup-content-wrapper {
  padding: 0;
  background: transparent;
  box-shadow: none;
}

.leaflet-popup.drone-telemetry-popup .leaflet-popup-content {
  margin: 0;
}

.leaflet-popup.drone-telemetry-popup .leaflet-popup-tip {
  background: rgba(15, 23, 42, 0.92);
  box-shadow: none;
}

.leaflet-popup.drone-telemetry-popup .leaflet-popup-close-button {
  top: 12px;
  right: 14px;
  color: var(--text-muted);
  font-size: 22px;
  font-weight: 400;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.leaflet-popup.history-track-popup .leaflet-popup-content-wrapper {
  padding: 0;
  background: transparent;
  box-shadow: none;
}

.leaflet-popup.history-track-popup .leaflet-popup-content {
  margin: 0;
}

.leaflet-popup.history-track-popup .leaflet-popup-tip {
  background: rgba(15, 23, 42, 0.94);
  box-shadow: none;
}

.leaflet-popup.history-track-popup .leaflet-popup-close-button {
  top: 8px;
  right: 10px;
  color: #94a3b8;
  font-size: 18px;
  width: 22px;
  height: 22px;
}

.leaflet-popup.history-track-popup .leaflet-popup-close-button:hover {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 999px;
}

.history-track-popup-card {
  width: 200px;
  min-height: 50px;
  padding: 0.6rem 0.8rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.18rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.94);
  backdrop-filter: var(--glass-blur);
  box-shadow: 0 18px 34px rgba(2, 6, 23, 0.28);
}

.history-track-popup-card strong {
  padding-right: 1rem;
  color: #f8fafc;
  font-size: 0.78rem;
  line-height: 1.2;
  word-break: break-all;
}

.history-track-popup-card span {
  color: #94a3b8;
  font-size: 0.7rem;
  line-height: 1.2;
}

.history-track-popup-card--replay {
  width: 220px;
}

.leaflet-popup.drone-telemetry-popup .leaflet-popup-close-button:hover {
  color: var(--danger);
  background: rgba(239, 68, 68, 0.1);
  border-radius: 50%;
}

.drone-popup-shell {
  min-width: 340px;
  min-height: auto;
  padding: 0;
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: var(--bg-panel);
  backdrop-filter: var(--glass-blur);
  box-shadow: 0 18px 44px rgba(2, 6, 23, 0.36);
  color: var(--text-main);
  overflow: hidden;
}

:deep(.leaflet-popup.drone-telemetry-popup .leaflet-popup-close-button) {
  top: 16px !important;    
  right: 12px !important;  
  color: var(--text-muted) !important;
  font-size: 20px !important;
  background: transparent !important;
}

.drone-popup-header {
  min-height: 108px;
  padding: 1rem 1rem 1.1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  position: relative;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.4);
}

.drone-popup-attitude-compact {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
}

.drone-model {
  color: var(--text-main);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 0;
  text-align: center;
}

.drone-popup-content {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.drone-popup-attitude__frame {
  position: relative;
  width: 80px;
  height: 80px;
  overflow: hidden;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(15, 23, 42, 0.62);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}

.drone-popup-details {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.drone-popup-row,
.drone-popup-coordinates {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.drone-popup-attitude__disc {
  position: absolute;
  inset: -24%;
  transform: translateY(var(--attitude-pitch-offset)) rotate(var(--attitude-roll));
  transition: all 0.2s ease;
}

.drone-popup-attitude__sky,
.drone-popup-attitude__ground,
.drone-popup-attitude__horizon,
.drone-popup-attitude__tick {
  position: absolute;
  left: 0;
}

.drone-popup-attitude__sky,
.drone-popup-attitude__ground,
.drone-popup-attitude__horizon {
  width: 100%;
}

.drone-popup-attitude__sky {
  top: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(181, 203, 238, 0.98), rgba(163, 191, 234, 0.94));
}

.drone-popup-attitude__ground {
  bottom: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(230, 221, 196, 0.98), rgba(220, 209, 181, 0.95));
}

.drone-popup-attitude__horizon {
  top: calc(50% - 1px);
  height: 2px;
  background: rgba(15, 23, 42, 0.88);
}

.drone-popup-attitude__tick {
  left: 50%;
  height: 2px;
  background: rgba(15, 23, 42, 0.7);
  transform: translateX(-50%);
}

.drone-popup-attitude__tick--top-large {
  top: calc(50% - 22px);
  width: 30px;
}

.drone-popup-attitude__tick--top-medium {
  top: calc(50% - 12px);
  width: 18px;
}

.drone-popup-attitude__tick--bottom-medium {
  top: calc(50% + 10px);
  width: 18px;
}

.drone-popup-attitude__tick--bottom-large {
  top: calc(50% + 20px);
  width: 30px;
}

.drone-popup-attitude__symbol {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 32px;
  height: 18px;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.drone-popup-attitude__symbol-wing,
.drone-popup-attitude__symbol-post {
  position: absolute;
  display: block;
  background: #2563eb;
  box-shadow: 0 0 8px rgba(37, 99, 235, 0.16);
}

.drone-popup-attitude__symbol-wing {
  top: 7px;
  width: 12px;
  height: 2.5px;
  border-radius: 999px;
}

.drone-popup-attitude__symbol-wing--left {
  left: 0;
}

.drone-popup-attitude__symbol-wing--right {
  right: 0;
}

.drone-popup-attitude__symbol-post {
  left: 50%;
  top: 0;
  width: 2.5px;
  height: 18px;
  border-radius: 999px;
  transform: translateX(-50%);
}

.drone-popup-stat {
  padding: 0.7rem 0.85rem;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.34);
  border: 1px solid rgba(148, 163, 184, 0.12);
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  gap: 0.3rem;
}

.drone-popup-stat span {
  color: var(--text-muted);
  font-size: 0.75rem;
  letter-spacing: 0.03em;
}

.drone-popup-stat strong {
  color: var(--text-main);
  font-size: 0.96rem;
  font-weight: 600;
}

.drone-popup-stat--danger strong {
  color: var(--danger);
}

@media (max-width: 640px) {
  .drone-popup-shell {
    min-width: 300px;
  }

  .drone-popup-header {
    flex-direction: column;
    min-height: auto;
    padding-top: 1.5rem;
  }

  .drone-popup-attitude-compact {
    position: static;
    transform: none;
    margin-bottom: 0.5rem;
  }

  .drone-popup-row,
  .drone-popup-coordinates {
    grid-template-columns: 1fr;
  }

  .drone-popup-attitude__frame {
    width: 70px;
    height: 70px;
  }
}
</style>
