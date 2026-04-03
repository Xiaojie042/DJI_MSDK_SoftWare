import { defineStore } from 'pinia'

export const useDroneStore = defineStore('drone', {
  state: () => ({
    droneState: {
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
    },
    alerts: [],
    isConnected: false,
    history: []
  }),

  actions: {
    updateDroneState(newState) {
      this.droneState = { ...this.droneState, ...newState }
      // Keep a small history for charts if needed
      this.history.push({
        time: (new Date()).toLocaleTimeString(),
        altitude: newState.position?.altitude || 0,
        speed: newState.velocity?.horizontal || 0
      })
      if (this.history.length > 50) {
        this.history.shift()
      }
    },
    addAlert(alertData) {
      const alert = {
        id: Date.now(),
        ...alertData,
        read: false
      }
      this.alerts.unshift(alert)
      if (this.alerts.length > 20) {
        this.alerts.pop()
      }
    },
    setConnectionStatus(status) {
      this.isConnected = status
    }
  }
})
