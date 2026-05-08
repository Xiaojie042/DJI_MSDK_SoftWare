import { defineStore } from 'pinia'
import { useRuntimeConfigStore } from '@/stores/runtimeConfigStore'

const LOCAL_CACHE_KEY = 'drone-monitor:telemetry-cache:v1'
const TRACK_LIMIT = 5000
const HISTORY_LIMIT = 50
const RAW_STREAM_LIMIT = 50
const ALERT_LIMIT = 20
const TELEMETRY_ARCHIVE_LIMIT = 300
const REPLAY_DELAY_MIN_MS = 120
const REPLAY_DELAY_MAX_MS = 1200
const PERSIST_DEBOUNCE_MS = 800

let persistTimer = null
let replayTimer = null

const createApiUrl = (path) => `${useRuntimeConfigStore().apiBaseUrl}${path}`

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)
const toFiniteNumber = (value, fallback = 0) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}
const toNullableNumber = (value) => {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}
const toBoolean = (value, fallback = false) => {
  if (typeof value === 'boolean') {
    return value
  }

  if (typeof value === 'number') {
    return Boolean(value)
  }

  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (['true', '1', 'yes', 'on'].includes(normalized)) {
      return true
    }
    if (['false', '0', 'no', 'off'].includes(normalized)) {
      return false
    }
  }

  return fallback
}
const parseTimestampToSeconds = (value, fallback = Date.now() / 1000) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string') {
    const numeric = Number(value)
    if (Number.isFinite(numeric)) {
      return numeric
    }

    const parsed = Date.parse(value)
    if (Number.isFinite(parsed)) {
      return parsed / 1000
    }
  }

  return fallback
}
const toRadians = (degrees) => degrees * (Math.PI / 180)

const haversineDistanceMeters = (pointA, pointB) => {
  const earthRadius = 6371000
  const latDelta = toRadians(pointB.lat - pointA.lat)
  const lngDelta = toRadians(pointB.lng - pointA.lng)
  const startLat = toRadians(pointA.lat)
  const endLat = toRadians(pointB.lat)

  const haversine =
    Math.sin(latDelta / 2) * Math.sin(latDelta / 2) +
    Math.cos(startLat) *
      Math.cos(endLat) *
      Math.sin(lngDelta / 2) *
      Math.sin(lngDelta / 2)

  return 2 * earthRadius * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine))
}

const hasValidPosition = (position) =>
  Number.isFinite(position?.latitude) &&
  Number.isFinite(position?.longitude) &&
  (position.latitude !== 0 || position.longitude !== 0)

const formatTelemetryTime = (timestamp) =>
  new Date(parseTimestampToSeconds(timestamp) * 1000).toLocaleTimeString('zh-CN', { hour12: false })

const sortRecordsByTimestamp = (records = []) =>
  [...records].sort(
    (left, right) =>
      parseTimestampToSeconds(left?.timestamp ?? left?.telemetry?.timestamp, 0) -
      parseTimestampToSeconds(right?.timestamp ?? right?.telemetry?.timestamp, 0)
  )

const getRecordTimestampSeconds = (record = {}, fallback = 0) =>
  parseTimestampToSeconds(record?.timestamp ?? record?.telemetry?.timestamp ?? record?.raw_payload?.timestamp, fallback)

const findLatestRawStreamData = (frames = [], matcher = () => true) => {
  for (let index = frames.length - 1; index >= 0; index -= 1) {
    const candidate = frames[index]?.data
    if (candidate && typeof candidate === 'object' && matcher(candidate)) {
      return candidate
    }
  }

  return null
}

const findLastRecordIndexAtOrBefore = (records = [], targetTimestamp) => {
  if (!Array.isArray(records) || records.length === 0) {
    return -1
  }

  const targetSeconds = parseTimestampToSeconds(targetTimestamp, Number.POSITIVE_INFINITY)
  let left = 0
  let right = records.length - 1
  let result = -1

  while (left <= right) {
    const mid = Math.floor((left + right) / 2)
    const midTimestamp = getRecordTimestampSeconds(records[mid], Number.POSITIVE_INFINITY)

    if (midTimestamp <= targetSeconds) {
      result = mid
      left = mid + 1
    } else {
      right = mid - 1
    }
  }

  return result
}

const findLatestRecordAtOrBefore = (records = [], targetTimestamp, matcher = () => true) => {
  if (!Array.isArray(records) || records.length === 0) {
    return null
  }

  const startIndex = findLastRecordIndexAtOrBefore(records, targetTimestamp)

  for (let index = startIndex; index >= 0; index -= 1) {
    const candidate = records[index]
    if (matcher(candidate)) {
      return candidate
    }
  }

  for (let index = records.length - 1; index >= 0; index -= 1) {
    const candidate = records[index]
    if (matcher(candidate)) {
      return candidate
    }
  }

  return null
}

const createDefaultDroneState = () => ({
  drone_id: 'DJI-NONE',
  timestamp: Date.now() / 1000,
  position: { latitude: 0, longitude: 0, altitude: 0 },
  heading: 0,
  velocity: { horizontal: 0, vertical: 0 },
  battery: { percent: 0, voltage: 0, temperature: 0 },
  gps_signal: 0,
  flight_mode: 'DISCONNECTED',
  is_flying: false,
  home_distance: 0,
  gimbal_pitch: 0,
  rc_signal: null
})

const normalizeFlightSessionSummary = (record = {}) => ({
  flight_id: record.flight_id || '',
  file_name: record.file_name || record.flight_id || 'unknown-flight.json',
  drone_id: record.drone_id || null,
  takeoff_time: parseTimestampToSeconds(record.takeoff_time, Date.now() / 1000),
  landing_time: record.landing_time === null || record.landing_time === undefined
    ? null
    : parseTimestampToSeconds(record.landing_time, Date.now() / 1000),
  total_distance_m: toFiniteNumber(record.total_distance_m, 0),
  max_altitude_m: toFiniteNumber(record.max_altitude_m, 0),
  attached_weather_devices: Array.isArray(record.attached_weather_devices)
    ? record.attached_weather_devices
        .map((device) => ({
          payload_index: device?.payload_index || '--',
          device_type: device?.device_type || 'unknown'
        }))
        .filter((device) => device.payload_index || device.device_type)
    : []
})

const createHistoricalTrackPoint = (record = {}) => {
  const telemetry = record.telemetry || {}
  const position = telemetry.position || {}
  const latitude = toFiniteNumber(position.latitude ?? telemetry.latitude ?? telemetry.lat, NaN)
  const longitude = toFiniteNumber(position.longitude ?? telemetry.longitude ?? telemetry.lng, NaN)

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || (latitude === 0 && longitude === 0)) {
    return null
  }

  return {
    lat: latitude,
    lng: longitude,
    altitude: toFiniteNumber(position.altitude ?? telemetry.altitude, 0),
    heading: toFiniteNumber(telemetry.heading, 0),
    timestamp: parseTimestampToSeconds(record.timestamp ?? telemetry.timestamp, Date.now() / 1000)
  }
}

const buildHistoricalTrack = (detail = {}) =>
  sortRecordsByTimestamp(Array.isArray(detail.telemetry_records) ? detail.telemetry_records : [])
    .map((record) => createHistoricalTrackPoint(record))
    .filter(Boolean)

const createReplayFrame = (record = {}) => {
  const telemetry = record.telemetry && typeof record.telemetry === 'object' ? record.telemetry : record
  const state = normalizeDroneStatePayload({ telemetry })
  const trackPoint = createHistoricalTrackPoint(record)

  if (!trackPoint) {
    return null
  }

  const timestamp = parseTimestampToSeconds(record.timestamp ?? telemetry.timestamp, state.timestamp)

  return {
    ...state,
    timestamp,
    payload: record.raw_payload && typeof record.raw_payload === 'object' ? record.raw_payload : telemetry,
    trackPoint,
    timeLabel: formatTelemetryTime(timestamp)
  }
}

const buildReplayFrames = (detail = {}) =>
  sortRecordsByTimestamp(Array.isArray(detail.telemetry_records) ? detail.telemetry_records : [])
    .map((record) => createReplayFrame(record))
    .filter(Boolean)

const createDefaultReplayState = () => ({
  activeFlightId: '',
  status: 'idle',
  frameIndex: 0,
  speed: 1,
  error: ''
})

const createLiveFrameCache = (frames = []) => {
  let latestLiveFlightPayloadCache = null
  let latestLiveWeatherFrameCache = null
  let latestLiveVisibilityFrameCache = null

  for (const frame of frames) {
    const candidate = frame?.data
    if (!candidate || typeof candidate !== 'object') {
      continue
    }

    if (candidate.type === 'psdk_data') {
      if (candidate.device_type === 'weather') {
        latestLiveWeatherFrameCache = candidate
      } else if (candidate.device_type === 'visibility') {
        latestLiveVisibilityFrameCache = candidate
      }
    } else {
      latestLiveFlightPayloadCache = candidate
    }
  }

  return {
    latestLiveFlightPayloadCache,
    latestLiveWeatherFrameCache,
    latestLiveVisibilityFrameCache
  }
}

const applyLiveFrameCache = (store, frame) => {
  const candidate = frame?.data
  if (!candidate || typeof candidate !== 'object') {
    return
  }

  if (candidate.type === 'psdk_data') {
    if (candidate.device_type === 'weather') {
      store.latestLiveWeatherFrameCache = candidate
    } else if (candidate.device_type === 'visibility') {
      store.latestLiveVisibilityFrameCache = candidate
    }
    return
  }

  store.latestLiveFlightPayloadCache = candidate
}

const refreshLiveFrameCache = (store) => {
  const liveFrameCache = createLiveFrameCache(store.rawStream)
  store.latestLiveFlightPayloadCache = liveFrameCache.latestLiveFlightPayloadCache
  store.latestLiveWeatherFrameCache = liveFrameCache.latestLiveWeatherFrameCache
  store.latestLiveVisibilityFrameCache = liveFrameCache.latestLiveVisibilityFrameCache
}

const clearReplayTimer = () => {
  if (replayTimer) {
    if (typeof window !== 'undefined') {
      window.clearTimeout(replayTimer)
    } else {
      clearTimeout(replayTimer)
    }
    replayTimer = null
  }
}

const getReplayDelayMs = (frames, frameIndex, speed = 1) => {
  const currentFrame = frames[frameIndex]
  const nextFrame = frames[frameIndex + 1]

  if (!currentFrame || !nextFrame) {
    return null
  }

  const currentTimestamp = parseTimestampToSeconds(currentFrame.timestamp, 0)
  const nextTimestamp = parseTimestampToSeconds(nextFrame.timestamp, currentTimestamp)
  const speedFactor = Math.max(Number(speed) || 1, 0.25)
  const rawDelayMs = Math.max(0, (nextTimestamp - currentTimestamp) * 1000) / speedFactor

  return clamp(Math.round(rawDelayMs || REPLAY_DELAY_MIN_MS), REPLAY_DELAY_MIN_MS, REPLAY_DELAY_MAX_MS)
}

const createDefaultState = () => ({
  droneState: createDefaultDroneState(),
  alerts: [],
  isConnected: false,
  history: [],
  rawStream: [],
  latestLiveFlightPayloadCache: null,
  latestLiveWeatherFrameCache: null,
  latestLiveVisibilityFrameCache: null,
  flightTrack: [],
  telemetryArchive: [],
  flightHistoryPanelOpen: false,
  flightSessions: [],
  flightSessionsLoading: false,
  flightSessionsError: '',
  flightSessionsDeletingIds: [],
  selectedFlightSessionIds: [],
  flightSessionDetails: {},
  flightSessionTracks: {},
  flightReplayFrames: {},
  flightReplay: createDefaultReplayState(),
  droneRecenterRequestId: 0,
  localCacheMeta: {
    enabled: true,
    lastSavedAt: null
  }
})

const mergeDroneState = (baseState, nextState = {}) => ({
  ...baseState,
  ...nextState,
  position: {
    ...baseState.position,
    ...(nextState.position || {})
  },
  velocity: {
    ...baseState.velocity,
    ...(nextState.velocity || {})
  },
  battery: {
    ...baseState.battery,
    ...(nextState.battery || {})
  }
})

const readPersistedState = () => {
  const defaults = createDefaultState()

  if (typeof window === 'undefined') {
    return defaults
  }

  try {
    const raw = window.localStorage.getItem(LOCAL_CACHE_KEY)

    if (!raw) {
      return defaults
    }

    const parsed = JSON.parse(raw)
    const rawStream = Array.isArray(parsed.rawStream) ? parsed.rawStream.slice(-RAW_STREAM_LIMIT) : defaults.rawStream
    const liveFrameCache = createLiveFrameCache(rawStream)

    return {
      ...defaults,
      droneState: mergeDroneState(defaults.droneState, parsed.droneState || {}),
      alerts: Array.isArray(parsed.alerts) ? parsed.alerts.slice(0, ALERT_LIMIT) : defaults.alerts,
      history: Array.isArray(parsed.history) ? parsed.history.slice(-HISTORY_LIMIT) : defaults.history,
      rawStream,
      latestLiveFlightPayloadCache: liveFrameCache.latestLiveFlightPayloadCache,
      latestLiveWeatherFrameCache: liveFrameCache.latestLiveWeatherFrameCache,
      latestLiveVisibilityFrameCache: liveFrameCache.latestLiveVisibilityFrameCache,
      flightTrack: Array.isArray(parsed.flightTrack) ? parsed.flightTrack.slice(-TRACK_LIMIT) : defaults.flightTrack,
      telemetryArchive: Array.isArray(parsed.telemetryArchive)
        ? parsed.telemetryArchive.slice(-TELEMETRY_ARCHIVE_LIMIT)
        : defaults.telemetryArchive,
      localCacheMeta: {
        ...defaults.localCacheMeta,
        ...(parsed.localCacheMeta || {})
      }
    }
  } catch (error) {
    console.warn('Failed to restore local telemetry cache:', error)
    return defaults
  }
}

const buildArchiveRecord = (state) => ({
  id: `${Math.round((state.timestamp || Date.now() / 1000) * 1000)}-${Math.random().toString(16).slice(2, 8)}`,
  timestamp: state.timestamp || Date.now() / 1000,
  drone_id: state.drone_id,
  latitude: state.position.latitude,
  longitude: state.position.longitude,
  altitude: state.position.altitude || 0,
  heading: state.heading || 0,
  horizontal_speed: state.velocity.horizontal || 0,
  vertical_speed: state.velocity.vertical || 0,
  battery_percent: state.battery.percent || 0,
  battery_voltage: state.battery.voltage || 0,
  battery_temperature: state.battery.temperature || 0,
  gps_signal: state.gps_signal || 0,
  flight_mode: state.flight_mode || 'UNKNOWN',
  is_flying: Boolean(state.is_flying)
})

const createTrackPoint = (state) => {
  if (!hasValidPosition(state.position)) {
    return null
  }

  return {
    lat: state.position.latitude,
    lng: state.position.longitude,
    altitude: state.position.altitude || 0,
    heading: state.heading || 0,
    timestamp: state.timestamp || Date.now() / 1000
  }
}

const appendTrackPoint = (track, state) => {
  const nextPoint = createTrackPoint(state)

  if (!nextPoint) {
    return
  }

  const lastPoint = track[track.length - 1]
  const shouldAppend =
    !lastPoint ||
    Math.abs(lastPoint.lat - nextPoint.lat) > 0.00001 ||
    Math.abs(lastPoint.lng - nextPoint.lng) > 0.00001 ||
    Math.abs(lastPoint.altitude - nextPoint.altitude) > 0.8

  if (shouldAppend) {
    track.push(nextPoint)
  }

  if (track.length > TRACK_LIMIT) {
    track.shift()
  }
}

const buildHistoryEntry = (state) => ({
  time: formatTelemetryTime(state.timestamp),
  altitude: state.position.altitude || 0,
  speed: state.velocity.horizontal || 0
})

const extractRawFrameData = (payload = {}) => {
  if (payload && typeof payload === 'object') {
    if (payload.type === 'psdk_data') {
      return payload
    }

    if (payload.raw_payload && typeof payload.raw_payload === 'object') {
      return payload.raw_payload
    }

    if (payload.telemetry?.raw_payload && typeof payload.telemetry.raw_payload === 'object') {
      return payload.telemetry.raw_payload
    }

    if (payload.telemetry && typeof payload.telemetry === 'object') {
      return payload.telemetry
    }
  }

  return payload
}

const buildRawStreamFrame = (payload, fallbackTimestamp = null) => {
  const rawData = extractRawFrameData(payload)

  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    time: formatTelemetryTime(rawData?.timestamp ?? payload?.timestamp ?? fallbackTimestamp),
    data: rawData
  }
}

const isGroundReadyState = (state) => {
  if (!state) {
    return false
  }

  const altitude = toFiniteNumber(state.position?.altitude, 0)
  const flightMode = String(state.flight_mode || '').trim().toUpperCase()
  return !toBoolean(state.is_flying, false) && altitude <= 2 && flightMode === 'TAKE_OFF_READY'
}

const hasScenarioTimestampReset = (previousState, nextState) => {
  const previousTimestamp = parseTimestampToSeconds(previousState?.timestamp, 0)
  const nextTimestamp = parseTimestampToSeconds(nextState?.timestamp, 0)

  return previousTimestamp > 0 && nextTimestamp > 0 && nextTimestamp + 1 < previousTimestamp
}

const hasGroundBoundaryShift = (previousState, nextState) => {
  if (!hasValidPosition(previousState?.position) || !hasValidPosition(nextState?.position)) {
    return false
  }

  const distanceMeters = haversineDistanceMeters(
    {
      lat: previousState.position.latitude,
      lng: previousState.position.longitude
    },
    {
      lat: nextState.position.latitude,
      lng: nextState.position.longitude
    }
  )

  return distanceMeters >= 12
}

const shouldResetTrackForNewFlight = (previousState, nextState) => {
  if (!previousState || !nextState) {
    return false
  }

  const previousAltitude = toFiniteNumber(previousState.position?.altitude, 0)
  const takeoffTransition =
    !toBoolean(previousState.is_flying, false) &&
    toBoolean(nextState.is_flying, false) &&
    previousAltitude <= 2

  const groundReadyBoundary =
    isGroundReadyState(previousState) &&
    isGroundReadyState(nextState) &&
    (hasScenarioTimestampReset(previousState, nextState) || hasGroundBoundaryShift(previousState, nextState))

  return (
    takeoffTransition ||
    groundReadyBoundary
  )
}

const normalizeDroneStatePayload = (payload = {}) => {
  const source =
    payload && typeof payload === 'object' && payload.telemetry && typeof payload.telemetry === 'object'
      ? payload.telemetry
      : payload

  const position = source.position || {}
  const velocity = source.velocity || {}
  const battery = source.battery || {}

  return {
    drone_id: source.drone_id || source.droneId || 'DJI-NONE',
    timestamp: toFiniteNumber(source.timestamp, Date.now() / 1000),
    position: {
      latitude: toFiniteNumber(position.latitude ?? source.latitude ?? source.lat, 0),
      longitude: toFiniteNumber(position.longitude ?? source.longitude ?? source.lng ?? source.lon, 0),
      altitude: toFiniteNumber(position.altitude ?? source.altitude ?? source.relative_altitude, 0)
    },
    heading: toFiniteNumber(source.heading ?? source.aircraft_heading, 0),
    velocity: {
      horizontal: toFiniteNumber(
        velocity.horizontal ?? velocity.horizontal_speed ?? source.horizontal_speed ?? source.horizontalSpeed,
        0
      ),
      vertical: toFiniteNumber(velocity.vertical ?? source.vertical_speed ?? source.verticalSpeed, 0)
    },
    battery: {
      percent: clamp(
        Math.round(toFiniteNumber(battery.percent ?? source.battery_percent ?? source.batteryPercent, 0)),
        0,
        100
      ),
      voltage: toFiniteNumber(battery.voltage ?? source.battery_voltage ?? source.batteryVoltage, 0),
      temperature: toFiniteNumber(
        battery.temperature ?? source.battery_temperature ?? source.batteryTemperature,
        0
      )
    },
    gps_signal: clamp(
      Math.round(toFiniteNumber(source.gps_signal ?? source.gpsSignal, 0)),
      0,
      5
    ),
    flight_mode: source.flight_mode || source.flightMode || source.flight_mode_string || 'UNKNOWN',
    is_flying: toBoolean(source.is_flying ?? source.isFlying, false),
    home_distance: toFiniteNumber(source.home_distance ?? source.homeDistance, 0),
    gimbal_pitch: toFiniteNumber(source.gimbal_pitch ?? source.gimbalPitch, 0),
    rc_signal: toNullableNumber(source.rc_signal ?? source.rcSignal)
  }
}

const persistStateToLocal = (storeState) => {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(
      LOCAL_CACHE_KEY,
      JSON.stringify({
        droneState: storeState.droneState,
        alerts: storeState.alerts,
        history: storeState.history,
        rawStream: storeState.rawStream,
        flightTrack: storeState.flightTrack,
        telemetryArchive: storeState.telemetryArchive,
        localCacheMeta: storeState.localCacheMeta
      })
    )
  } catch (error) {
    console.warn('Failed to persist local telemetry cache:', error)
  }
}

const schedulePersistence = (store) => {
  if (typeof window === 'undefined') {
    return
  }

  if (persistTimer) {
    window.clearTimeout(persistTimer)
  }

  persistTimer = window.setTimeout(() => {
    store.localCacheMeta = {
      ...store.localCacheMeta,
      lastSavedAt: Date.now()
    }
    persistStateToLocal(store)
    persistTimer = null
  }, PERSIST_DEBOUNCE_MS)
}

const getBatteryHealth = (battery, isConnected) => {
  if (!isConnected) {
    return {
      score: null,
      label: '待接入',
      tone: 'neutral',
      summary: '等待链路恢复后评估电池健康度'
    }
  }

  if (!battery.voltage && !battery.temperature) {
    return {
      score: null,
      label: '待诊断',
      tone: 'neutral',
      summary: '已接入飞行链路，等待更多电压与温度数据'
    }
  }

  let score = 100
  const notes = []

  if (battery.voltage > 0 && battery.voltage < 21.5) {
    score -= 12
    notes.push('电压偏低')
  }

  if (battery.voltage > 0 && battery.voltage < 20) {
    score -= 15
    notes.push('建议尽快返航并检查电芯')
  }

  if (battery.temperature >= 55) {
    score -= 12
    notes.push('电池温升偏高')
  }

  if (battery.temperature >= 65) {
    score -= 18
    notes.push('存在过热风险')
  }

  score = clamp(Math.round(score), 40, 100)

  if (score >= 90) {
    return {
      score,
      label: '优秀',
      tone: 'good',
      summary: notes[0] || '电压与温度处于健康区间'
    }
  }

  if (score >= 75) {
    return {
      score,
      label: '良好',
      tone: 'good',
      summary: notes[0] || '建议继续保持当前任务负载'
    }
  }

  if (score >= 60) {
    return {
      score,
      label: '关注',
      tone: 'warning',
      summary: notes.join('，') || '建议缩短任务时长并复查电池状态'
    }
  }

  return {
    score,
    label: '预警',
    tone: 'danger',
    summary: notes.join('，') || '建议立即结束任务并进行维护检查'
  }
}

const getSafetyPolicy = (state, isConnected) => {
  if (!isConnected) {
    return {
      level: 'offline',
      badge: '链路离线',
      title: '失联保护待机',
      description: '当前未接收到实时遥测，系统保持保守监控策略。',
      action: '优先恢复链路，再执行起飞或返航指令。'
    }
  }

  if (state.flight_mode === 'DISCONNECTED' || (!hasValidPosition(state.position) && state.battery.percent === 0)) {
    return {
      level: 'good',
      badge: '待同步',
      title: '等待遥测同步',
      description: '飞行链路已建立，等待首帧遥测数据完成状态同步。',
      action: '收到实时数据后自动切换对应安全策略。'
    }
  }

  if (state.battery.percent <= 10) {
    return {
      level: 'danger',
      badge: '紧急',
      title: '紧急返航 / 就近降落',
      description: '剩余电量已进入紧急阈值，需要尽快结束飞行任务。',
      action: '立即锁定返航通道，避免额外机动。'
    }
  }

  if (state.battery.percent <= 20) {
    return {
      level: 'warning',
      badge: '预警',
      title: '低电量返航',
      description: '电量已进入返航保护区间，应开始回收任务载荷。',
      action: '减少悬停和绕飞，保留安全余量。'
    }
  }

  if (state.is_flying && state.gps_signal <= 1) {
    return {
      level: 'warning',
      badge: 'GNSS 弱',
      title: '弱定位保守控制',
      description: 'GPS 信号不足，建议降低航速并缩小作业半径。',
      action: '切换保守姿态控制，保持目视可控范围。'
    }
  }

  if (state.is_flying && state.rc_signal !== null && state.rc_signal < 35) {
    return {
      level: 'warning',
      badge: '链路弱',
      title: '遥控链路保护',
      description: '遥控器信号较弱，远距飞行存在失联风险。',
      action: '限制继续外扩航线，准备执行返航。'
    }
  }

  if (state.is_flying) {
    return {
      level: 'good',
      badge: '正常',
      title: 'GPS 优先巡航',
      description: '当前飞行状态稳定，执行围栏监测和返航保护。',
      action: '持续监控电量、定位和链路质量。'
    }
  }

  return {
    level: 'good',
    badge: '待命',
    title: '地面待命自检',
    description: '无人机处于地面状态，可进行起飞前安全检查。',
    action: '确认电池、GNSS 与链路状态后再起飞。'
  }
}

export const useDroneStore = defineStore('drone', {
  state: () => readPersistedState(),

  getters: {
    batteryHealth(state) {
      return getBatteryHealth(state.droneState.battery, state.isConnected)
    },
    safetyPolicy(state) {
      return getSafetyPolicy(state.droneState, state.isConnected)
    },
    trackDistanceMeters(state) {
      if (state.flightTrack.length < 2) {
        return 0
      }

      return state.flightTrack.slice(1).reduce((total, point, index) => {
        const previousPoint = state.flightTrack[index]
        return total + haversineDistanceMeters(previousPoint, point)
      }, 0)
    },
    localArchiveCount(state) {
      return state.telemetryArchive.length
    },
    latestLiveFlightPayload(state) {
      return state.latestLiveFlightPayloadCache || findLatestRawStreamData(
        state.rawStream,
        (candidate) => candidate.type !== 'psdk_data'
      )
    },
    latestLiveWeatherFrame(state) {
      return state.latestLiveWeatherFrameCache || findLatestRawStreamData(
        state.rawStream,
        (candidate) => candidate.type === 'psdk_data' && candidate.device_type === 'weather'
      )
    },
    latestLiveVisibilityFrame(state) {
      return state.latestLiveVisibilityFrameCache || findLatestRawStreamData(
        state.rawStream,
        (candidate) => candidate.type === 'psdk_data' && candidate.device_type === 'visibility'
      )
    },
    historicalTracks(state) {
      return state.selectedFlightSessionIds
        .map((flightId) => {
          const points = state.flightSessionTracks[flightId]
          if (!Array.isArray(points) || points.length < 2) {
            return null
          }

          const summary =
            state.flightSessions.find((item) => item.flight_id === flightId) ||
            state.flightSessionDetails[flightId] ||
            {}

          return {
            flight_id: flightId,
            file_name: summary.file_name || flightId,
            points,
            attached_weather_devices: Array.isArray(summary.attached_weather_devices)
              ? summary.attached_weather_devices
              : [],
            has_weather_devices: Array.isArray(summary.attached_weather_devices)
              ? summary.attached_weather_devices.length > 0
              : false
          }
          })
          .filter(Boolean)
    },
    isReplayActive(state) {
      return Boolean(state.flightReplay.activeFlightId && this.activeFlightReplayFrames.length)
    },
    activeFlightReplayFrames(state) {
      if (!state.flightReplay.activeFlightId) {
        return []
      }

      return state.flightReplayFrames[state.flightReplay.activeFlightId] || []
    },
    activeFlightReplayFrame() {
      const frames = this.activeFlightReplayFrames
      if (!frames.length) {
        return null
      }

      const frameIndex = clamp(this.flightReplay.frameIndex, 0, frames.length - 1)
      return frames[frameIndex] || null
    },
    activeFlightReplayTrack() {
      const frames = this.activeFlightReplayFrames
      if (!frames.length) {
        return []
      }

      const frameIndex = clamp(this.flightReplay.frameIndex, 0, frames.length - 1)
      return frames.slice(0, frameIndex + 1).map((frame) => frame.trackPoint)
    },
    activeFlightReplayProgress() {
      const frames = this.activeFlightReplayFrames
      if (!frames.length) {
        return 0
      }

      if (frames.length === 1) {
        return 100
      }

      const frameIndex = clamp(this.flightReplay.frameIndex, 0, frames.length - 1)
      return Math.round((frameIndex / (frames.length - 1)) * 100)
    },
    currentDroneState(state) {
      return this.isReplayActive && this.activeFlightReplayFrame
        ? mergeDroneState(createDefaultDroneState(), this.activeFlightReplayFrame)
        : state.droneState
    },
    currentFlightPayload(state) {
      if (this.isReplayActive) {
        return this.activeFlightReplayFrame?.payload || null
      }

      return this.latestLiveFlightPayload
    },
    currentWeatherFrame(state) {
      if (this.isReplayActive) {
        return findLatestRecordAtOrBefore(
          state.flightSessionDetails[state.flightReplay.activeFlightId]?.psdk_records || [],
          this.activeFlightReplayFrame?.timestamp,
          (candidate) => candidate?.device_type === 'weather'
        )
      }

      return this.latestLiveWeatherFrame
    },
    currentVisibilityFrame(state) {
      if (this.isReplayActive) {
        return findLatestRecordAtOrBefore(
          state.flightSessionDetails[state.flightReplay.activeFlightId]?.psdk_records || [],
          this.activeFlightReplayFrame?.timestamp,
          (candidate) => candidate?.device_type === 'visibility'
        )
      }

      return this.latestLiveVisibilityFrame
    }
  },

  actions: {
    _setFlightReplayState(nextState = {}) {
      this.flightReplay = {
        ...this.flightReplay,
        ...nextState
      }
    },
    _scheduleFlightReplayAdvance() {
      clearReplayTimer()

      if (typeof window === 'undefined' || this.flightReplay.status !== 'playing') {
        return
      }

      const frames = this.flightReplay.activeFlightId
        ? this.flightReplayFrames[this.flightReplay.activeFlightId] || []
        : []

      if (frames.length < 2) {
        this._setFlightReplayState({
          status: frames.length ? 'completed' : 'idle'
        })
        return
      }

      if (this.flightReplay.frameIndex >= frames.length - 1) {
        this._setFlightReplayState({ status: 'completed' })
        return
      }

      const delayMs = getReplayDelayMs(frames, this.flightReplay.frameIndex, this.flightReplay.speed)
      replayTimer = window.setTimeout(() => {
        this.advanceFlightReplay()
      }, delayMs ?? REPLAY_DELAY_MIN_MS)
    },
    async startFlightReplay(flightId) {
      const detail = await this.fetchFlightSessionDetail(flightId)
      const frames = this.flightReplayFrames[flightId] || []

      if (!frames.length) {
        clearReplayTimer()
        this.flightReplay = {
          ...createDefaultReplayState(),
          activeFlightId: flightId,
          error: '所选架次没有可回放的有效航迹'
        }
        return false
      }

      if (!this.selectedFlightSessionIds.includes(flightId)) {
        this.selectedFlightSessionIds = [...this.selectedFlightSessionIds, flightId]
      }

      this.flightReplay = {
        activeFlightId: flightId,
        status: 'playing',
        frameIndex: 0,
        speed: this.flightReplay.activeFlightId === flightId ? this.flightReplay.speed : 1,
        error: ''
      }

      this._scheduleFlightReplayAdvance()
      return Boolean(detail)
    },
    pauseFlightReplay() {
      if (this.flightReplay.status !== 'playing') {
        return
      }

      clearReplayTimer()
      this._setFlightReplayState({ status: 'paused' })
    },
    resumeFlightReplay() {
      const frames = this.flightReplay.activeFlightId
        ? this.flightReplayFrames[this.flightReplay.activeFlightId] || []
        : []

      if (!frames.length) {
        return
      }

      const resetIndex = this.flightReplay.frameIndex >= frames.length - 1 ? 0 : this.flightReplay.frameIndex
      this._setFlightReplayState({
        frameIndex: resetIndex,
        status: 'playing',
        error: ''
      })
      this._scheduleFlightReplayAdvance()
    },
    stopFlightReplay() {
      clearReplayTimer()
      this.flightReplay = {
        ...createDefaultReplayState(),
        speed: this.flightReplay.speed
      }
    },
    advanceFlightReplay() {
      const frames = this.flightReplay.activeFlightId
        ? this.flightReplayFrames[this.flightReplay.activeFlightId] || []
        : []

      if (!frames.length) {
        this.stopFlightReplay()
        return false
      }

      if (this.flightReplay.frameIndex >= frames.length - 1) {
        clearReplayTimer()
        this._setFlightReplayState({ status: 'completed' })
        return false
      }

      this._setFlightReplayState({
        frameIndex: this.flightReplay.frameIndex + 1,
        status: 'playing'
      })
      this._scheduleFlightReplayAdvance()
      return true
    },
    seekFlightReplay(frameIndex) {
      const frames = this.flightReplay.activeFlightId
        ? this.flightReplayFrames[this.flightReplay.activeFlightId] || []
        : []

      if (!frames.length) {
        return
      }

      const nextIndex = clamp(Math.round(Number(frameIndex) || 0), 0, frames.length - 1)
      const nextStatus =
        nextIndex >= frames.length - 1
          ? 'completed'
          : this.flightReplay.status === 'playing'
            ? 'playing'
            : 'paused'

      if (nextIndex === this.flightReplay.frameIndex && nextStatus === this.flightReplay.status) {
        return
      }

      clearReplayTimer()

      this._setFlightReplayState({
        frameIndex: nextIndex,
        status: nextStatus,
        error: ''
      })

      if (this.flightReplay.status === 'playing') {
        this._scheduleFlightReplayAdvance()
      }
    },
    setFlightReplaySpeed(speed) {
      const numericSpeed = Number(speed)
      if (!Number.isFinite(numericSpeed) || numericSpeed <= 0) {
        return
      }

      this._setFlightReplayState({ speed: numericSpeed })

      if (this.flightReplay.status === 'playing') {
        this._scheduleFlightReplayAdvance()
      }
    },
    updateDroneState(newState) {
      const previousState = this.droneState
      const normalizedState = normalizeDroneStatePayload(newState)
      const mergedState = mergeDroneState(previousState, normalizedState)

      if (shouldResetTrackForNewFlight(previousState, mergedState)) {
        this.flightTrack = []
      }

      this.droneState = mergedState

      this.history.push(buildHistoryEntry(mergedState))

      if (this.history.length > HISTORY_LIMIT) {
        this.history.shift()
      }

      const rawFrame = buildRawStreamFrame(newState, mergedState.timestamp)

      this.rawStream.push(rawFrame)
      applyLiveFrameCache(this, rawFrame)

      if (this.rawStream.length > RAW_STREAM_LIMIT) {
        this.rawStream.shift()
        refreshLiveFrameCache(this)
      }

      if (hasValidPosition(mergedState.position)) {
        appendTrackPoint(this.flightTrack, mergedState)
        this.telemetryArchive.push(buildArchiveRecord(mergedState))

        if (this.telemetryArchive.length > TELEMETRY_ARCHIVE_LIMIT) {
          this.telemetryArchive.shift()
        }
      }

      schedulePersistence(this)
    },
    clearCurrentTrack() {
      this.flightTrack = []
      schedulePersistence(this)
    },
    requestDroneRecenter() {
      this.droneRecenterRequestId += 1
    },
    async openFlightHistoryPanel() {
      this.flightHistoryPanelOpen = true
      await this.fetchFlightSessions()
    },
    closeFlightHistoryPanel() {
      this.flightHistoryPanelOpen = false
      this.flightSessionsError = ''
    },
    clearSelectedFlightSessions() {
      this.selectedFlightSessionIds = []
    },
    async fetchFlightSessions(force = false) {
      if (this.flightSessionsLoading) {
        return this.flightSessions
      }

      if (!force && this.flightSessions.length > 0) {
        return this.flightSessions
      }

      this.flightSessionsLoading = true
      this.flightSessionsError = ''

      try {
        const response = await fetch(createApiUrl('/api/flights'))
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const payload = await response.json()
        const records = Array.isArray(payload?.records)
          ? payload.records.map((record) => normalizeFlightSessionSummary(record))
          : []

        this.flightSessions = records

        const validIds = new Set(records.map((record) => record.flight_id))
        this.selectedFlightSessionIds = this.selectedFlightSessionIds.filter((flightId) => validIds.has(flightId))

        const nextDetails = {}
        const nextTracks = {}
        const nextReplayFrames = {}
        for (const flightId of this.selectedFlightSessionIds) {
          if (this.flightSessionDetails[flightId]) {
            nextDetails[flightId] = this.flightSessionDetails[flightId]
          }
          if (this.flightSessionTracks[flightId]) {
            nextTracks[flightId] = this.flightSessionTracks[flightId]
          }
          if (this.flightReplayFrames[flightId]) {
            nextReplayFrames[flightId] = this.flightReplayFrames[flightId]
          }
        }
        this.flightSessionDetails = nextDetails
        this.flightSessionTracks = nextTracks
        this.flightReplayFrames = nextReplayFrames

        if (!validIds.has(this.flightReplay.activeFlightId)) {
          this.stopFlightReplay()
        }

        return records
      } catch (error) {
        this.flightSessionsError = '历史架次加载失败'
        console.warn('Failed to load flight sessions:', error)
        return []
      } finally {
        this.flightSessionsLoading = false
      }
    },
    async fetchFlightSessionDetail(flightId) {
      if (this.flightSessionDetails[flightId]) {
        return this.flightSessionDetails[flightId]
      }

      const response = await fetch(createApiUrl(`/api/flights/${encodeURIComponent(flightId)}`))
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

        const payload = await response.json()
        const summary = normalizeFlightSessionSummary(payload)
        const detail = {
          ...payload,
          ...summary,
          telemetry_records: sortRecordsByTimestamp(
            Array.isArray(payload?.telemetry_records) ? payload.telemetry_records : []
          ),
          psdk_records: sortRecordsByTimestamp(Array.isArray(payload?.psdk_records) ? payload.psdk_records : []),
          summary: payload?.summary || {}
        }

      this.flightSessionDetails = {
        ...this.flightSessionDetails,
        [flightId]: detail
      }
      this.flightSessionTracks = {
        ...this.flightSessionTracks,
        [flightId]: buildHistoricalTrack(detail)
      }
      this.flightReplayFrames = {
        ...this.flightReplayFrames,
        [flightId]: buildReplayFrames(detail)
      }

      return detail
    },
    async toggleFlightSessionSelection(flightId) {
      if (this.selectedFlightSessionIds.includes(flightId)) {
        this.selectedFlightSessionIds = this.selectedFlightSessionIds.filter((id) => id !== flightId)
        return false
      }

      await this.fetchFlightSessionDetail(flightId)
      this.selectedFlightSessionIds = [...this.selectedFlightSessionIds, flightId]
      return true
    },
    async deleteFlightSession(flightId, { refresh = true } = {}) {
      if (this.flightSessionsDeletingIds.includes(flightId)) {
        return false
      }

      this.flightSessionsDeletingIds = [...this.flightSessionsDeletingIds, flightId]
      this.flightSessionsError = ''

      try {
        const response = await fetch(createApiUrl(`/api/flights/${encodeURIComponent(flightId)}`), {
          method: 'DELETE'
        })
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        this.selectedFlightSessionIds = this.selectedFlightSessionIds.filter((id) => id !== flightId)
        this.flightSessions = this.flightSessions.filter((item) => item.flight_id !== flightId)

        const { [flightId]: _removedDetail, ...remainingDetails } = this.flightSessionDetails
        const { [flightId]: _removedTrack, ...remainingTracks } = this.flightSessionTracks
        const { [flightId]: _removedReplayFrames, ...remainingReplayFrames } = this.flightReplayFrames
        this.flightSessionDetails = remainingDetails
        this.flightSessionTracks = remainingTracks
        this.flightReplayFrames = remainingReplayFrames

        if (this.flightReplay.activeFlightId === flightId) {
          this.stopFlightReplay()
        }

        if (refresh) {
          await this.fetchFlightSessions(true)
        }

        return true
      } catch (error) {
        this.flightSessionsError = '删除历史架次失败'
        console.warn(`Failed to delete flight session ${flightId}:`, error)
        return false
      } finally {
        this.flightSessionsDeletingIds = this.flightSessionsDeletingIds.filter((id) => id !== flightId)
      }
    },
    async deleteSelectedFlightSessions() {
      const targets = [...new Set(this.selectedFlightSessionIds)]
      for (const flightId of targets) {
        const deleted = await this.deleteFlightSession(flightId, { refresh: false })
        if (!deleted) {
          return false
        }
      }

      await this.fetchFlightSessions(true)
      return true
    },
    addRawFrame(framePayload, fallbackTimestamp = null) {
      const rawFrame = buildRawStreamFrame(framePayload, fallbackTimestamp)

      this.rawStream.push(rawFrame)
      applyLiveFrameCache(this, rawFrame)

      if (this.rawStream.length > RAW_STREAM_LIMIT) {
        this.rawStream.shift()
        refreshLiveFrameCache(this)
      }

      schedulePersistence(this)
    },
    hydrateFromBackend(historyRecords = [], rawRecords = []) {
      const normalizedHistory = Array.isArray(historyRecords)
        ? historyRecords.map((record) => normalizeDroneStatePayload(record)).filter(Boolean)
        : []

      if (normalizedHistory.length > 0) {
        const chronologicalHistory = normalizedHistory.slice().reverse()
        const latestState = normalizedHistory[0]

        this.droneState = mergeDroneState(this.droneState, latestState)
        this.history = chronologicalHistory.slice(-HISTORY_LIMIT).map((state) => buildHistoryEntry(state))
        this.flightTrack = []
        this.telemetryArchive = []

        for (const state of chronologicalHistory) {
          appendTrackPoint(this.flightTrack, state)

          if (hasValidPosition(state.position)) {
            this.telemetryArchive.push(buildArchiveRecord(state))
          }
        }

        if (this.telemetryArchive.length > TELEMETRY_ARCHIVE_LIMIT) {
          this.telemetryArchive = this.telemetryArchive.slice(-TELEMETRY_ARCHIVE_LIMIT)
        }
      }

      if (Array.isArray(rawRecords) && rawRecords.length > 0) {
        this.rawStream = rawRecords
          .slice(-RAW_STREAM_LIMIT)
          .map((record, index) =>
            buildRawStreamFrame(record.telemetry || record, record.stored_at || record.timestamp || index)
          )
        refreshLiveFrameCache(this)

        if (normalizedHistory.length === 0) {
          const latestRawState = normalizeDroneStatePayload(rawRecords[rawRecords.length - 1] || {})
          this.droneState = mergeDroneState(this.droneState, latestRawState)
        }
      }

      schedulePersistence(this)
    },
    addAlert(alertData) {
      const alert = {
        id: Date.now(),
        ...alertData,
        read: false
      }

      this.alerts.unshift(alert)

      if (this.alerts.length > ALERT_LIMIT) {
        this.alerts.pop()
      }

      schedulePersistence(this)
    },
    setConnectionStatus(status) {
      this.isConnected = status
    }
  }
})
