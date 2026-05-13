import { createRouter, createWebHistory } from 'vue-router'
import MonitorView from '../views/MonitorView.vue'
import WeatherChartsView from '../views/WeatherChartsView.vue'
import config from '@/utils/config'

const routes = [
  {
    path: '/',
    name: 'monitor',
    component: MonitorView
  }
]

if (config.ENABLE_WEATHER_CHARTS) {
  routes.push({
    path: '/weather-charts',
    name: 'weather-charts',
    component: WeatherChartsView
  })
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
