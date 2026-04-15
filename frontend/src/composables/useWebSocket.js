import { onMounted, onUnmounted, ref } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

const DEFAULT_API_PORT = '8000'

const buildApiBase = () => {
  const configuredBase = import.meta.env.VITE_API_BASE_URL
  if (configuredBase) {
    return configuredBase.replace(/\/$/, '')
  }

  return ''
}

const buildWebSocketUrl = () => {
  const configuredUrl = import.meta.env.VITE_WS_URL
  if (configuredUrl) {
    return configuredUrl
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsHost = import.meta.env.VITE_API_HOST || window.location.hostname
  const wsPort = import.meta.env.VITE_API_PORT || DEFAULT_API_PORT
  return `${wsProtocol}//${wsHost}:${wsPort}/ws`
}

const createApiUrl = (path) => {
  const base = buildApiBase()
  return base ? `${base}${path}` : path
}

export function useWebSocket() {
  const url = buildWebSocketUrl()
  const store = useDroneStore()
  const socket = ref(null)
  let reconnectTimer = null

  const hydrateFromBackend = async () => {
    try {
      const [historyResponse, rawResponse] = await Promise.all([
        fetch(createApiUrl('/api/history?limit=300')),
        fetch(createApiUrl('/api/history/raw?limit=50'))
      ])

      if (!historyResponse.ok && !rawResponse.ok) {
        return
      }

      const historyPayload = historyResponse.ok ? await historyResponse.json() : { records: [] }
      const rawPayload = rawResponse.ok ? await rawResponse.json() : { records: [] }

      store.hydrateFromBackend(historyPayload.records || [], rawPayload.records || [])
    } catch (error) {
      console.warn('Failed to hydrate telemetry from backend:', error)
    }
  }

  const connect = () => {
    try {
      socket.value = new WebSocket(url)

      socket.value.onopen = () => {
        console.log('WebSocket Connected')
        store.setConnectionStatus(true)
        if (reconnectTimer) {
          clearInterval(reconnectTimer)
          reconnectTimer = null
        }
      }

      socket.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'alert') {
            store.addAlert(data.data)
          } else if (data.drone_id || data.droneId || data.telemetry) {
            store.updateDroneState(data)
          }
        } catch (error) {
          console.error('Error parsing WS message:', error)
        }
      }

      socket.value.onclose = () => {
        console.log('WebSocket Disconnected')
        store.setConnectionStatus(false)
        scheduleReconnect()
      }

      socket.value.onerror = (error) => {
        console.error('WebSocket Error:', error)
        socket.value.close()
      }
    } catch (error) {
      console.error('WS connection initiation failed:', error)
      scheduleReconnect()
    }
  }

  const scheduleReconnect = () => {
    if (!reconnectTimer) {
      reconnectTimer = setInterval(() => {
        console.log('Attempting to reconnect...')
        connect()
      }, 3000)
    }
  }

  onMounted(async () => {
    await hydrateFromBackend()
    connect()
  })

  onUnmounted(() => {
    if (socket.value) {
      socket.value.close()
    }
    if (reconnectTimer) {
      clearInterval(reconnectTimer)
      reconnectTimer = null
    }
  })

  return {
    socket
  }
}
