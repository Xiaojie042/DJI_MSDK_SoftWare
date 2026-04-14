<script setup>
import { computed, ref } from 'vue'
import { useDroneStore } from '@/stores/droneStore'
import { LCircleMarker, LMap, LMarker, LPolyline, LTileLayer } from '@vue-leaflet/vue-leaflet'
import L from 'leaflet'

defineEmits(['drone-click'])

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
        <svg viewBox="0 0 56 56" fill="none" aria-hidden="true">
          <g transform="rotate(${store.droneState.heading || 0} 28 28)">
            <line x1="28" y1="28" x2="28" y2="10" stroke="#f8fafc" stroke-width="3.2" stroke-linecap="round" />
            <path d="M28 5L34 15H22L28 5Z" fill="#f8fafc" />
          </g>
          <circle cx="28" cy="28" r="14" fill="rgba(15, 23, 42, 0.92)" stroke="var(--accent)" stroke-width="2.6" />
          <circle cx="28" cy="28" r="6.2" fill="var(--accent)" />
          <path d="M18 20L11 13M38 20L45 13M18 36L11 43M38 36L45 43" stroke="#38bdf8" stroke-width="2.6" stroke-linecap="round" />
          <circle cx="18" cy="20" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
          <circle cx="38" cy="20" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
          <circle cx="18" cy="36" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
          <circle cx="38" cy="36" r="3.6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.9" />
        </svg>
      </div>
    `,
    iconSize: [52, 52],
    iconAnchor: [26, 26]
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

      <l-marker v-if="dronePosition" :lat-lng="dronePosition" :icon="droneIcon" @click="$emit('drone-click')" />
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
  width: 52px;
  height: 52px;
  cursor: pointer;
  filter: drop-shadow(0 8px 16px rgba(14, 165, 233, 0.3));
}

.custom-drone-icon svg {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
