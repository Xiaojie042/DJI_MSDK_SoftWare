import { computed, onUnmounted, ref, watch } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import { useRuntimeConfigStore } from '@/stores/runtimeConfigStore'

export function useWebSocket() {
  const store = useDroneStore()
  const runtimeConfigStore = useRuntimeConfigStore()
  const socket = ref(null)
  const socketUrl = computed(() => runtimeConfigStore.webSocketUrl)
  let reconnectTimer = null

  const clearReconnectTimer = () => {
    if (reconnectTimer) {
      clearInterval(reconnectTimer)
      reconnectTimer = null
    }
  }

  const disposeSocket = () => {
    if (!socket.value) {
      return
    }

    socket.value.onopen = null
    socket.value.onmessage = null
    socket.value.onclose = null
    socket.value.onerror = null
    socket.value.close()
    socket.value = null
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
        fetchJsonWithTimeout('/api/history/raw?limit=50')
      ])

      if (!historyPayload && !rawPayload) {
        return
      }

      store.hydrateFromBackend(historyPayload?.records || [], rawPayload?.records || [])
    } catch (error) {
      console.warn('Failed to hydrate telemetry from backend:', error)
    }
  }

  const connect = (targetUrl = socketUrl.value) => {
    if (!targetUrl) {
      return
    }

    try {
      const nextSocket = new WebSocket(targetUrl)
      socket.value = nextSocket

      nextSocket.onopen = () => {
        console.log('WebSocket Connected')
        store.setConnectionStatus(true)
        clearReconnectTimer()
        void runtimeConfigStore.fetchBackendStatus()
      }

      nextSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'alert') {
            store.addAlert(data.data)
          } else if (data.type === 'psdk_data') {
            store.addRawFrame(data, data.timestamp)
          } else if (data.drone_id || data.droneId || data.telemetry) {
            store.updateDroneState(data)
          }
        } catch (error) {
          console.error('Error parsing WS message:', error)
        }
      }

      nextSocket.onclose = () => {
        console.log('WebSocket Disconnected')
        store.setConnectionStatus(false)
        socket.value = null
        scheduleReconnect()
      }

      nextSocket.onerror = (error) => {
        console.error('WebSocket Error:', error)
        nextSocket.close()
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
        connect(socketUrl.value)
      }, 3000)
    }
  }

  watch(
    socketUrl,
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

  onUnmounted(() => {
    clearReconnectTimer()
    disposeSocket()
  })

  return {
    socket
  }
}
