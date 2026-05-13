<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRuntimeConfigStore } from '@/stores/runtimeConfigStore'
import logger from '@/utils/logger'

const configStore = useRuntimeConfigStore()
const PREVIEW_SIZE_STORAGE_KEY = 'drone-monitor:live-preview-width:v1'
const PREVIEW_DEFAULT_WIDTH = 450
const PREVIEW_MIN_WIDTH = 320
const PREVIEW_MAX_WIDTH = 960
const PREVIEW_WIDTH_STEP = 80
const PREVIEW_ASPECT_RATIO = 16 / 9

const readStoredPreviewWidth = () => {
  if (typeof window === 'undefined') {
    return PREVIEW_DEFAULT_WIDTH
  }

  const parsed = Number(window.localStorage.getItem(PREVIEW_SIZE_STORAGE_KEY))
  return Number.isFinite(parsed) ? parsed : PREVIEW_DEFAULT_WIDTH
}

const expanded = ref(false)
const errorMessage = ref('')
const infoMessage = ref('')
const logs = ref([])
const logWindow = ref(null)
const previewVideo = ref(null)
const rtmpStatus = ref(null)
const gbStatus = ref(null)
const previewVisible = ref(false)
const previewMinimized = ref(false)
const previewPlaying = ref(true)
const previewError = ref('')
const previewMode = ref('flv')
const previewWidth = ref(readStoredPreviewWidth())
const previewPosition = reactive({
  x: 24,
  y: 88
})
const meta = reactive({
  lanIp: '',
  rtmpPushUrl: '',
  dependencies: null
})
const loading = reactive({
  config: false,
  save: false,
  rtmp: false,
  gb: false,
  restart: false,
  refresh: false
})

let refreshTimer = null
let flvPlayer = null
let flvjsModule = null
let rtcPeerConnection = null
let rtcRemoteStream = null
let previewDrag = null
let previewResize = null
let previewFallbackTimer = null

const createDefaultConfig = () => ({
  rtmp: {
    service_provider: 'zlmediakit',
    listen_host: '0.0.0.0',
    port: 1935,
    app: 'live',
    stream: 'drone',
    zlm_executable_path: '',
    zlm_work_dir: '',
    zlm_config_path: '',
    zlm_http_host: '127.0.0.1',
    zlm_http_port: 18080,
    zlm_secret: '035c73f7-bb44-4885-a715-d9eb2d1925cc'
  },
  gb28181: {
    sip_server_ip: '',
    sip_server_port: 5060,
    sip_domain: '',
    sip_server_id: '',
    device_id: '',
    channel_id: '',
    local_sip_port: 5062,
    local_rtp_port_start: 30000,
    local_rtp_port_end: 30100,
    password: '',
    transport: 'UDP',
    ssrc: '',
    auto_reconnect: true,
    heartbeat_interval: 60,
    rtmp_input_url: 'rtmp://127.0.0.1/live/drone',
    bridge_executable_path: '',
    bridge_work_dir: '',
    bridge_config_path: '',
    bridge_command_template: ''
  }
})

const draft = reactive(createDefaultConfig())

const apiUrl = (path) => `${configStore.apiBaseUrl}${path}`

const requestJson = async (path, options = {}) => {
  const response = await fetch(apiUrl(path), options)
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = await response.json()
      detail = payload?.detail || detail
    } catch (error) {
      // Keep HTTP status as fallback.
    }
    throw new Error(detail)
  }
  return response.json()
}

const mergeConfig = (payload = {}) => {
  const defaults = createDefaultConfig()
  Object.assign(draft.rtmp, defaults.rtmp, payload.rtmp || {})
  Object.assign(draft.gb28181, defaults.gb28181, payload.gb28181 || {})
  meta.lanIp = payload.lan_ip || ''
  meta.rtmpPushUrl = payload.rtmp_push_url || ''
  meta.dependencies = payload.dependencies || null
}

const refreshConfig = async () => {
  loading.config = true
  try {
    const payload = await requestJson('/api/live/config')
    mergeConfig(payload)
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = `直播配置加载失败：${error.message}`
  } finally {
    loading.config = false
  }
}

const refreshStatus = async () => {
  loading.refresh = true
  try {
    const [rtmpPayload, gbPayload, logPayload] = await Promise.all([
      requestJson('/api/live/rtmp/status'),
      requestJson('/api/live/gb28181/status'),
      requestJson('/api/live/logs?limit=160')
    ])
    rtmpStatus.value = rtmpPayload
    gbStatus.value = gbPayload
    logs.value = Array.isArray(logPayload?.lines) ? logPayload.lines : []
    if (rtmpPayload?.lan_ip) {
      meta.lanIp = rtmpPayload.lan_ip
    }
    if (rtmpPayload?.push_url) {
      meta.rtmpPushUrl = rtmpPayload.push_url
    }
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = `直播状态刷新失败：${error.message}`
  } finally {
    loading.refresh = false
  }
}

const saveConfig = async () => {
  loading.save = true
  infoMessage.value = ''
  try {
    const payload = await requestJson('/api/live/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draft)
    })
    mergeConfig(payload)
    infoMessage.value = '配置已保存'
    await refreshStatus()
  } catch (error) {
    errorMessage.value = `配置保存失败：${error.message}`
  } finally {
    loading.save = false
  }
}

const postAction = async (path, key, successText) => {
  loading[key] = true
  infoMessage.value = ''
  try {
    const payload = await requestJson(path, { method: 'POST' })
    if (path.includes('/rtmp/')) {
      rtmpStatus.value = payload
    } else {
      gbStatus.value = payload
    }
    infoMessage.value = successText
    await refreshStatus()
  } catch (error) {
    errorMessage.value = error.message
    await refreshStatus()
  } finally {
    loading[key] = false
  }
}

const startRtmp = async () => postAction('/api/live/rtmp/start', 'rtmp', 'RTMP 服务启动请求已发送')
const stopRtmp = async () => postAction('/api/live/rtmp/stop', 'rtmp', 'RTMP 服务停止请求已发送')
const startGb = async () => postAction('/api/live/gb28181/start', 'gb', 'GB28181 转发启动请求已发送')
const stopGb = async () => postAction('/api/live/gb28181/stop', 'gb', 'GB28181 转发停止请求已发送')

const restartLiveServices = async () => {
  loading.restart = true
  infoMessage.value = ''
  errorMessage.value = ''
  try {
    const payload = await requestJson('/api/live/restart', { method: 'POST' })
    if (payload?.rtmp) {
      rtmpStatus.value = payload.rtmp
    }
    if (payload?.gb28181) {
      gbStatus.value = payload.gb28181
    }
    infoMessage.value = payload?.message || '直播相关服务重启请求已发送'
    await refreshStatus()
    if (previewVisible.value && !previewMinimized.value) {
      await initPreviewPlayer()
    }
  } catch (error) {
    errorMessage.value = `重启直播服务失败：${error.message}`
    await refreshStatus()
  } finally {
    loading.restart = false
  }
}

const generateSsrc = () => {
  draft.gb28181.ssrc = String(Math.floor(1000000000 + Math.random() * 9000000000))
}

const copyPushUrl = async () => {
  const value = rtmpPushUrl.value
  if (!value || typeof navigator === 'undefined' || !navigator.clipboard) {
    return
  }
  await navigator.clipboard.writeText(value)
  infoMessage.value = 'RTMP 地址已复制'
}

const toggleExpanded = async () => {
  expanded.value = !expanded.value
  if (expanded.value) {
    await Promise.all([refreshConfig(), refreshStatus()])
  }
}

const closePanel = () => {
  expanded.value = false
}

const buildZlmHttpOrigin = () => {
  const configuredHost = String(draft.rtmp.zlm_http_host || '').trim()
  const browserHost = typeof window !== 'undefined' ? window.location.hostname : ''
  const apiHost = configStore.connection?.apiHost || (typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1')
  const localHosts = ['0.0.0.0', '127.0.0.1', 'localhost', '::']
  const host =
    !configuredHost || localHosts.includes(configuredHost)
      ? browserHost && !localHosts.includes(browserHost) ? browserHost : apiHost
      : configuredHost
  const port = Number(draft.rtmp.zlm_http_port || 80)
  const portPart = port === 80 ? '' : `:${port}`
  return `http://${host}${portPart}`
}

const buildZlmPlayUrl = (suffix) => {
  const app = encodeURIComponent(draft.rtmp.app || 'live')
  const stream = encodeURIComponent(draft.rtmp.stream || 'drone')
  return `${buildZlmHttpOrigin()}/${app}/${stream}.${suffix}`
}

const buildZlmWebrtcUrl = () => {
  const params = new URLSearchParams({
    app: draft.rtmp.app || 'live',
    stream: draft.rtmp.stream || 'drone',
    type: 'play',
    preferred_tcp: '1'
  })
  const secret = String(draft.rtmp.zlm_secret || '').trim()
  if (secret) {
    params.set('secret', secret)
  }
  return `${buildZlmHttpOrigin()}/index/api/webrtc?${params.toString()}`
}

const rtmpPushUrl = computed(() => meta.rtmpPushUrl || rtmpStatus.value?.push_url || 'rtmp://127.0.0.1/live/drone')
const httpFlvUrl = computed(() => buildZlmPlayUrl('live.flv'))
const fmp4Url = computed(() => buildZlmPlayUrl('live.mp4'))
const webrtcPlayUrl = computed(() => buildZlmWebrtcUrl())
const lanIp = computed(() => meta.lanIp || rtmpStatus.value?.lan_ip || '127.0.0.1')
const hasRtmpStream = computed(() => Boolean(rtmpStatus.value?.has_drone_stream))
const rtmpRunning = computed(() => Boolean(rtmpStatus.value?.running))
const gbRunning = computed(() => Boolean(gbStatus.value?.process_running))
const liveActionBusy = computed(() => loading.rtmp || loading.gb || loading.restart)

const numberOf = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const gbMediaActive = computed(() => {
  const bitrate = numberOf(gbStatus.value?.bitrate_kbps || rtmpStatus.value?.bitrate_kbps)
  const fps = numberOf(gbStatus.value?.fps ?? rtmpStatus.value?.fps)
  return bitrate > 0 || fps > 0
})

const gbStreamingLocallyConfirmed = computed(() => {
  const rawStatus = gbStatus.value?.streaming_status || ''
  return gbRunning.value
    && gbStatus.value?.registration_status === 'registered'
    && hasRtmpStream.value
    && gbMediaActive.value
    && ['streaming', 'negotiating'].includes(rawStatus)
})

const effectiveGbStreamingStatus = computed(() => {
  const rawStatus = gbStatus.value?.streaming_status || ''
  if (rawStatus === 'failed') return rawStatus
  if (gbStreamingLocallyConfirmed.value) return 'streaming'
  return rawStatus
})

const isAuxiliaryMediaConnectError = (message = '') => (
  /sua_init_media_tcp/i.test(message)
  && /connect to/i.test(message)
  && /fail/i.test(message)
)

const rtmpTone = computed(() => {
  if (hasRtmpStream.value) return 'good'
  if (rtmpRunning.value) return 'warn'
  return 'idle'
})

const streamTone = computed(() => (hasRtmpStream.value ? 'good' : 'idle'))
const gbRegistrationTone = computed(() => {
  const status = gbStatus.value?.registration_status || ''
  if (status === 'registered') return 'good'
  if (status === 'failed') return 'bad'
  if (gbRunning.value) return 'warn'
  return 'idle'
})
const gbStreamingTone = computed(() => {
  const status = effectiveGbStreamingStatus.value
  if (status === 'streaming') return 'good'
  if (status === 'waiting_rtmp' || status === 'waiting_invite' || status === 'negotiating') return 'warn'
  if (status === 'failed') return 'bad'
  return 'idle'
})

const labelMap = {
  managed: '托管进程',
  external: '外部服务',
  stopped: '已停止',
  not_configured: '未配置',
  registered: '已注册',
  registering: '注册中',
  starting: '启动中',
  failed: '失败',
  waiting_invite: '等待平台点播',
  waiting_rtmp: '等待 RTMP 输入',
  negotiating: '协商中',
  streaming: '推流中'
}

const labelOf = (value, fallback = '--') => labelMap[value] || value || fallback

const dependencyText = computed(() => {
  const dependencies = meta.dependencies || rtmpStatus.value?.dependencies
  if (!dependencies) {
    return '依赖检测待刷新'
  }
  const zlm = dependencies.zlm_executable_found ? 'ZLM 已找到' : 'ZLM 未配置'
  const bridge = dependencies.gb_bridge_configured ? 'GB 桥接已配置' : 'GB 桥接未配置'
  const ffmpeg = dependencies.ffmpeg_found ? 'FFmpeg 已找到' : 'FFmpeg 未找到'
  return `${zlm} / ${bridge} / ${ffmpeg}`
})

const bitrateLabel = computed(() => `${Number(gbStatus.value?.bitrate_kbps || rtmpStatus.value?.bitrate_kbps || 0).toFixed(1)} kbps`)
const fpsLabel = computed(() => {
  const fps = gbStatus.value?.fps ?? rtmpStatus.value?.fps
  return Number.isFinite(Number(fps)) ? `${Number(fps).toFixed(1)} fps` : '--'
})
const statusWarningText = computed(() => (
  gbStatus.value?.process_warning
  || (() => {
    const recentError = gbStatus.value?.recent_error || ''
    if (recentError && gbStreamingLocallyConfirmed.value && isAuxiliaryMediaConnectError(recentError)) {
      return `国标视频已检测到有效媒体数据；最近一次辅助 TCP 媒体端口连接失败：${recentError}`
    }
    return recentError
  })()
  || rtmpStatus.value?.last_error
  || ''
))

const maxPreviewWidth = () => {
  if (typeof window === 'undefined') {
    return PREVIEW_DEFAULT_WIDTH
  }

  return Math.min(PREVIEW_MAX_WIDTH, Math.max(PREVIEW_MIN_WIDTH, window.innerWidth - 24))
}

const clampPreviewWidth = (value) => {
  const numeric = Number(value)
  const safeValue = Number.isFinite(numeric) ? numeric : PREVIEW_DEFAULT_WIDTH
  return Math.round(Math.min(Math.max(safeValue, PREVIEW_MIN_WIDTH), maxPreviewWidth()))
}

const savePreviewWidth = () => {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(PREVIEW_SIZE_STORAGE_KEY, String(clampPreviewWidth(previewWidth.value)))
}

const setPreviewWidth = (nextWidth, { persist = true } = {}) => {
  previewWidth.value = clampPreviewWidth(nextWidth)
  if (persist) {
    savePreviewWidth()
  }
  clampPreviewPosition()
}

const resizePreviewBy = (deltaWidth) => {
  setPreviewWidth(previewWidth.value + deltaWidth)
}

const previewDimensions = computed(() => {
  if (previewMinimized.value) {
    return {
      width: 220,
      height: 46
    }
  }

  const width = clampPreviewWidth(previewWidth.value)
  return {
    width,
    height: Math.round(width / PREVIEW_ASPECT_RATIO)
  }
})

const previewStyle = computed(() => ({
  width: previewMinimized.value ? '220px' : `${previewDimensions.value.width}px`,
  transform: `translate3d(${previewPosition.x}px, ${previewPosition.y}px, 0)`
}))

const previewStatusText = computed(() => {
  if (previewError.value) return previewError.value
  if (!hasRtmpStream.value) return '等待 RTMP 视频流'
  if (!previewPlaying.value) return '已暂停'
  if (previewMode.value === 'webrtc') return 'WebRTC 低延迟预览中'
  return previewMode.value === 'fmp4' ? '实时预览中（兼容模式）' : '实时预览中'
})

const destroyWebrtcPlayer = () => {
  if (rtcPeerConnection) {
    rtcPeerConnection.ontrack = null
    rtcPeerConnection.onconnectionstatechange = null
    rtcPeerConnection.oniceconnectionstatechange = null
    rtcPeerConnection.close()
    rtcPeerConnection = null
  }
  if (rtcRemoteStream) {
    rtcRemoteStream.getTracks().forEach((track) => track.stop())
    rtcRemoteStream = null
  }
  if (previewVideo.value?.srcObject) {
    previewVideo.value.srcObject = null
  }
}

const destroyPreviewPlayer = () => {
  if (previewFallbackTimer) {
    window.clearTimeout(previewFallbackTimer)
    previewFallbackTimer = null
  }
  destroyWebrtcPlayer()
  if (previewVideo.value) {
    previewVideo.value.onloadedmetadata = null
    previewVideo.value.oncanplay = null
    previewVideo.value.pause()
    previewVideo.value.removeAttribute('src')
    previewVideo.value.load()
  }
  if (!flvPlayer) {
    return
  }
  try {
    flvPlayer.pause()
    flvPlayer.unload()
    flvPlayer.detachMediaElement()
    flvPlayer.destroy()
  } catch (error) {
    // Player cleanup should never block the panel.
  }
  flvPlayer = null
}

const armPreviewFallback = () => {
  if (typeof window === 'undefined') {
    return
  }
  if (previewFallbackTimer) {
    window.clearTimeout(previewFallbackTimer)
  }
  previewFallbackTimer = window.setTimeout(async () => {
    previewFallbackTimer = null
    if (!previewVisible.value || previewMinimized.value || previewMode.value !== 'flv') {
      return
    }
    const video = previewVideo.value
    const playable = video && video.readyState >= 2 && video.currentTime > 0
    if (!playable) {
      await startNativePreview()
    }
  }, 4000)
}

const startNativePreview = async () => {
  destroyPreviewPlayer()
  await nextTick()
  if (!previewVideo.value || !previewVisible.value || previewMinimized.value) {
    return
  }
  previewMode.value = 'fmp4'
  previewError.value = ''
  previewVideo.value.muted = true
  previewVideo.value.defaultMuted = true
  previewVideo.value.volume = 0
  previewVideo.value.src = fmp4Url.value
  previewVideo.value.onloadedmetadata = playPreviewVideo
  previewVideo.value.oncanplay = playPreviewVideo
  previewVideo.value.load()
  await playPreviewVideo()
}

const loadFlvjs = async () => {
  if (!flvjsModule) {
    const module = await import('flv.js')
    flvjsModule = module.default || module
  }
  return flvjsModule
}

const playPreviewVideo = async () => {
  if (!previewVideo.value || !previewPlaying.value) {
    return
  }
  previewVideo.value.muted = true
  previewVideo.value.defaultMuted = true
  previewVideo.value.volume = 0
  await previewVideo.value.play().catch(() => {
    previewError.value = '点击继续播放以启动预览'
    previewPlaying.value = false
  })
}

const waitForIceGatheringComplete = (peerConnection, timeoutMs = 1800) =>
  new Promise((resolve) => {
    if (peerConnection.iceGatheringState === 'complete') {
      resolve()
      return
    }
    let timer = null
    const finish = () => {
      if (timer) {
        window.clearTimeout(timer)
      }
      peerConnection.removeEventListener('icegatheringstatechange', handleStateChange)
      resolve()
    }
    const handleStateChange = () => {
      if (peerConnection.iceGatheringState === 'complete') {
        finish()
      }
    }
    peerConnection.addEventListener('icegatheringstatechange', handleStateChange)
    timer = window.setTimeout(finish, timeoutMs)
  })

const switchToFlvPreview = async (reason = '') => {
  if (!previewVisible.value || previewMinimized.value || previewMode.value !== 'webrtc') {
    return
  }
  if (reason) {
    logger.warn('WebRTC preview failed, switching to HTTP-FLV', reason)
  }
  await startFlvPreview()
}

const armWebrtcFallback = () => {
  if (typeof window === 'undefined') {
    return
  }
  if (previewFallbackTimer) {
    window.clearTimeout(previewFallbackTimer)
  }
  previewFallbackTimer = window.setTimeout(async () => {
    previewFallbackTimer = null
    if (!previewVisible.value || previewMinimized.value || previewMode.value !== 'webrtc') {
      return
    }
    const video = previewVideo.value
    const playable = video && video.srcObject && video.readyState >= 2
    if (!playable) {
      await switchToFlvPreview('no remote video track after timeout')
    }
  }, 5000)
}

const startWebrtcPreview = async () => {
  if (typeof RTCPeerConnection === 'undefined') {
    await startFlvPreview()
    return
  }
  if (!previewVisible.value || previewMinimized.value) {
    return
  }
  await nextTick()
  destroyPreviewPlayer()
  previewMode.value = 'webrtc'
  previewError.value = ''

  const video = previewVideo.value
  if (!video) {
    return
  }

  const peerConnection = new RTCPeerConnection({ iceServers: [] })
  rtcPeerConnection = peerConnection
  peerConnection.addTransceiver('video', { direction: 'recvonly' })

  peerConnection.ontrack = async (event) => {
    if (peerConnection !== rtcPeerConnection || event.track.kind !== 'video') {
      return
    }
    rtcRemoteStream = event.streams?.[0] || new MediaStream([event.track])
    video.srcObject = rtcRemoteStream
    video.muted = true
    video.defaultMuted = true
    video.volume = 0
    await playPreviewVideo()
  }

  peerConnection.onconnectionstatechange = () => {
    if (peerConnection !== rtcPeerConnection) {
      return
    }
    if (['failed', 'closed'].includes(peerConnection.connectionState)) {
      void switchToFlvPreview(peerConnection.connectionState)
    }
  }
  peerConnection.oniceconnectionstatechange = () => {
    if (peerConnection !== rtcPeerConnection) {
      return
    }
    if (['failed', 'closed'].includes(peerConnection.iceConnectionState)) {
      void switchToFlvPreview(`ice ${peerConnection.iceConnectionState}`)
    }
  }

  try {
    const offer = await peerConnection.createOffer()
    await peerConnection.setLocalDescription(offer)
    await waitForIceGatheringComplete(peerConnection)
    const localDescription = peerConnection.localDescription || offer
    const response = await fetch(webrtcPlayUrl.value, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: localDescription.sdp || offer.sdp
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const payload = await response.json()
    if (!payload || payload.code !== 0 || !payload.sdp) {
      throw new Error(payload?.msg || payload?.data || 'ZLM WebRTC answer invalid')
    }
    if (peerConnection !== rtcPeerConnection) {
      return
    }
    await peerConnection.setRemoteDescription({ type: payload.type || 'answer', sdp: payload.sdp })
    armWebrtcFallback()
  } catch (error) {
    if (peerConnection === rtcPeerConnection) {
      await switchToFlvPreview(error.message || String(error))
    }
  }
}

const startFlvPreview = async () => {
  if (!previewVisible.value || previewMinimized.value) {
    return
  }
  await nextTick()
  destroyPreviewPlayer()
  previewError.value = ''

  if (!previewVideo.value) {
    return
  }
  let flvjs
  try {
    flvjs = await loadFlvjs()
  } catch (error) {
    await startNativePreview()
    return
  }
  if (!flvjs.isSupported()) {
    await startNativePreview()
    return
  }

  try {
    previewMode.value = 'flv'
    previewVideo.value.muted = true
    previewVideo.value.defaultMuted = true
    previewVideo.value.volume = 0
    previewVideo.value.onloadedmetadata = playPreviewVideo
    previewVideo.value.oncanplay = playPreviewVideo

    flvPlayer = flvjs.createPlayer(
      {
        type: 'flv',
        isLive: true,
        hasVideo: true,
        hasAudio: false,
        cors: true,
        withCredentials: false,
        url: httpFlvUrl.value
      },
      {
        enableWorker: false,
        enableStashBuffer: false,
        stashInitialSize: 128 * 1024,
        lazyLoad: false,
        autoCleanupSourceBuffer: true,
        autoCleanupMaxBackwardDuration: 12,
        autoCleanupMinBackwardDuration: 6
      }
    )
    flvPlayer.on(flvjs.Events.MEDIA_INFO, playPreviewVideo)
    flvPlayer.on(flvjs.Events.ERROR, async (type, detail, info) => {
      const suffix = [type, detail, info?.msg || info?.code].filter(Boolean).join(' / ')
      logger.warn('HTTP-FLV preview failed, switching to fMP4', suffix)
      await startNativePreview()
    })
    flvPlayer.attachMediaElement(previewVideo.value)
    flvPlayer.load()
    armPreviewFallback()
    if (previewPlaying.value) {
      await playPreviewVideo()
    }
  } catch (error) {
    previewError.value = `预览启动失败：${error.message || error}`
  }
}

const initPreviewPlayer = async () => {
  await startWebrtcPreview()
}

const clampPreviewPosition = () => {
  if (typeof window === 'undefined') {
    return
  }
  const { width, height } = previewDimensions.value
  previewPosition.x = Math.min(Math.max(12, previewPosition.x), Math.max(12, window.innerWidth - width - 12))
  previewPosition.y = Math.min(Math.max(12, previewPosition.y), Math.max(12, window.innerHeight - height - 12))
}

const openPreview = async () => {
  if (typeof window !== 'undefined' && !previewVisible.value) {
    previewPosition.x = Math.max(16, window.innerWidth - previewDimensions.value.width - 32)
    previewPosition.y = 88
  }
  previewVisible.value = true
  previewMinimized.value = false
  previewPlaying.value = true
  clampPreviewPosition()
  await initPreviewPlayer()
}

const closePreview = () => {
  previewVisible.value = false
  previewMinimized.value = false
  previewError.value = ''
  destroyPreviewPlayer()
}

const togglePreviewMinimize = async () => {
  previewMinimized.value = !previewMinimized.value
  clampPreviewPosition()
  if (previewMinimized.value) {
    destroyPreviewPlayer()
  } else {
    await initPreviewPlayer()
  }
}

const togglePreviewPlayback = async () => {
  previewPlaying.value = !previewPlaying.value
  if (!previewVideo.value) {
    return
  }
  if (previewPlaying.value) {
    previewError.value = ''
    if (previewMode.value === 'webrtc' && rtcPeerConnection) {
      await playPreviewVideo()
      return
    }
    if (previewMode.value === 'fmp4' && previewVideo.value.src) {
      await playPreviewVideo()
      return
    }
    if (!flvPlayer) {
      await initPreviewPlayer()
      return
    }
    await previewVideo.value.play().catch(() => {
      previewError.value = '播放启动失败'
      previewPlaying.value = false
    })
  } else {
    previewVideo.value.pause()
  }
}

const startPreviewDrag = (event) => {
  if (event.button !== undefined && event.button !== 0) {
    return
  }
  previewDrag = {
    startX: event.clientX,
    startY: event.clientY,
    originX: previewPosition.x,
    originY: previewPosition.y
  }
  window.addEventListener('pointermove', handlePreviewDrag)
  window.addEventListener('pointerup', stopPreviewDrag, { once: true })
}

const handlePreviewDrag = (event) => {
  if (!previewDrag) {
    return
  }
  previewPosition.x = previewDrag.originX + event.clientX - previewDrag.startX
  previewPosition.y = previewDrag.originY + event.clientY - previewDrag.startY
  clampPreviewPosition()
}

const stopPreviewDrag = () => {
  previewDrag = null
  window.removeEventListener('pointermove', handlePreviewDrag)
}

const startPreviewResize = (event) => {
  if (previewMinimized.value || (event.button !== undefined && event.button !== 0)) {
    return
  }

  event.preventDefault()
  event.stopPropagation()
  previewResize = {
    startX: event.clientX,
    startY: event.clientY,
    originWidth: previewWidth.value
  }
  window.addEventListener('pointermove', handlePreviewResize)
  window.addEventListener('pointerup', stopPreviewResize, { once: true })
}

const handlePreviewResize = (event) => {
  if (!previewResize) {
    return
  }

  const deltaX = event.clientX - previewResize.startX
  const deltaY = (event.clientY - previewResize.startY) * PREVIEW_ASPECT_RATIO
  const delta = Math.abs(deltaX) >= Math.abs(deltaY) ? deltaX : deltaY
  setPreviewWidth(previewResize.originWidth + delta, { persist: false })
}

const stopPreviewResize = () => {
  if (!previewResize) {
    return
  }

  previewResize = null
  savePreviewWidth()
  window.removeEventListener('pointermove', handlePreviewResize)
}

watch(
  logs,
  async () => {
    await nextTick()
    if (logWindow.value) {
      logWindow.value.scrollTop = logWindow.value.scrollHeight
    }
  },
  { deep: true }
)

watch(
  () => [previewVisible.value, previewMinimized.value, webrtcPlayUrl.value, httpFlvUrl.value, fmp4Url.value],
  async () => {
    if (previewVisible.value && !previewMinimized.value) {
      await initPreviewPlayer()
    } else if (!previewVisible.value || previewMinimized.value) {
      destroyPreviewPlayer()
    }
  }
)

onMounted(async () => {
  await Promise.all([refreshConfig(), refreshStatus()])
  refreshTimer = window.setInterval(refreshStatus, 3000)
  window.addEventListener('resize', clampPreviewPosition)
})

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
  window.removeEventListener('resize', clampPreviewPosition)
  window.removeEventListener('pointermove', handlePreviewDrag)
  window.removeEventListener('pointermove', handlePreviewResize)
  destroyPreviewPlayer()
})
</script>

<template>
  <section class="live-forward glass-panel" :class="{ 'live-forward--open': expanded }">
    <header class="live-forward__header">
      <button type="button" class="live-forward__toggle" @click="toggleExpanded">
        <span class="toggle-title">直播转发</span>
        <span class="toggle-subtitle">{{ labelOf(rtmpStatus?.service_source) }} · {{ hasRtmpStream ? '已收流' : '未收流' }}</span>
      </button>
      <div class="live-forward__header-actions">
        <button
          type="button"
          class="live-forward__restart"
          :disabled="liveActionBusy"
          title="按顺序重启 RTMP 与 GB28181 转发服务"
          @click.stop="restartLiveServices"
        >
          {{ loading.restart ? '重启中' : '重启服务' }}
        </button>
        <span class="state-dot" :class="`state-dot--${rtmpTone}`"></span>
        <button
          v-if="expanded"
          type="button"
          class="live-forward__close"
          aria-label="关闭直播转发面板"
          title="关闭"
          @click.stop="closePanel"
        >
          &times;
        </button>
      </div>
    </header>

    <div v-if="expanded" class="live-forward__body">
      <div class="push-address">
        <div>
          <span>本机局域网 IP</span>
          <strong>{{ lanIp }}</strong>
        </div>
        <div>
          <span>RTMP 推流地址</span>
          <strong>{{ rtmpPushUrl }}</strong>
        </div>
        <button type="button" class="icon-action" title="复制 RTMP 地址" @click="copyPushUrl">复制</button>
      </div>

      <div class="status-grid">
        <div class="status-cell" :class="`status-cell--${rtmpTone}`">
          <span>RTMP 服务</span>
          <strong>{{ rtmpRunning ? labelOf(rtmpStatus?.service_source) : '已停止' }}</strong>
        </div>
        <div class="status-cell" :class="`status-cell--${streamTone}`">
          <span>无人机视频流</span>
          <strong>{{ hasRtmpStream ? '在线' : '未检测到' }}</strong>
        </div>
        <div class="status-cell" :class="`status-cell--${gbRegistrationTone}`">
          <span>SIP 注册</span>
          <strong>{{ labelOf(gbStatus?.registration_status) }}</strong>
        </div>
        <div class="status-cell" :class="`status-cell--${gbStreamingTone}`">
          <span>国标推流</span>
          <strong>{{ labelOf(effectiveGbStreamingStatus) }}</strong>
        </div>
      </div>

      <div class="metric-row">
        <span>码率 {{ bitrateLabel }}</span>
        <span>帧率 {{ fpsLabel }}</span>
        <span>客户端 {{ rtmpStatus?.online_clients ?? 0 }}</span>
      </div>

      <p v-if="errorMessage" class="message message--error">{{ errorMessage }}</p>
      <p v-else-if="statusWarningText" class="message message--warning">{{ statusWarningText }}</p>
      <p v-else-if="infoMessage" class="message message--info">{{ infoMessage }}</p>
      <p class="dependency-line">{{ dependencyText }}</p>

      <div class="form-sections">
        <section class="form-section">
          <header>
            <strong>RTMP 接收</strong>
            <div class="button-row">
              <button type="button" class="control-btn control-btn--primary" :disabled="liveActionBusy" @click="startRtmp">
                启动 RTMP
              </button>
              <button type="button" class="control-btn" :disabled="liveActionBusy" @click="stopRtmp">
                停止 RTMP
              </button>
            </div>
          </header>

          <div class="field-grid field-grid--compact">
            <label class="field">
              <span>RTMP 端口</span>
              <input v-model.number="draft.rtmp.port" type="number" min="1" max="65535" />
            </label>
            <label class="field">
              <span>App</span>
              <input v-model.trim="draft.rtmp.app" type="text" />
            </label>
            <label class="field">
              <span>Stream</span>
              <input v-model.trim="draft.rtmp.stream" type="text" />
            </label>
            <label class="field">
              <span>ZLM HTTP 端口</span>
              <input v-model.number="draft.rtmp.zlm_http_port" type="number" min="1" max="65535" />
            </label>
          </div>

          <label class="field">
            <span>ZLMediaKit MediaServer.exe</span>
            <input v-model.trim="draft.rtmp.zlm_executable_path" type="text" placeholder="tools\\zlmediakit\\MediaServer.exe" />
          </label>
          <label class="field">
            <span>ZLM Secret</span>
            <input v-model.trim="draft.rtmp.zlm_secret" type="text" />
          </label>
        </section>

        <section class="form-section">
          <header>
            <strong>GB28181 转发</strong>
            <div class="button-row">
              <button type="button" class="control-btn control-btn--primary" :disabled="liveActionBusy" @click="startGb">
                开始转发
              </button>
              <button type="button" class="control-btn" :disabled="liveActionBusy" @click="stopGb">
                停止转发
              </button>
            </div>
          </header>

          <div class="field-grid">
            <label class="field">
              <span>SIP 服务器 IP</span>
              <input v-model.trim="draft.gb28181.sip_server_ip" type="text" placeholder="192.168.1.10" />
            </label>
            <label class="field">
              <span>SIP 服务器端口</span>
              <input v-model.number="draft.gb28181.sip_server_port" type="number" min="1" max="65535" />
            </label>
            <label class="field">
              <span>SIP 域</span>
              <input v-model.trim="draft.gb28181.sip_domain" type="text" placeholder="3402000000" />
            </label>
            <label class="field">
              <span>ServerID</span>
              <input v-model.trim="draft.gb28181.sip_server_id" type="text" placeholder="留空使用 SIP 域" />
            </label>
            <label class="field">
              <span>DeviceID</span>
              <input v-model.trim="draft.gb28181.device_id" type="text" />
            </label>
            <label class="field">
              <span>ChannelID</span>
              <input v-model.trim="draft.gb28181.channel_id" type="text" />
            </label>
            <label class="field">
              <span>本地 SIP 端口</span>
              <input v-model.number="draft.gb28181.local_sip_port" type="number" min="0" max="65535" />
            </label>
            <label class="field">
              <span>传输方式</span>
              <select v-model="draft.gb28181.transport">
                <option value="UDP">UDP</option>
                <option value="TCP">TCP</option>
              </select>
            </label>
            <label class="field">
              <span>RTP 起始端口</span>
              <input v-model.number="draft.gb28181.local_rtp_port_start" type="number" min="1" max="65535" />
            </label>
            <label class="field">
              <span>RTP 结束端口</span>
              <input v-model.number="draft.gb28181.local_rtp_port_end" type="number" min="1" max="65535" />
            </label>
            <label class="field">
              <span>心跳间隔</span>
              <input v-model.number="draft.gb28181.heartbeat_interval" type="number" min="5" max="3600" />
            </label>
            <label class="field">
              <span>密码</span>
              <input v-model="draft.gb28181.password" type="password" />
            </label>
          </div>

          <div class="ssrc-row">
            <label class="field">
              <span>SSRC</span>
              <input v-model.trim="draft.gb28181.ssrc" type="text" />
            </label>
            <button type="button" class="control-btn" @click="generateSsrc">生成</button>
            <label class="check-row">
              <input v-model="draft.gb28181.auto_reconnect" type="checkbox" />
              <span>自动重连</span>
            </label>
          </div>

          <label class="field">
            <span>RTMP 输入地址</span>
            <input v-model.trim="draft.gb28181.rtmp_input_url" type="text" placeholder="rtmp://127.0.0.1/live/drone" />
          </label>
          <label class="field">
            <span>GB28181 桥接程序</span>
            <input v-model.trim="draft.gb28181.bridge_executable_path" type="text" placeholder="tools\\gb28181-bridge\\gb28181-bridge.exe" />
          </label>
          <label class="field">
            <span>桥接命令模板</span>
            <textarea
              v-model.trim="draft.gb28181.bridge_command_template"
              rows="2"
              placeholder="bridge.exe --config {config_path}"
            ></textarea>
          </label>
        </section>
      </div>

      <footer class="panel-actions">
        <button type="button" class="control-btn" :title="httpFlvUrl" @click="openPreview">
          打开预览
        </button>
        <button type="button" class="control-btn" :disabled="loading.config || loading.refresh" @click="refreshStatus">
          刷新状态
        </button>
        <button type="button" class="control-btn control-btn--primary" :disabled="loading.save" @click="saveConfig">
          保存配置
        </button>
      </footer>

      <section class="log-panel">
        <header>
          <strong>运行日志</strong>
          <span>{{ logs.length }} 行</span>
        </header>
        <div ref="logWindow" class="log-window">
          <p v-if="!logs.length" class="log-empty">暂无日志</p>
          <p v-for="line in logs" :key="`${line.timestamp}-${line.source}-${line.message}`" :class="`log-line log-line--${line.level}`">
            <span>{{ line.time }}</span>
            <b>{{ line.source }}</b>
            <em>{{ line.message }}</em>
          </p>
        </div>
      </section>
    </div>
  </section>

  <Teleport to="body">
    <section
      v-if="previewVisible"
      class="live-preview"
      :class="{ 'live-preview--minimized': previewMinimized }"
      :style="previewStyle"
    >
      <header class="live-preview__header" @pointerdown="startPreviewDrag">
        <div class="live-preview__title">
          <strong>无人机视频预览</strong>
          <span>{{ previewStatusText }}</span>
        </div>
        <div class="live-preview__actions" @pointerdown.stop>
          <button v-if="!previewMinimized && previewMode === 'webrtc'" type="button" @click="startFlvPreview">
            HTTP-FLV
          </button>
          <button v-if="!previewMinimized && previewMode === 'flv'" type="button" @click="startNativePreview">
            fMP4
          </button>
          <button
            v-if="!previewMinimized"
            type="button"
            class="live-preview__size-btn"
            title="缩小预览"
            aria-label="缩小预览"
            @click="resizePreviewBy(-PREVIEW_WIDTH_STEP)"
          >
            -
          </button>
          <button
            v-if="!previewMinimized"
            type="button"
            class="live-preview__size-btn"
            title="放大预览"
            aria-label="放大预览"
            @click="resizePreviewBy(PREVIEW_WIDTH_STEP)"
          >
            +
          </button>
          <button v-if="!previewMinimized" type="button" @click="togglePreviewPlayback">
            {{ previewPlaying ? '暂停' : '继续' }}
          </button>
          <button type="button" :aria-label="previewMinimized ? '还原预览' : '最小化预览'" @click="togglePreviewMinimize">
            {{ previewMinimized ? '还原' : '最小化' }}
          </button>
          <button type="button" aria-label="关闭预览" @click="closePreview">&times;</button>
        </div>
      </header>

      <div v-if="!previewMinimized" class="live-preview__stage">
        <video ref="previewVideo" muted playsinline></video>
        <div v-if="previewError || !hasRtmpStream" class="live-preview__overlay">
          {{ previewStatusText }}
        </div>
      </div>
      <button
        v-if="!previewMinimized"
        type="button"
        class="live-preview__resize-handle"
        title="拖动调整预览大小"
        aria-label="拖动调整预览大小"
        @pointerdown="startPreviewResize"
      ></button>
    </section>
  </Teleport>
</template>

<style scoped>
.live-forward {
  --live-forward-open-height: min(560px, calc(100vh - 360px));
  width: 336px;
  max-height: calc(100vh - 250px);
  overflow: hidden;
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.9);
  border-color: rgba(56, 189, 248, 0.18);
}

.live-forward--open {
  width: min(620px, calc(100vw - 2rem));
  max-height: var(--live-forward-open-height);
}

.live-forward__header {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.65rem 0.8rem;
}

.live-forward__toggle {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.12rem;
  border: 0;
  background: transparent;
  color: #f8fafc;
  cursor: pointer;
}

.live-forward__header-actions {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
}

.live-forward__restart {
  min-height: 32px;
  padding: 0 0.68rem;
  border-radius: 999px;
  border: 1px solid rgba(56, 189, 248, 0.26);
  background: rgba(14, 165, 233, 0.16);
  color: #e0f2fe;
  font-size: 0.7rem;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.live-forward__restart:hover:not(:disabled) {
  border-color: rgba(56, 189, 248, 0.44);
  background: rgba(14, 165, 233, 0.24);
}

.live-forward__restart:disabled {
  cursor: wait;
  opacity: 0.62;
}

.toggle-title {
  font-size: 0.86rem;
  font-weight: 700;
}

.toggle-subtitle {
  max-width: 260px;
  color: #94a3b8;
  font-size: 0.7rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.state-dot {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
  border-radius: 999px;
  background: #64748b;
}

.state-dot--good {
  background: #10b981;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.62);
}

.state-dot--warn {
  background: #f59e0b;
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.42);
}

.live-forward__close {
  width: 32px;
  height: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(30, 41, 59, 0.84);
  color: #f8fafc;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}

.live-forward__close:hover {
  border-color: rgba(56, 189, 248, 0.32);
  background: rgba(51, 65, 85, 0.88);
}

.live-forward__body {
  max-height: calc(var(--live-forward-open-height) - 48px);
  padding: 0 0.85rem 0.9rem;
  overflow: auto;
}

.push-address {
  display: grid;
  grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.35fr) auto;
  gap: 0.65rem;
  align-items: stretch;
  padding: 0.75rem;
  border-radius: 14px;
  background: rgba(30, 41, 59, 0.58);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.push-address div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.22rem;
}

.push-address span,
.status-cell span,
.field span,
.metric-row,
.dependency-line,
.log-panel header span {
  color: #94a3b8;
  font-size: 0.72rem;
}

.push-address strong {
  color: #f8fafc;
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.55rem;
  margin-top: 0.75rem;
}

.status-cell {
  min-height: 58px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.18rem;
  padding: 0.62rem;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.48);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.status-cell strong {
  color: #e2e8f0;
  font-size: 0.82rem;
}

.status-cell--good {
  border-color: rgba(16, 185, 129, 0.24);
  background: rgba(16, 185, 129, 0.1);
}

.status-cell--warn {
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(245, 158, 11, 0.1);
}

.status-cell--bad {
  border-color: rgba(248, 113, 113, 0.3);
  background: rgba(239, 68, 68, 0.1);
}

.metric-row,
.dependency-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 0.7rem 0 0;
}

.message {
  margin: 0.7rem 0 0;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  font-size: 0.74rem;
}

.message--error {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.22);
}

.message--info {
  color: #d1fae5;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.22);
}

.message--warning {
  color: #fde68a;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.24);
}

.form-sections {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  margin-top: 0.85rem;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  padding: 0.78rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.form-section > header,
.log-panel header,
.panel-actions,
.button-row,
.ssrc-row,
.check-row {
  display: flex;
  align-items: center;
}

.form-section > header,
.log-panel header,
.panel-actions {
  justify-content: space-between;
  gap: 0.8rem;
}

.form-section strong,
.log-panel strong {
  color: #f8fafc;
  font-size: 0.86rem;
}

.button-row {
  gap: 0.45rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.control-btn,
.icon-action {
  min-height: 34px;
  padding: 0 0.75rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(30, 41, 59, 0.84);
  color: #e2e8f0;
  font-size: 0.73rem;
  font-weight: 650;
  cursor: pointer;
}

.control-btn:disabled {
  cursor: wait;
  opacity: 0.62;
}

.control-btn--primary {
  border-color: rgba(56, 189, 248, 0.26);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.86), rgba(37, 99, 235, 0.82));
  color: #f8fafc;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.62rem;
}

.field-grid--compact {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.field {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
}

.field input,
.field select,
.field textarea {
  width: 100%;
  min-height: 36px;
  padding: 0 0.68rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.68);
  color: #f8fafc;
  font-size: 0.75rem;
  outline: none;
}

.field textarea {
  min-height: 58px;
  padding-top: 0.55rem;
  resize: vertical;
}

.field input:focus,
.field select:focus,
.field textarea:focus {
  border-color: rgba(56, 189, 248, 0.35);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.12);
}

.ssrc-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 0.6rem;
  align-items: end;
}

.check-row {
  gap: 0.45rem;
  color: #cbd5e1;
  font-size: 0.74rem;
  white-space: nowrap;
}

.check-row input {
  width: 15px;
  height: 15px;
  accent-color: #38bdf8;
}

.panel-actions {
  margin-top: 0.8rem;
}

.log-panel {
  margin-top: 0.8rem;
}

.log-window {
  height: 180px;
  margin-top: 0.5rem;
  padding: 0.55rem;
  overflow: auto;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.68);
  border: 1px solid rgba(148, 163, 184, 0.12);
  font-family: Consolas, 'Courier New', monospace;
}

.log-empty,
.log-line {
  margin: 0;
  font-size: 0.68rem;
  line-height: 1.55;
}

.log-empty {
  color: #64748b;
}

.log-line {
  display: grid;
  grid-template-columns: 118px 68px minmax(0, 1fr);
  gap: 0.45rem;
  color: #cbd5e1;
}

.log-line span {
  color: #64748b;
}

.log-line b {
  color: #7dd3fc;
  font-weight: 700;
}

.log-line em {
  min-width: 0;
  font-style: normal;
  overflow-wrap: anywhere;
}

.log-line--ERROR em {
  color: #fecaca;
}

.log-line--WARNING em {
  color: #fde68a;
}

.live-preview {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 10020;
  width: min(450px, calc(100vw - 24px));
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(56, 189, 248, 0.28);
  background: #020617;
  box-shadow: 0 22px 56px rgba(2, 6, 23, 0.42);
}

.live-preview--minimized {
  width: 220px;
  height: 46px;
  aspect-ratio: auto;
}

.live-preview__header {
  position: absolute;
  inset: 0 0 auto;
  z-index: 2;
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.42rem 0.48rem 0.42rem 0.72rem;
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.88), rgba(2, 6, 23, 0.24));
  cursor: grab;
  user-select: none;
}

.live-preview--minimized .live-preview__header {
  position: static;
  height: 100%;
  background: rgba(15, 23, 42, 0.94);
}

.live-preview__header:active {
  cursor: grabbing;
}

.live-preview__title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.08rem;
}

.live-preview__title strong {
  color: #f8fafc;
  font-size: 0.78rem;
}

.live-preview__title span {
  max-width: 180px;
  color: #93c5fd;
  font-size: 0.66rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.live-preview__actions {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
}

.live-preview__actions button {
  min-height: 28px;
  padding: 0 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.78);
  color: #e2e8f0;
  font-size: 0.68rem;
  cursor: pointer;
}

.live-preview__actions .live-preview__size-btn {
  width: 28px;
  padding: 0;
  font-size: 0.82rem;
}

.live-preview__actions button:hover {
  border-color: rgba(56, 189, 248, 0.36);
  background: rgba(30, 41, 59, 0.9);
}

.live-preview__stage {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #020617;
}

.live-preview__stage video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #020617;
}

.live-preview__overlay {
  position: absolute;
  left: 50%;
  bottom: 0.8rem;
  max-width: calc(100% - 1.5rem);
  transform: translateX(-50%);
  padding: 0.38rem 0.66rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: #e2e8f0;
  font-size: 0.7rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.live-preview__resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  z-index: 4;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background:
    linear-gradient(135deg, transparent 0 46%, rgba(125, 211, 252, 0.76) 48% 53%, transparent 55%),
    linear-gradient(135deg, transparent 0 62%, rgba(125, 211, 252, 0.52) 64% 68%, transparent 70%);
  cursor: nwse-resize;
}

.live-preview__resize-handle:hover {
  background:
    linear-gradient(135deg, transparent 0 46%, rgba(224, 242, 254, 0.96) 48% 53%, transparent 55%),
    linear-gradient(135deg, transparent 0 62%, rgba(224, 242, 254, 0.74) 64% 68%, transparent 70%);
}

@media (max-width: 900px) {
  .live-forward,
  .live-forward--open {
    --live-forward-open-height: calc(100vh - 1.5rem);
    width: calc(100vw - 1.5rem);
    max-height: calc(100vh - 1.5rem);
  }

  .push-address,
  .status-grid,
  .field-grid,
  .field-grid--compact,
  .ssrc-row {
    grid-template-columns: 1fr;
  }

  .log-line {
    grid-template-columns: 1fr;
    gap: 0.1rem;
  }
}
</style>
