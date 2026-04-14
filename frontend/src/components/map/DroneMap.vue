<script setup>
import { computed, ref } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import { LCircleMarker, LMap, LMarker, LPolyline, LTileLayer } from '@vue-leaflet/vue-leaflet'
import L from 'leaflet'

const store = useDroneStore()
const zoom = ref(16)

const hasLivePosition = computed(() =>
  Number.isFinite(store.droneState.position.latitude) &&
  Number.isFinite(store.droneState.position.longitude) &&
  (store.droneState.position.latitude !== 0 || store.droneState.position.longitude !== 0)
)

const mapCenter = computed(() =>
  hasLivePosition.value
    ? [store.droneState.position.latitude, store.droneState.position.longitude]
    : [31.2304, 121.4737]
)

const pathCoords = computed(() => store.flightTrack.map((point) => [point.lat, point.lng]))
const highlightedTrail = computed(() => pathCoords.value.slice(-24))
const takeoffPoint = computed(() => pathCoords.value[0] || null)
const dronePosition = computed(() =>
  hasLivePosition.value ? [store.droneState.position.latitude, store.droneState.position.longitude] : null
)

const droneIcon = computed(() => {
  const batteryPercent = store.droneState.battery.percent || 0
  const accentColor =
    batteryPercent <= 20 ? '#ef4444' : batteryPercent <= 45 ? '#f59e0b' : '#22c55e'

  return L.divIcon({
    className: 'custom-drone-icon',
    html: `
      <div class="drone-marker" style="--accent:${accentColor};">
        <svg viewBox="0 0 64 64" fill="none" aria-hidden="true">
          <g transform="rotate(${store.droneState.heading || 0} 32 32)">
            <line x1="32" y1="32" x2="32" y2="9" stroke="#f8fafc" stroke-width="4" stroke-linecap="round" />
            <path d="M32 4L39 16H25L32 4Z" fill="#f8fafc" />
          </g>
          <circle cx="32" cy="32" r="17" fill="rgba(15, 23, 42, 0.92)" stroke="var(--accent)" stroke-width="3" />
          <circle cx="32" cy="32" r="7.5" fill="var(--accent)" />
          <path d="M20 22L12 14M44 22L52 14M20 42L12 50M44 42L52 50" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" />
          <circle cx="20" cy="22" r="4.2" fill="#0f172a" stroke="#38bdf8" stroke-width="2.2" />
          <circle cx="44" cy="22" r="4.2" fill="#0f172a" stroke="#38bdf8" stroke-width="2.2" />
          <circle cx="20" cy="42" r="4.2" fill="#0f172a" stroke="#38bdf8" stroke-width="2.2" />
          <circle cx="44" cy="42" r="4.2" fill="#0f172a" stroke="#38bdf8" stroke-width="2.2" />
        </svg>
      </div>
    `,
    iconSize: [64, 64],
    iconAnchor: [32, 32]
  })
})
</script>

<template>
  <div class="map-shell">
    <l-map v-model:zoom="zoom" :center="mapCenter" :useGlobalLeaflet="false" :zoom-control="false">
      <l-tile-layer
        url="http://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
        layer-type="base"
        name="GaodeMap"
        attribution="&copy; 高德地图"
      />

      <l-polyline
        v-if="pathCoords.length > 1"
        :lat-lngs="pathCoords"
        color="#22d3ee"
        :weight="7"
        :opacity="0.3"
      />
      <l-polyline
        v-if="highlightedTrail.length > 1"
        :lat-lngs="highlightedTrail"
        color="#3b82f6"
        :weight="5"
        :opacity="0.9"
      />

      <l-circle-marker
        v-if="takeoffPoint"
        :lat-lng="takeoffPoint"
        :radius="6"
        color="#22c55e"
        fill-color="#86efac"
        :fill-opacity="0.9"
      />

      <l-marker v-if="dronePosition" :lat-lng="dronePosition" :icon="droneIcon" />
    </l-map>
  </div>
</template>

<style>
.map-shell {
  width: 100%;
  height: 100%;
}

.map-shell .leaflet-container {
  width: 100%;
  height: 100%;
  background: #0f172a;
}

.custom-drone-icon {
  background: transparent;
  border: none;
}

.custom-drone-icon .drone-marker {
  width: 64px;
  height: 64px;
  filter: drop-shadow(0 10px 20px rgba(14, 165, 233, 0.36));
}

.custom-drone-icon svg {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
