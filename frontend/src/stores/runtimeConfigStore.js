import { defineStore } from 'pinia'

const RUNTIME_CONFIG_KEY = 'drone-monitor:runtime-config:v1'
const DEFAULT_API_PORT = '8000'
const DEFAULT_DEVICE_LISTEN_PORT = '9001'

const sanitizeText = (value, fallback = '') => {
  const normalized = String(value ?? '').trim()
  return normalized || fallback
}

const sanitizePort = (value, fallback) => {
  const numeric = Number(String(value ?? '').trim())
  if (!Number.isFinite(numeric)) {
    return String(fallback)
  }

  const rounded = Math.round(numeric)
  if (rounded < 1 || rounded > 65535) {
    return String(fallback)
  }

  return String(rounded)
}

const sanitizeBoolean = (value, fallback = false) => {
  if (typeof value === 'boolean') {
    return value
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

  if (typeof value === 'number') {
    return Boolean(value)
  }

  return fallback
}

const getLocationHostname = () => {
  if (typeof window === 'undefined') {
    return '127.0.0.1'
  }

  return window.location.hostname || '127.0.0.1'
}

const getHttpProtocol = () => {
  if (typeof window === 'undefined') {
    return 'http:'
  }

  return window.location.protocol === 'https:' ? 'https:' : 'http:'
}

const getWebSocketProtocol = () => (getHttpProtocol() === 'https:' ? 'wss:' : 'ws:')

const parseConfiguredBaseUrl = () => {
  const configuredBase = import.meta.env.VITE_API_BASE_URL
  if (!configuredBase) {
    return null
  }

  try {
    const baseOrigin =
      typeof window !== 'undefined' ? window.location.origin : `${getHttpProtocol()}//${getLocationHostname()}`
    const url = new URL(configuredBase, baseOrigin)
    return {
      host: url.hostname || getLocationHostname(),
      port: url.port || DEFAULT_API_PORT
    }
  } catch (error) {
    console.warn('Failed to parse VITE_API_BASE_URL, falling back to window location:', error)
    return null
  }
}

const createDefaultConnectionConfig = () => {
  const parsedBase = parseConfiguredBaseUrl()
  return {
    apiHost: sanitizeText(parsedBase?.host || import.meta.env.VITE_API_HOST, getLocationHostname()),
    apiPort: sanitizePort(parsedBase?.port || import.meta.env.VITE_API_PORT, DEFAULT_API_PORT),
    deviceListenPort: sanitizePort(DEFAULT_DEVICE_LISTEN_PORT, DEFAULT_DEVICE_LISTEN_PORT)
  }
}

const createDefaultMqttTarget = (kind = 'local') =>
  kind === 'cloud'
    ? {
        enabled: false,
        host: '',
        port: '8883',
        clientId: 'drone-monitor-cloud',
        username: '',
        password: '',
        topic: 'drone/telemetry/cloud',
        tls: true
      }
    : {
        enabled: true,
        host: '127.0.0.1',
        port: '1883',
        clientId: 'drone-monitor-local',
        username: '',
        password: '',
        topic: 'drone/telemetry/local',
        tls: false
      }

const normalizeConnectionConfig = (payload = {}, defaults = createDefaultConnectionConfig()) => ({
  apiHost: sanitizeText(payload.apiHost, defaults.apiHost),
  apiPort: sanitizePort(payload.apiPort, defaults.apiPort),
  deviceListenPort: sanitizePort(payload.deviceListenPort, defaults.deviceListenPort)
})

const normalizeMqttTarget = (payload = {}, defaults = createDefaultMqttTarget()) => ({
  enabled: sanitizeBoolean(payload.enabled, defaults.enabled),
  host: sanitizeText(payload.host, defaults.host),
  port: sanitizePort(payload.port, defaults.port),
  clientId: sanitizeText(payload.clientId, defaults.clientId),
  username: sanitizeText(payload.username, ''),
  password: String(payload.password ?? ''),
  topic: sanitizeText(payload.topic, defaults.topic),
  tls: sanitizeBoolean(payload.tls, defaults.tls)
})

const buildApiBaseUrl = (host, port) =>
  `${getHttpProtocol()}//${sanitizeText(host, getLocationHostname())}:${sanitizePort(port, DEFAULT_API_PORT)}`

const buildWebSocketUrl = (host, port) =>
  `${getWebSocketProtocol()}//${sanitizeText(host, getLocationHostname())}:${sanitizePort(port, DEFAULT_API_PORT)}/ws`

const normalizeBackendStatus = (payload = {}) => ({
  status: payload.status || 'unknown',
  tcpServerPort: Number(payload.tcp_server_port ?? payload.tcpServerPort ?? 0) || 0,
  mqttBroker: payload.mqtt_broker || payload.mqttBroker || '',
  mqttConnected: Boolean(payload.mqtt_connected ?? payload.mqttConnected),
  websocketClients: Number(payload.websocket_clients ?? payload.websocketClients ?? 0) || 0,
  uptimeSeconds: Number(payload.uptime_seconds ?? payload.uptimeSeconds ?? 0) || 0
})

const createDefaultState = () => ({
  connection: createDefaultConnectionConfig(),
  mqttLocal: createDefaultMqttTarget('local'),
  mqttCloud: createDefaultMqttTarget('cloud'),
  backendStatus: null,
  statusLoading: false,
  statusError: '',
  lastSavedAt: null
})

const persistRuntimeConfig = (state) => {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(
      RUNTIME_CONFIG_KEY,
      JSON.stringify({
        connection: state.connection,
        mqttLocal: state.mqttLocal,
        mqttCloud: state.mqttCloud,
        lastSavedAt: state.lastSavedAt
      })
    )
  } catch (error) {
    console.warn('Failed to persist runtime config:', error)
  }
}

const readPersistedState = () => {
  const defaults = createDefaultState()
  if (typeof window === 'undefined') {
    return defaults
  }

  try {
    const raw = window.localStorage.getItem(RUNTIME_CONFIG_KEY)
    if (!raw) {
      return defaults
    }

    const parsed = JSON.parse(raw)
    return {
      ...defaults,
      connection: normalizeConnectionConfig(parsed.connection, defaults.connection),
      mqttLocal: normalizeMqttTarget(parsed.mqttLocal, defaults.mqttLocal),
      mqttCloud: normalizeMqttTarget(parsed.mqttCloud, defaults.mqttCloud),
      lastSavedAt: parsed.lastSavedAt || null
    }
  } catch (error) {
    console.warn('Failed to restore runtime config:', error)
    return defaults
  }
}

export const useRuntimeConfigStore = defineStore('runtime-config', {
  state: () => readPersistedState(),

  getters: {
    apiBaseUrl(state) {
      return buildApiBaseUrl(state.connection.apiHost, state.connection.apiPort)
    },
    webSocketUrl(state) {
      return buildWebSocketUrl(state.connection.apiHost, state.connection.apiPort)
    }
  },

  actions: {
    saveRuntimeConfig(payload = {}) {
      this.connection = normalizeConnectionConfig(payload.connection, this.connection)
      this.mqttLocal = normalizeMqttTarget(payload.mqttLocal, this.mqttLocal)
      this.mqttCloud = normalizeMqttTarget(payload.mqttCloud, this.mqttCloud)
      this.lastSavedAt = Date.now()
      persistRuntimeConfig(this)
    },

    resetRuntimeConfig() {
      const defaults = createDefaultState()
      this.connection = defaults.connection
      this.mqttLocal = defaults.mqttLocal
      this.mqttCloud = defaults.mqttCloud
      this.backendStatus = null
      this.statusLoading = false
      this.statusError = ''
      this.lastSavedAt = Date.now()
      persistRuntimeConfig(this)
    },

    async fetchBackendStatus() {
      this.statusLoading = true
      this.statusError = ''

      try {
        const response = await fetch(`${this.apiBaseUrl}/api/status`)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const payload = await response.json()
        this.backendStatus = normalizeBackendStatus(payload)
        return this.backendStatus
      } catch (error) {
        this.backendStatus = null
        this.statusError = '当前端口暂时无法获取后端状态'
        console.warn('Failed to load backend status:', error)
        return null
      } finally {
        this.statusLoading = false
      }
    }
  }
})
