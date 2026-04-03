<script setup>
import { useDroneStore } from '@/stores/droneStore'
const store = useDroneStore()
</script>

<template>
  <div class="alert-panel glass-panel">
    <div class="header">
      <h3>System Alerts</h3>
      <span class="badge" v-if="store.alerts.length > 0">{{ store.alerts.length }}</span>
    </div>
    
    <div class="alerts-list">
      <div v-if="store.alerts.length === 0" class="no-alerts">
        No active alerts
      </div>
      
      <div v-for="alert in store.alerts" :key="alert.id" 
           class="alert-item" 
           :class="alert.level.toLowerCase()">
        <div class="alert-icon">
          <svg v-if="alert.level === 'CRITICAL'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="12 2 22 22 2 22"></polygon>
            <line x1="12" y1="8" x2="12" y2="14"></line>
            <line x1="12" y1="18" x2="12" y2="18"></line>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12" y2="16"></line>
          </svg>
        </div>
        <div class="alert-content">
          <div class="alert-time">{{ new Date(alert.timestamp * 1000).toLocaleTimeString() }}</div>
          <div class="alert-msg">{{ alert.message }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.alert-panel {
  padding: 1.5rem;
  border-radius: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

h3 {
  margin: 0;
  font-size: 1.2rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.badge {
  background: var(--danger);
  color: white;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: bold;
}

.alerts-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.no-alerts {
  color: var(--text-muted);
  text-align: center;
  padding: 2rem 0;
  font-style: italic;
}

.alert-item {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border-radius: 12px;
  background: var(--bg-card);
  border-left: 4px solid transparent;
}

.alert-item.critical {
  border-left-color: var(--danger);
  background: rgba(239, 68, 68, 0.1);
}

.alert-item.warning {
  border-left-color: var(--warning);
  background: rgba(245, 158, 11, 0.1);
}

.alert-icon {
  width: 24px;
  height: 24px;
}

.alert-item.critical .alert-icon {
  color: var(--danger);
}

.alert-item.warning .alert-icon {
  color: var(--warning);
}

.alert-content {
  flex: 1;
}

.alert-time {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 0.2rem;
}

.alert-msg {
  font-size: 0.95rem;
  color: var(--text-main);
  font-weight: 500;
}
</style>
