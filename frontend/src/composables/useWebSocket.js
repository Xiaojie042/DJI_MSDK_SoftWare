import { effectScope, onUnmounted, ref, watch } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import { useRuntimeConfigStore } from '@/stores/runtimeConfigStore'
import logger from '@/utils/logger'

const sharedSocket = ref(null)
let reconnectTimer = null
let stopSocketUrlWatch = null
let socketWatchScope = null
let activeConsumers = 0

const WEATHER_SAMPLE_KEYS = [
  'temperature',
  'temperature_c',
  'humidity',
  'humidity_percent',
  'windDirection',
  'wind_direction',
  'wind_direction_deg',
  'windSpeed',
  'wind_speed',
  'wind_speed_ms',
  'visibility',
  'visibility_m',
  'pressure',
  'pressure_hpa'
]

const hasWeatherSampleFields = (payload = {}) =>
  WEATHER_SAMPLE_KEYS.some((key) => {
    const value = payload[key]
    return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
  })

const normalizeWeatherSocketPayload = (payload) => {
  if (!payload || typeof payload !== 'object' || payload.type === 'psdk_data') {
    return null
  }

  if (payload.type === 'weather' && payload.data && typeof payload.data === 'object') {
    return {
      ...payload.data,
      timestamp: payload.data.timestamp ?? payload.timestamp
    }
  }

  return hasWeatherSampleFields(payload) ? payload : null
}

export function useWebSocket() {
  const store = useDroneStore()
  const runtimeConfigStore = useRuntimeConfigStore()
  const getSocketUrl = () => runtimeConfigStore.webSocketUrl
  activeConsumers += 1

  const clearReconnectTimer = () => {
    if (reconnectTimer) {
      clearInterval(reconnectTimer)
      reconnectTimer = null
    }
  }

  const disposeSocket = () => {
    if (!sharedSocket.value) {
      return
    }

    sharedSocket.value.onopen = null
    sharedSocket.value.onmessage = null
    sharedSocket.value.onclose = null
    sharedSocket.value.onerror = null
    sharedSocket.value.close()
    sharedSocket.value = null
  }

  const fetchJsonWithTimeout = async (path, timeoutMs = 2500) => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)

    try {
      const response = await fetch(`${runtimeConfigStore.apiBaseUrl}${path}`, { signal: controller.signal })
      if (!response.ok) {
        return null
      }

      return await response.json()
    } finally {
      window.clearTimeout(timer)
    }
  }

  const hydrateFromBackend = async () => {
    try {
      const [historyPayload, rawPayload] = await Promise.all([
        fetchJsonWithTimeout('/api/history?limit=300&latest_session_only=true'),
        fetchJsonWithTimeout('/api/history/raw?limit=720')
      ])

      if (!historyPayload && !rawPayload) {
        return
      }

      store.hydrateFromBackend(historyPayload?.records || [], rawPayload?.records || [])
    } catch (error) {
      logger.warn('Failed to hydrate telemetry from backend:', error)
    }
  }

  const connect = (targetUrl = getSocketUrl()) => {
    if (!targetUrl) {
      return
    }

    if (
      sharedSocket.value?.url === targetUrl &&
      [WebSocket.CONNECTING, WebSocket.OPEN].includes(sharedSocket.value.readyState)
    ) {
      return
    }

    disposeSocket()

    try {
      const nextSocket = new WebSocket(targetUrl)
      sharedSocket.value = nextSocket

      nextSocket.onopen = () => {
        logger.info('WebSocket connected', { url: targetUrl })
        store.setConnectionStatus(true)
        clearReconnectTimer()
        runtimeConfigStore.startDeviceMonitor()
        void runtimeConfigStore.fetchBackendStatus()
      }

      nextSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const weatherPayload = normalizeWeatherSocketPayload(data)
          if (data.type === 'alert') {
            store.addAlert(data.data)
          } else if (data.type === 'psdk_data') {
            store.addRawFrame(data, data.timestamp)
          } else if (weatherPayload) {
            store.addWeatherSample(weatherPayload)
          } else if (data.drone_id || data.droneId || data.telemetry) {
            store.updateDroneState(data)
          }
        } catch (error) {
          logger.error('Error parsing WS message:', error)
        }
      }

      nextSocket.onclose = () => {
        logger.warn('WebSocket disconnected')
        store.setConnectionStatus(false)
        if (sharedSocket.value === nextSocket) {
          sharedSocket.value = null
        }
        scheduleReconnect()
      }

      nextSocket.onerror = (error) => {
        logger.error('WebSocket error:', error)
        nextSocket.close()
      }
    } catch (error) {
      logger.error('WS connection initiation failed:', error)
      scheduleReconnect()
    }
  }

  const scheduleReconnect = () => {
    if (!reconnectTimer) {
      reconnectTimer = setInterval(() => {
        logger.debug('Attempting to reconnect...')
        connect(getSocketUrl())
      }, 3000)
    }
  }

  if (!socketWatchScope || !stopSocketUrlWatch) {
    socketWatchScope = effectScope(true)
    stopSocketUrlWatch = socketWatchScope.run(() =>
      watch(
        getSocketUrl,
        (nextUrl) => {
          clearReconnectTimer()
          store.setConnectionStatus(false)
          disposeSocket()

          if (!nextUrl) {
            return
          }

          connect(nextUrl)
          void hydrateFromBackend()
          void runtimeConfigStore.fetchBackendStatus()
        },
        { immediate: true }
      )
    )
  }

  onUnmounted(() => {
    // WebSocket 是应用级实时数据源，页面卸载时只减少使用计数，不关闭共享连接。
    activeConsumers = Math.max(0, activeConsumers - 1)
  })

  return {
    socket: sharedSocket
  }
}
