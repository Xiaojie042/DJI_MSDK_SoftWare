<script setup>
import { computed, reactive, ref } from 'vue'
import { useRuntimeConfigStore } from '@/stores/runtimeConfigStore'

const configStore = useRuntimeConfigStore()
const isOpen = ref(false)

const draft = reactive({
  connection: {
    apiHost: '',
    apiPort: '',
    deviceListenPort: ''
  },
  mqttLocal: {
    enabled: false,
    host: '',
    port: '',
    clientId: '',
    username: '',
    password: '',
    topic: '',
    tls: false
  },
  mqttCloud: {
    enabled: false,
    host: '',
    port: '',
    clientId: '',
    username: '',
    password: '',
    topic: '',
    tls: false
  }
})

const syncDraftFromStore = () => {
  Object.assign(draft.connection, configStore.connection)
  Object.assign(draft.mqttLocal, configStore.mqttLocal)
  Object.assign(draft.mqttCloud, configStore.mqttCloud)
}

const openPanel = async () => {
  syncDraftFromStore()
  isOpen.value = true
  await configStore.fetchRuntimeConfig()
  syncDraftFromStore()
  void configStore.fetchBackendStatus()
}

const closePanel = () => {
  isOpen.value = false
}

const savePanel = async () => {
  const saved = await configStore.applyRuntimeConfig({
    connection: { ...draft.connection },
    mqttLocal: { ...draft.mqttLocal },
    mqttCloud: { ...draft.mqttCloud }
  })

  if (saved) {
    isOpen.value = false
  }
}

const resetPanel = () => {
  configStore.resetRuntimeConfig()
  syncDraftFromStore()
  void configStore.fetchBackendStatus()
}

const backendStatusTone = computed(() => {
  if (configStore.backendStatus) {
    return 'good'
  }
  if (configStore.statusError) {
    return 'danger'
  }
  return 'neutral'
})

const backendStatusText = computed(() => {
  if (configStore.statusLoading) {
    return '正在探测后端状态'
  }
  if (configStore.backendStatus) {
    return '后端状态已连接'
  }
  return configStore.statusError || '等待状态探测'
})

const backendListenPort = computed(
  () => configStore.backendStatus?.tcpServerPort || Number(configStore.connection.deviceListenPort) || '--'
)

const lastSavedLabel = computed(() => {
  if (!configStore.lastSavedAt) {
    return '未保存'
  }

  return new Date(configStore.lastSavedAt).toLocaleTimeString('zh-CN', { hour12: false })
})

const localMqttSummary = computed(() =>
  configStore.mqttLocal.enabled ? `${configStore.mqttLocal.host}:${configStore.mqttLocal.port}` : '本地 MQTT 已关闭'
)

const cloudMqttSummary = computed(() =>
  configStore.mqttCloud.enabled && configStore.mqttCloud.host
    ? `${configStore.mqttCloud.host}:${configStore.mqttCloud.port}`
    : '云端 MQTT 未启用'
)
</script>

<template>
  <div class="config-hub">
    <button class="config-launcher glass-panel" type="button" @click="openPanel">
      <div class="config-launcher__chips">
        <span class="config-chip">监听 {{ backendListenPort }}</span>
        <span class="config-chip" :class="{ 'config-chip--active': configStore.mqttLocal.enabled }">本地</span>
        <span class="config-chip" :class="{ 'config-chip--active': configStore.mqttCloud.enabled }">云端</span>
      </div>
    </button>

    <Teleport to="body">
      <div v-if="isOpen" class="config-overlay" @click.self="closePanel">
        <section class="config-modal glass-panel">
          <form class="config-shell" @submit.prevent="savePanel">
            <header class="config-modal__header">
              <div class="config-modal__title">
                <p class="config-eyebrow">TopBar 中控</p>
                <strong>连接与上传配置</strong>
                <span>保存后前端会按当前主机自动切换端口重新连接，本地 MQTT 与云端 MQTT 独立保存、互不影响。</span>
              </div>

              <button type="button" class="config-close" aria-label="关闭配置面板" @click="closePanel">
                &times;
              </button>
            </header>

            <div class="config-runtime">
              <span class="runtime-pill" :class="`runtime-pill--${backendStatusTone}`">{{ backendStatusText }}</span>
              <span class="runtime-pill">API {{ configStore.connection.apiHost }}:{{ configStore.connection.apiPort }}</span>
              <span class="runtime-pill">后端监听 {{ backendListenPort }}</span>
              <span class="runtime-pill">保存于 {{ lastSavedLabel }}</span>
            </div>

            <p v-if="configStore.statusError" class="config-error">{{ configStore.statusError }}</p>

            <div class="config-panels">
              <article class="config-card config-card--wide">
                <header class="section-head">
                  <p class="section-eyebrow">本机连接</p>
                  <strong>前端连接与监听预设</strong>
                  <span>API / WebSocket 端口会立即生效；设备监听端口先由前端保存，便于后续接入后端配置。</span>
                </header>

                <div class="form-grid form-grid--wide">
                  <label class="field">
                    <span>本机主机名</span>
                    <input v-model.trim="draft.connection.apiHost" type="text" placeholder="127.0.0.1" />
                  </label>

                  <label class="field">
                    <span>API / WS 端口</span>
                    <input v-model.trim="draft.connection.apiPort" type="number" min="1" max="65535" placeholder="8000" />
                    <small>保存后前端会切换到当前主机的这个端口。</small>
                  </label>

                  <label class="field">
                    <span>设备监听端口</span>
                    <input
                      v-model.trim="draft.connection.deviceListenPort"
                      type="number"
                      min="1"
                      max="65535"
                      placeholder="9001"
                    />
                    <small>当前后端实际监听：{{ backendListenPort }}</small>
                  </label>
                </div>
              </article>

              <article class="config-card" :class="{ 'config-card--disabled': !draft.mqttLocal.enabled }">
                <header class="section-head">
                  <p class="section-eyebrow">本地上传</p>
                  <strong>本地 MQTT</strong>
                  <span>{{ localMqttSummary }}</span>
                </header>

                <label class="toggle-row">
                  <div>
                    <strong>启用本地 MQTT 上传</strong>
                    <small>本地 Broker 配置保存在当前浏览器。</small>
                  </div>
                  <span class="toggle-switch">
                    <input v-model="draft.mqttLocal.enabled" type="checkbox" />
                    <span></span>
                  </span>
                </label>

                <div class="form-grid">
                  <label class="field">
                    <span>Broker 地址</span>
                    <input v-model.trim="draft.mqttLocal.host" type="text" placeholder="127.0.0.1" />
                  </label>

                  <label class="field">
                    <span>端口</span>
                    <input v-model.trim="draft.mqttLocal.port" type="number" min="1" max="65535" placeholder="1883" />
                  </label>

                  <label class="field">
                    <span>Client ID</span>
                    <input v-model.trim="draft.mqttLocal.clientId" type="text" placeholder="drone-monitor-local" />
                  </label>

                  <label class="field">
                    <span>Topic</span>
                    <input v-model.trim="draft.mqttLocal.topic" type="text" placeholder="drone/telemetry/local" />
                  </label>

                  <label class="field">
                    <span>用户名</span>
                    <input v-model.trim="draft.mqttLocal.username" type="text" placeholder="可选" />
                  </label>

                  <label class="field">
                    <span>密码</span>
                    <input v-model="draft.mqttLocal.password" type="password" placeholder="可选" />
                  </label>
                </div>

                <label class="check-row">
                  <input v-model="draft.mqttLocal.tls" type="checkbox" />
                  <span>启用 TLS 连接</span>
                </label>
              </article>

              <article class="config-card" :class="{ 'config-card--disabled': !draft.mqttCloud.enabled }">
                <header class="section-head">
                  <p class="section-eyebrow">云端上传</p>
                  <strong>云端 MQTT</strong>
                  <span>{{ cloudMqttSummary }}</span>
                </header>

                <label class="toggle-row">
                  <div>
                    <strong>启用云端 MQTT 上传</strong>
                    <small>独立于本地 MQTT，不会互相覆盖。</small>
                  </div>
                  <span class="toggle-switch">
                    <input v-model="draft.mqttCloud.enabled" type="checkbox" />
                    <span></span>
                  </span>
                </label>

                <div class="form-grid">
                  <label class="field">
                    <span>Broker 地址</span>
                    <input v-model.trim="draft.mqttCloud.host" type="text" placeholder="mqtt.example.com" />
                  </label>

                  <label class="field">
                    <span>端口</span>
                    <input v-model.trim="draft.mqttCloud.port" type="number" min="1" max="65535" placeholder="8883" />
                  </label>

                  <label class="field">
                    <span>Client ID</span>
                    <input v-model.trim="draft.mqttCloud.clientId" type="text" placeholder="drone-monitor-cloud" />
                  </label>

                  <label class="field">
                    <span>Topic</span>
                    <input v-model.trim="draft.mqttCloud.topic" type="text" placeholder="drone/telemetry/cloud" />
                  </label>

                  <label class="field">
                    <span>用户名</span>
                    <input v-model.trim="draft.mqttCloud.username" type="text" placeholder="云端账号" />
                  </label>

                  <label class="field">
                    <span>密码</span>
                    <input v-model="draft.mqttCloud.password" type="password" placeholder="云端密码" />
                  </label>
                </div>

                <label class="check-row">
                  <input v-model="draft.mqttCloud.tls" type="checkbox" />
                  <span>启用 TLS 连接</span>
                </label>
              </article>
            </div>

            <footer class="config-actions">
              <button type="button" class="action-btn action-btn--ghost" @click="resetPanel">恢复默认</button>
              <button type="button" class="action-btn action-btn--muted" @click="closePanel">取消</button>
              <button type="submit" class="action-btn action-btn--primary">保存并应用</button>
            </footer>
          </form>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.config-hub {
  width: 100%;
  max-width: 300px;
  display: flex;
  justify-content: center;
}

.config-launcher {
  width: min(100%, 300px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  padding: 0.44rem 0.7rem;
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(59, 130, 246, 0.06)),
    var(--bg-panel);
  border: 1px solid rgba(56, 189, 248, 0.18);
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.config-launcher:hover {
  transform: translateY(-1px);
  border-color: rgba(56, 189, 248, 0.28);
  box-shadow: 0 18px 36px rgba(2, 6, 23, 0.22);
}

.config-eyebrow,
.section-eyebrow {
  margin: 0;
  color: #7dd3fc;
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.config-launcher__chips {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
  justify-content: center;
  gap: 0.35rem;
}

.config-chip {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 0.52rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.48);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: #cbd5e1;
  font-size: 0.66rem;
  white-space: nowrap;
}

.config-chip--active {
  border-color: rgba(16, 185, 129, 0.24);
  background: rgba(16, 185, 129, 0.12);
  color: #d1fae5;
}

.config-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.2rem;
  background: rgba(2, 6, 23, 0.56);
  backdrop-filter: blur(12px);
}

.config-modal {
  width: min(1100px, calc(100vw - 2.4rem));
  max-height: calc(100vh - 2.4rem);
  overflow: hidden;
  border-radius: 26px;
  background: rgba(15, 23, 42, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 30px 80px rgba(2, 6, 23, 0.5);
}

.config-shell {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 2.4rem);
}

.config-modal__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.35rem 0.95rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.config-modal__title {
  display: flex;
  flex-direction: column;
  gap: 0.22rem;
}

.config-modal__title strong {
  color: #f8fafc;
  font-size: 1.12rem;
}

.config-modal__title span {
  color: #94a3b8;
  font-size: 0.8rem;
  line-height: 1.5;
}

.config-close {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(30, 41, 59, 0.82);
  color: #f8fafc;
  font-size: 1.4rem;
  line-height: 1;
}

.config-runtime {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  padding: 0.9rem 1.35rem 0;
}

.runtime-pill {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 0.8rem;
  border-radius: 999px;
  background: rgba(30, 41, 59, 0.56);
  border: 1px solid rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
  font-size: 0.74rem;
}

.runtime-pill--good {
  border-color: rgba(16, 185, 129, 0.24);
  background: rgba(16, 185, 129, 0.12);
  color: #d1fae5;
}

.runtime-pill--danger {
  border-color: rgba(248, 113, 113, 0.24);
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
}

.config-error {
  margin: 0;
  padding: 0.8rem 1.35rem 0;
  color: #fca5a5;
  font-size: 0.78rem;
}

.config-panels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  padding: 1rem 1.35rem 1.2rem;
  overflow: auto;
}

.config-card {
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
  padding: 1rem;
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.config-card--wide {
  grid-column: 1 / -1;
}

.config-card--disabled {
  border-color: rgba(148, 163, 184, 0.1);
  background: rgba(15, 23, 42, 0.34);
}

.section-head {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.section-head strong {
  color: #f8fafc;
  font-size: 0.98rem;
}

.section-head span {
  color: #94a3b8;
  font-size: 0.76rem;
  line-height: 1.5;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.8rem 0.9rem;
  border-radius: 16px;
  background: rgba(30, 41, 59, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.toggle-row strong {
  color: #f8fafc;
  font-size: 0.82rem;
}

.toggle-row small {
  display: block;
  margin-top: 0.12rem;
  color: #94a3b8;
  font-size: 0.72rem;
}

.toggle-switch {
  position: relative;
  display: inline-flex;
  width: 54px;
  height: 30px;
  flex-shrink: 0;
}

.toggle-switch input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.toggle-switch span {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: rgba(51, 65, 85, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.14);
  transition: background 0.2s ease, border-color 0.2s ease;
}

.toggle-switch span::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: #f8fafc;
  box-shadow: 0 4px 10px rgba(2, 6, 23, 0.28);
  transition: transform 0.2s ease;
}

.toggle-switch input:checked + span {
  background: rgba(14, 165, 233, 0.24);
  border-color: rgba(56, 189, 248, 0.24);
}

.toggle-switch input:checked + span::after {
  transform: translateX(24px);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}

.form-grid--wide {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
}

.field span {
  color: #cbd5e1;
  font-size: 0.76rem;
  font-weight: 600;
}

.field small {
  color: #64748b;
  font-size: 0.68rem;
  line-height: 1.45;
}

.field input {
  width: 100%;
  min-height: 40px;
  padding: 0 0.82rem;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.62);
  color: #f8fafc;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field input:focus {
  border-color: rgba(56, 189, 248, 0.34);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.12);
}

.check-row {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  color: #cbd5e1;
  font-size: 0.76rem;
}

.check-row input {
  width: 15px;
  height: 15px;
  accent-color: #38bdf8;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.7rem;
  padding: 0 1.35rem 1.25rem;
}

.action-btn {
  min-height: 40px;
  padding: 0 1rem;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 0.78rem;
  font-weight: 600;
}

.action-btn--ghost {
  border-color: rgba(248, 113, 113, 0.18);
  background: rgba(239, 68, 68, 0.1);
  color: #fecaca;
}

.action-btn--muted {
  border-color: rgba(148, 163, 184, 0.16);
  background: rgba(30, 41, 59, 0.82);
  color: #e2e8f0;
}

.action-btn--primary {
  border-color: rgba(56, 189, 248, 0.24);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.82), rgba(59, 130, 246, 0.82));
  color: #eff6ff;
}

@media (max-width: 1080px) {
  .config-panels,
  .form-grid,
  .form-grid--wide {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .config-launcher {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
  }

  .config-launcher__chips {
    justify-content: flex-start;
  }

  .config-overlay {
    padding: 0.75rem;
  }

  .config-modal {
    width: 100%;
    max-height: calc(100vh - 1.5rem);
  }

  .config-shell {
    max-height: calc(100vh - 1.5rem);
  }

  .config-modal__header,
  .toggle-row,
  .config-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .config-actions {
    padding-top: 0.3rem;
  }
}
</style>
