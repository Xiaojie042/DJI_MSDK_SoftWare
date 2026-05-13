import config from '@/utils/config'

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 }
const LEVEL_LABELS = { debug: 'DEBUG', info: 'INFO', warn: 'WARN', error: 'ERROR' }

let logBuffer = []
let pendingEntries = []
let backendSendTimer = null
let apiBaseUrl = ''
const BACKEND_SEND_INTERVAL_MS = 5000
const BACKEND_SEND_BATCH_SIZE = 50

function formatNow() {
  return new Date().toISOString().replace('T', ' ').slice(0, 23)
}

function pushLog(level, message, data = null) {
  const entry = {
    time: formatNow(),
    level: LEVEL_LABELS[level],
    message: String(message)
  }
  if (data !== null && data !== undefined) {
    try {
      entry.data = typeof data === 'object' ? JSON.stringify(data) : String(data)
    } catch {
      entry.data = '[unserializable]'
    }
  }

  logBuffer.push(entry)
  if (logBuffer.length > config.LOG_BUFFER_LIMIT) {
    logBuffer = logBuffer.slice(-config.LOG_BUFFER_LIMIT)
  }

  pendingEntries.push(entry)

  if (config.DEBUG_MODE) {
    const consoleMethod = level === 'debug' ? 'log' : level
    const consoleArgs = [`[${LEVEL_LABELS[level]}] ${entry.time} ${message}`]
    if (data !== null && data !== undefined) {
      consoleArgs.push(data)
    }
    console[consoleMethod](...consoleArgs)
  }

  scheduleBackendSend()
}

async function sendLogsToBackend() {
  if (typeof window === 'undefined' || pendingEntries.length === 0 || !apiBaseUrl) {
    return
  }

  const batch = pendingEntries.splice(0, BACKEND_SEND_BATCH_SIZE)

  try {
    await fetch(`${apiBaseUrl}/api/logs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entries: batch })
    })
  } catch {
    // Silently fail - logs are still available in buffer
  }
}

function scheduleBackendSend() {
  if (typeof window === 'undefined' || backendSendTimer) return
  backendSendTimer = window.setTimeout(() => {
    sendLogsToBackend().finally(() => {
      backendSendTimer = null
      if (pendingEntries.length > 0) {
        scheduleBackendSend()
      }
    })
  }, BACKEND_SEND_INTERVAL_MS)
}

const logger = {
  debug(message, data) { pushLog('debug', message, data) },
  info(message, data) { pushLog('info', message, data) },
  warn(message, data) { pushLog('warn', message, data) },
  error(message, data) { pushLog('error', message, data) },

  setApiBaseUrl(url) {
    apiBaseUrl = url
  },

  getLogs() {
    return [...logBuffer]
  },

  exportLogs(format = 'txt') {
    if (format === 'json') {
      return JSON.stringify(logBuffer, null, 2)
    }
    return logBuffer.map((entry) => {
      let line = `[${entry.level}] ${entry.time} ${entry.message}`
      if (entry.data) {
        line += ` | ${entry.data}`
      }
      return line
    }).join('\n')
  },

  downloadLogs(format = 'txt') {
    if (typeof window === 'undefined') return
    const content = this.exportLogs(format)
    const ext = format === 'json' ? 'json' : 'log'
    const filename = `${config.LOG_EXPORT_FILENAME_PREFIX}-${Date.now()}.${ext}`
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
    logger.info('Logs exported', { filename, entries: logBuffer.length })
  },

  clearLogs() {
    logBuffer = []
    pendingEntries = []
    logger.info('Log buffer cleared')
  },

  flushToBackend() {
    return sendLogsToBackend()
  },

  bufferSize() {
    return logBuffer.length
  },

  pendingCount() {
    return pendingEntries.length
  }
}

export default logger
