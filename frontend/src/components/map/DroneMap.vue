<script setup>
import { computed, ref, watch } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import { LMap, LTileLayer, LMarker, LPopup, LPolyline } from '@vue-leaflet/vue-leaflet'
import L from 'leaflet'

const store = useDroneStore()

const mapCenter = computed(() => {
  const pos = store.droneState.position
  return pos.latitude ? [pos.latitude, pos.longitude] : [31.2304, 121.4737] // Default Shanghai
})

const zoom = ref(16)

const droneIcon = computed(() => {
  return L.divIcon({
    className: 'custom-drone-icon',
    html: `<div class="drone-marker" style="transform: rotate(${store.droneState.heading || 0}deg)">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
               <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
               <polygon points="12 2 15 7 9 7 12 2"/>
               <!-- Basic drone shape representation -->
               <circle cx="12" cy="12" r="4" fill="var(--primary)" stroke="none"/>
               <path d="M7 7l10 10M17 7L7 17" stroke="var(--info)" stroke-width="2"/>
             </svg>
           </div>`,
    iconSize: [50, 50],
    iconAnchor: [25, 25]
  })
})

const pathCoords = ref([])

// Update path when position changes
watch(() => store.droneState.position, (newPos) => {
  if (newPos && newPos.latitude && newPos.longitude) {
    pathCoords.value.push([newPos.latitude, newPos.longitude])
    // Limit path length to prevent memory issues
    if (pathCoords.value.length > 2000) {
      pathCoords.value.shift()
    }
  }
}, { deep: true })

</script>

<template>
  <div style="height: 100%; width: 100%;">
    <l-map ref="map" v-model:zoom="zoom" :center="mapCenter" :useGlobalLeaflet="false">
      <!-- Gaode Maps TileLayer -->
      <l-tile-layer
        url="http://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
        layer-type="base"
        name="GaodeMap"
        attribution="&copy; 高德地图"
      />
      
      <!-- Drone Marker with Premium Embedded Popup -->
      <l-marker v-if="store.droneState.position.latitude" :lat-lng="[store.droneState.position.latitude, store.droneState.position.longitude]" :icon="droneIcon">
        <l-popup :options="{ minWidth: 280, className: 'premium-popup' }">
          <div class="popup-content">
            <div class="popup-header">
              <h4>机载实时数据</h4>
              <span class="status-badge" :class="store.droneState.flight_mode === 'GPS' ? 'good' : 'warn'">{{ store.droneState.flight_mode || '无状态' }}</span>
            </div>
            
            <div class="popup-grid">
              <div class="info-item">
                <span class="label">设备编号</span>
                <span class="val highlight">{{ store.droneState.drone_id }}</span>
              </div>
              <div class="info-item">
                <span class="label">飞行高度</span>
                <span class="val">{{ store.droneState.position.altitude?.toFixed(1) }} m</span>
              </div>
              <div class="info-item">
                <span class="label">水平速度</span>
                <span class="val">{{ store.droneState.velocity.horizontal?.toFixed(1) }} m/s</span>
              </div>
              <div class="info-item">
                <span class="label">偏航航向</span>
                <span class="val">{{ store.droneState.heading?.toFixed(0) }}°</span>
              </div>
              <div class="info-item loc">
                <span class="label">实时经纬度</span>
                <span class="val">{{ store.droneState.position.latitude?.toFixed(6) }}, {{ store.droneState.position.longitude?.toFixed(6) }}</span>
              </div>
            </div>

            <div class="popup-footer">
              <div class="battery-section">
                <span>电量 {{ store.droneState.battery.percent }}%</span>
                <div class="battery-bar">
                  <div class="fill" :style="{ width: `${store.droneState.battery.percent}%`, background: store.droneState.battery.percent > 20 ? 'linear-gradient(90deg, #10b981, #34d399)' : '#ef4444' }"></div>
                </div>
              </div>
              <div class="gps-section">
                <span>卫星 🛰️ {{ store.droneState.gps_signal || 0 }}</span>
              </div>
            </div>
          </div>
        </l-popup>
      </l-marker>

      <!-- Flight Path -->
      <l-polyline :lat-lngs="pathCoords" color="#3b82f6" :weight="4" :opacity="0.8" />
    </l-map>
  </div>
</template>

<style>
/* Reset Leaflet Popup Default Styles for Premium Look */
.premium-popup .leaflet-popup-content-wrapper {
  background: rgba(15, 23, 42, 0.9);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(59, 130, 246, 0.4);
  color: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.5);
  padding: 0;
  overflow: hidden;
}

.premium-popup .leaflet-popup-tip {
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(59, 130, 246, 0.4);
}

.premium-popup .leaflet-popup-content {
  margin: 0;
  width: 100% !important;
}

.popup-content {
  padding: 15px;
  font-family: inherit;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 10px;
  margin-bottom: 15px;
}

.popup-header h4 {
  margin: 0;
  font-size: 1.1rem;
  color: #f8fafc;
  font-weight: 600;
}

.status-badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 50px;
  font-weight: bold;
}
.status-badge.good { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
.status-badge.warn { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }

.popup-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 15px;
}

.info-item {
  display: flex;
  flex-direction: column;
}

.info-item.loc {
  grid-column: span 2;
}

.info-item .label {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-bottom: 3px;
}

.info-item .val {
  font-size: 0.9rem;
  font-weight: 500;
}
.info-item .val.highlight {
  color: #3b82f6;
}

.popup-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(0,0,0,0.3);
  padding: 10px;
  border-radius: 8px;
  font-size: 0.8rem;
}

.battery-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.battery-bar {
  width: 60px;
  height: 8px;
  background: #334155;
  border-radius: 4px;
  overflow: hidden;
}

.battery-bar .fill {
  height: 100%;
  transition: width 0.3s ease;
}

.gps-section {
  font-weight: bold;
  color: #e2e8f0;
}

/* Drone Marker Wrapper Effects */
.custom-drone-icon .drone-marker {
  width: 50px;
  height: 50px;
  background: rgba(30, 41, 59, 0.9);
  border: 2px solid var(--info);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 20px rgba(14, 165, 233, 0.6);
  transition: transform 0.3s ease;
}

.custom-drone-icon svg {
  width: 28px;
  height: 28px;
}
</style>
