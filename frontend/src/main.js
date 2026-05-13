import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import logger from '@/utils/logger'
import { useRuntimeConfigStore } from '@/stores/runtimeConfigStore'

import 'leaflet/dist/leaflet.css'
import './assets/styles/variables.css'
import './assets/styles/global.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')

const runtimeConfigStore = useRuntimeConfigStore()
logger.setApiBaseUrl(runtimeConfigStore.apiBaseUrl)
logger.info('Frontend started', { apiBaseUrl: runtimeConfigStore.apiBaseUrl })
