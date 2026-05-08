import { createRouter, createWebHistory } from 'vue-router'
import MonitorView from '../views/MonitorView.vue'
import WeatherChartsView from '../views/WeatherChartsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'monitor',
      component: MonitorView
    },
    {
      path: '/weather-charts',
      name: 'weather-charts',
      component: WeatherChartsView
    }
  ]
})

export default router
