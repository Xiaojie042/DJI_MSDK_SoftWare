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

const sanitizeTimestamp = (value) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null
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
  apiHost: sanitizeText(payload.apiHost ?? payload.api_host, defaults.apiHost),
  apiPort: sanitizePort(payload.apiPort ?? payload.api_port, defaults.apiPort),
  deviceListenPort: sanitizePort(
    payload.deviceListenPort ?? payload.device_listen_port,
    defaults.deviceListenPort
  )
})

const normalizeMqttTarget = (payload = {}, defaults = createDefaultMqttTarget()) => ({
  enabled: sanitizeBoolean(payload.enabled, defaults.enabled),
  host: sanitizeText(payload.host, defaults.host),
  port: sanitizePort(payload.port, defaults.port),
  clientId: sanitizeText(payload.clientId ?? payload.client_id, defaults.clientId),
  username: sanitizeText(payload.username, ''),
  password: String(payload.password ?? ''),
  topic: sanitizeText(payload.topic, defaults.topic),
  tls: sanitizeBoolean(payload.tls, defaults.tls)
})

const normalizeRuntimeConfigPayload = (payload = {}, defaults = createDefaultState()) => ({
  connection: normalizeConnectionConfig(payload.connection, defaults.connection),
  mqttLocal: normalizeMqttTarget(payload.mqtt_local ?? payload.mqttLocal, defaults.mqttLocal),
  mqttCloud: normalizeMqttTarget(payload.mqtt_cloud ?? payload.mqttCloud, defaults.mqttCloud),
  lastSavedAt: sanitizeTimestamp(payload.updated_at ?? payload.updatedAt)
    ? Math.round(Number(payload.updated_at ?? payload.updatedAt) * 1000)
    : defaults.lastSavedAt
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
  mqttTargets:
    payload.mqtt_targets && typeof payload.mqtt_targets === 'object'
      ? payload.mqtt_targets
      : payload.mqttTargets && typeof payload.mqttTargets === 'object'
        ? payload.mqttTargets
        : {},
  websocketClients: Number(payload.websocket_clients ?? payload.websocketClients ?? 0) || 0,
  uptimeSeconds: Number(payload.uptime_seconds ?? payload.uptimeSeconds ?? 0) || 0
})

function createDefaultState() {
  return {
    connection: createDefaultConnectionConfig(),
    mqttLocal: createDefaultMqttTarget('local'),
    mqttCloud: createDefaultMqttTarget('cloud'),
    backendStatus: null,
    statusLoading: false,
    statusError: '',
    lastSavedAt: null
  }
}

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

const buildBackendRuntimeConfigPayload = (state) => ({
  connection: {
    api_host: sanitizeText(state.connection.apiHost, getLocationHostname()),
    api_port: Number(sanitizePort(state.connection.apiPort, DEFAULT_API_PORT)),
    device_listen_port: Number(sanitizePort(state.connection.deviceListenPort, DEFAULT_DEVICE_LISTEN_PORT))
  },
  mqtt_local: {
    enabled: Boolean(state.mqttLocal.enabled),
    host: sanitizeText(state.mqttLocal.host),
    port: Number(sanitizePort(state.mqttLocal.port, createDefaultMqttTarget('local').port)),
    client_id: sanitizeText(state.mqttLocal.clientId, createDefaultMqttTarget('local').clientId),
    username: sanitizeText(state.mqttLocal.username),
    password: String(state.mqttLocal.password ?? ''),
    topic: sanitizeText(state.mqttLocal.topic, createDefaultMqttTarget('local').topic),
    tls: Boolean(state.mqttLocal.tls)
  },
  mqtt_cloud: {
    enabled: Boolean(state.mqttCloud.enabled),
    host: sanitizeText(state.mqttCloud.host),
    port: Number(sanitizePort(state.mqttCloud.port, createDefaultMqttTarget('cloud').port)),
    client_id: sanitizeText(state.mqttCloud.clientId, createDefaultMqttTarget('cloud').clientId),
    username: sanitizeText(state.mqttCloud.username),
    password: String(state.mqttCloud.password ?? ''),
    topic: sanitizeText(state.mqttCloud.topic, createDefaultMqttTarget('cloud').topic),
    tls: Boolean(state.mqttCloud.tls)
  }
})

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

    mergeRuntimeConfig(payload = {}) {
      const normalized = normalizeRuntimeConfigPayload(payload, createDefaultState())
      this.connection = normalized.connection
      this.mqttLocal = normalized.mqttLocal
      this.mqttCloud = normalized.mqttCloud
      this.lastSavedAt = normalized.lastSavedAt || Date.now()
      persistRuntimeConfig(this)
      return normalized
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

      return {
        connection: { ...this.connection },
        mqttLocal: { ...this.mqttLocal },
        mqttCloud: { ...this.mqttCloud }
      }
    },

    async fetchRuntimeConfig() {
      try {
        const response = await fetch(`${this.apiBaseUrl}/api/runtime-config`)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const payload = await response.json()
        this.statusError = ''
        return this.mergeRuntimeConfig(payload)
      } catch (error) {
        this.statusError = 'Failed to load backend runtime config.'
        console.warn('Failed to load backend runtime config:', error)
        return null
      }
    },

    async applyRuntimeConfig(payload = {}) {
      this.saveRuntimeConfig(payload)

      try {
        const response = await fetch(`${this.apiBaseUrl}/api/runtime-config`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(buildBackendRuntimeConfigPayload(this))
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const runtimePayload = await response.json()
        this.mergeRuntimeConfig(runtimePayload)
        this.statusError = ''
        await this.fetchBackendStatus()
        return true
      } catch (error) {
        this.statusError = 'Failed to sync runtime config to backend.'
        console.warn('Failed to sync runtime config to backend:', error)
        return false
      }
    },

    async fetchBackendStatus() {
      this.statusLoading = true

      try {
        const response = await fetch(`${this.apiBaseUrl}/api/status`)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const payload = await response.json()
        this.backendStatus = normalizeBackendStatus(payload)
        this.statusError = ''
        return this.backendStatus
      } catch (error) {
        this.backendStatus = null
        this.statusError = 'Current backend endpoint is unreachable.'
        console.warn('Failed to load backend status:', error)
        return null
      } finally {
        this.statusLoading = false
      }
    }
  }
})
