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
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  })
})

const pathCoords = ref([])

// Update path when position changes
watch(() => store.droneState.position, (newPos) => {
  if (newPos && newPos.latitude && newPos.longitude) {
    pathCoords.value.push([newPos.latitude, newPos.longitude])
    // Limit path length to prevent memory issues
    if (pathCoords.value.length > 1000) {
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
      
      <!-- Drone Marker -->
      <l-marker v-if="store.droneState.position.latitude" :lat-lng="[store.droneState.position.latitude, store.droneState.position.longitude]" :icon="droneIcon">
        <l-popup>
          <div><strong>ID:</strong> {{ store.droneState.drone_id }}</div>
          <div><strong>Mode:</strong> {{ store.droneState.flight_mode }}</div>
          <div><strong>Alt:</strong> {{ store.droneState.position.altitude?.toFixed(1) }} m</div>
        </l-popup>
      </l-marker>

      <!-- Flight Path -->
      <l-polyline :lat-lngs="pathCoords" color="#3b82f6" :weight="4" :opacity="0.8" />
    </l-map>
  </div>
</template>

<style>
.custom-drone-icon .drone-marker {
  width: 40px;
  height: 40px;
  background: rgba(30, 41, 59, 0.8);
  border: 2px solid var(--info);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 15px rgba(14, 165, 233, 0.5);
  transition: transform 0.3s ease;
}

.custom-drone-icon svg {
  width: 24px;
  height: 24px;
}
</style>
