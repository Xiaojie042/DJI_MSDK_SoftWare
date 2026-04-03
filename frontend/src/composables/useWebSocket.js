import { ref, onMounted, onUnmounted } from 'vue'
import { useDroneStore } from '@/stores/droneStore'

export function useWebSocket() {
  // Use current host for websocket to allow connections from other devices
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${wsProtocol}//${window.location.hostname}:8000/ws`;
  
  const store = useDroneStore()
  const socket = ref(null)
  let reconnectTimer = null

  const connect = () => {
    try {
      socket.value = new WebSocket(url)

      socket.value.onopen = () => {
        console.log('WebSocket Connected')
        store.setConnectionStatus(true)
        if (reconnectTimer) clearInterval(reconnectTimer)
      }

      socket.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'alert') {
            store.addAlert(data.data)
          } else if (data.drone_id) {
            store.updateDroneState(data)
          }
        } catch (e) {
          console.error('Error parsing WS message:', e)
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
    } catch (err) {
      console.error('WS Connection initiation failed:', err)
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

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    if (socket.value) {
      socket.value.close()
    }
    if (reconnectTimer) {
      clearInterval(reconnectTimer)
    }
  })

  return {
    socket
  }
}
