import { defineStore } from 'pinia'

const LOCAL_CACHE_KEY = 'drone-monitor:telemetry-cache:v1'
const TRACK_LIMIT = 1500
const HISTORY_LIMIT = 50
const RAW_STREAM_LIMIT = 50
const ALERT_LIMIT = 20
const TELEMETRY_ARCHIVE_LIMIT = 300

let persistTimer = null

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)
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
  rc_signal: 0
})

const createDefaultState = () => ({
  droneState: createDefaultDroneState(),
  alerts: [],
  isConnected: false,
  history: [],
  rawStream: [],
  flightTrack: [],
  telemetryArchive: [],
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

    return {
      ...defaults,
      droneState: mergeDroneState(defaults.droneState, parsed.droneState || {}),
      alerts: Array.isArray(parsed.alerts) ? parsed.alerts.slice(0, ALERT_LIMIT) : defaults.alerts,
      history: Array.isArray(parsed.history) ? parsed.history.slice(-HISTORY_LIMIT) : defaults.history,
      rawStream: Array.isArray(parsed.rawStream) ? parsed.rawStream.slice(-RAW_STREAM_LIMIT) : defaults.rawStream,
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

  const nextSavedAt = Date.now()
  store.localCacheMeta = {
    ...store.localCacheMeta,
    lastSavedAt: nextSavedAt
  }

  if (persistTimer) {
    window.clearTimeout(persistTimer)
  }

  persistTimer = window.setTimeout(() => {
    persistStateToLocal(store)
    persistTimer = null
  }, 250)
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
    }
  },

  actions: {
    updateDroneState(newState) {
      const mergedState = mergeDroneState(this.droneState, newState)

      this.droneState = mergedState

      const currentTime = new Date().toLocaleTimeString('zh-CN', { hour12: false })

      this.history.push({
        time: currentTime,
        altitude: mergedState.position.altitude || 0,
        speed: mergedState.velocity.horizontal || 0
      })

      if (this.history.length > HISTORY_LIMIT) {
        this.history.shift()
      }

      const rawFrame = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        time: currentTime,
        data: newState
      }

      this.rawStream.push(rawFrame)

      if (this.rawStream.length > RAW_STREAM_LIMIT) {
        this.rawStream.shift()
      }

      if (hasValidPosition(mergedState.position)) {
        const nextPoint = {
          lat: mergedState.position.latitude,
          lng: mergedState.position.longitude,
          altitude: mergedState.position.altitude || 0,
          heading: mergedState.heading || 0,
          timestamp: mergedState.timestamp || Date.now() / 1000
        }

        const lastPoint = this.flightTrack[this.flightTrack.length - 1]
        const shouldAppend =
          !lastPoint ||
          Math.abs(lastPoint.lat - nextPoint.lat) > 0.00001 ||
          Math.abs(lastPoint.lng - nextPoint.lng) > 0.00001 ||
          Math.abs(lastPoint.altitude - nextPoint.altitude) > 0.8

        if (shouldAppend) {
          this.flightTrack.push(nextPoint)
        }

        if (this.flightTrack.length > TRACK_LIMIT) {
          this.flightTrack.shift()
        }

        this.telemetryArchive.push(buildArchiveRecord(mergedState))

        if (this.telemetryArchive.length > TELEMETRY_ARCHIVE_LIMIT) {
          this.telemetryArchive.shift()
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
