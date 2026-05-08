const XLSX_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

const WEATHER_FIELD_DEFINITIONS = [
  { key: 'relative_wind_direction_deg', label: '相对风向(度)' },
  { key: 'relative_wind_speed_ms', label: '相对风速(m/s)' },
  { key: 'true_wind_direction_deg', label: '真风向(度)' },
  { key: 'true_wind_speed_ms', label: '真风速(m/s)' },
  { key: 'temperature_c', label: '温度(°C)' },
  { key: 'humidity_percent', label: '湿度(%)' },
  { key: 'pressure_hpa', label: '气压(hPa)' },
  { key: 'lrc_valid', label: '校验通过' }
]

const VISIBILITY_FIELD_DEFINITIONS = [
  { key: 'visibility_10s_m', label: '10秒能见度(m)' },
  { key: 'visibility_1min_m', label: '1分钟能见度(m)' },
  { key: 'visibility_10min_m', label: '10分钟能见度(m)' },
  { key: 'power_voltage_v', label: '供电电压(V)' }
]

const BASE_COLUMNS = [
  { key: 'flight_id', label: '架次ID', width: 140 },
  { key: 'file_name', label: '文件名', width: 180 },
  { key: 'drone_id', label: '无人机ID', width: 110 },
  { key: 'takeoff_time_text', label: '起飞时间', width: 130 },
  { key: 'landing_time_text', label: '降落时间', width: 130 },
  { key: 'summary_point_count', label: '摘要-点位数', width: 80 },
  { key: 'summary_total_distance_m', label: '摘要-总里程(m)', width: 95 },
  { key: 'summary_max_altitude_m', label: '摘要-最大高度(m)', width: 95 },
  { key: 'summary_max_speed_ms', label: '摘要-最大速度(m/s)', width: 105 },
  { key: 'attached_weather_devices', label: '摘要-设备列表', width: 180 },
  { key: 'telemetry_timestamp', label: '遥测时间戳(s)', width: 105 },
  { key: 'telemetry_time_text', label: '遥测时间', width: 130 },
  { key: 'latitude', label: '纬度', width: 85 },
  { key: 'longitude', label: '经度', width: 85 },
  { key: 'altitude_m', label: '高度(m)', width: 80 },
  { key: 'heading_deg', label: '航向(度)', width: 75 },
  { key: 'horizontal_speed_ms', label: '水平速度(m/s)', width: 95 },
  { key: 'vertical_speed_ms', label: '垂直速度(m/s)', width: 95 },
  { key: 'battery_percent', label: '电池(%)', width: 70 },
  { key: 'battery_voltage_v', label: '电压(V)', width: 75 },
  { key: 'battery_temperature_c', label: '电池温度(°C)', width: 95 },
  { key: 'gps_signal', label: 'GPS信号', width: 70 },
  { key: 'flight_mode', label: '飞行模式', width: 90 },
  { key: 'is_flying', label: '是否飞行', width: 65 },
  { key: 'home_distance_m', label: '距家距离(m)', width: 90 },
  { key: 'gimbal_pitch_deg', label: '云台俯仰(度)', width: 90 },
  { key: 'rc_signal', label: '遥控信号', width: 75 },
  { key: 'attitude_pitch_deg', label: '姿态-俯仰(度)', width: 90 },
  { key: 'attitude_roll_deg', label: '姿态-横滚(度)', width: 90 },
  { key: 'attitude_yaw_deg', label: '姿态-偏航(度)', width: 90 }
]

const textEncoder = new TextEncoder()

const escapeXml = (value) =>
  String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')

const parseTimestampToSeconds = (value, fallback = null) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string') {
    const numeric = Number(value)
    if (Number.isFinite(numeric)) {
      return numeric
    }

    const parsed = Date.parse(value)
    if (Number.isFinite(parsed)) {
      return parsed / 1000
    }
  }

  return fallback
}

const toFiniteNumber = (value, fallback = null) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

const toNullableNumber = (value) => {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const toBooleanLabel = (value) => {
  if (value === null || value === undefined || value === '') {
    return ''
  }

  return Boolean(value) ? '是' : '否'
}

const formatDateTime = (timestamp) => {
  const numeric = parseTimestampToSeconds(timestamp, null)
  if (!Number.isFinite(numeric)) {
    return ''
  }

  return new Date(numeric * 1000).toLocaleString('zh-CN', { hour12: false })
}

const formatSummaryDevices = (devices = []) => {
  if (!Array.isArray(devices) || devices.length === 0) {
    return '无'
  }

  return devices
    .map((device) => `${device?.payload_index || '--'}/${device?.device_type || 'unknown'}`)
    .join('; ')
}

const sanitizeFileName = (value, fallback = 'flight-session-export') => {
  const normalized = String(value || fallback)
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
    .trim()

  return normalized || fallback
}

const sanitizeSheetName = (value, fallback = '历史航迹') => {
  const normalized = String(value || fallback)
    .replace(/[\[\]:*?/\\]/g, '_')
    .slice(0, 31)
    .trim()

  return normalized || fallback
}

const sortRecordsByTimestamp = (records = []) =>
  [...records].sort(
    (left, right) =>
      parseTimestampToSeconds(left?.timestamp ?? left?.telemetry?.timestamp, 0) -
      parseTimestampToSeconds(right?.timestamp ?? right?.telemetry?.timestamp, 0)
  )

const buildDeviceKey = (record = {}) => `${record?.payload_index || '--'}::${record?.device_type || 'unknown'}`

const buildDynamicFieldDefinitions = (records = []) => {
  const keys = [...new Set(
    records.flatMap((record) => Object.keys(
      record?.parsed_data && typeof record.parsed_data === 'object' ? record.parsed_data : {}
    ))
  )].sort((left, right) => left.localeCompare(right))

  return keys.map((key) => ({ key, label: key }))
}

const buildDeviceGroups = (detail = {}) => {
  const attachedDevices = Array.isArray(detail.attached_weather_devices) ? detail.attached_weather_devices : []
  const psdkRecords = sortRecordsByTimestamp(Array.isArray(detail.psdk_records) ? detail.psdk_records : [])
  const groupMap = new Map()

  for (const record of psdkRecords) {
    const key = buildDeviceKey(record)
    if (!groupMap.has(key)) {
      groupMap.set(key, {
        key,
        payloadIndex: record?.payload_index || '--',
        deviceType: record?.device_type || 'unknown',
        records: []
      })
    }

    groupMap.get(key).records.push(record)
  }

  const orderedKeys = []
  for (const device of attachedDevices) {
    const key = buildDeviceKey(device)
    if (!orderedKeys.includes(key)) {
      orderedKeys.push(key)
    }
  }

  for (const key of [...groupMap.keys()].sort((left, right) => left.localeCompare(right))) {
    if (!orderedKeys.includes(key)) {
      orderedKeys.push(key)
    }
  }

  return orderedKeys.map((key) => {
    const existingGroup = groupMap.get(key)
    const payloadIndex = existingGroup?.payloadIndex || key.split('::')[0] || '--'
    const deviceType = existingGroup?.deviceType || key.split('::')[1] || 'unknown'
    const records = existingGroup?.records || []

    const fieldDefinitions =
      deviceType === 'weather'
        ? WEATHER_FIELD_DEFINITIONS
        : deviceType === 'visibility'
          ? VISIBILITY_FIELD_DEFINITIONS
          : buildDynamicFieldDefinitions(records)

    return {
      key,
      payloadIndex,
      deviceType,
      records,
      fieldDefinitions
    }
  })
}

const buildDeviceColumns = (deviceGroups = []) =>
  deviceGroups.flatMap((group) => {
    const prefix = `${group.payloadIndex}/${group.deviceType}`
    return [
      { key: `${group.key}__timestamp_text`, label: `${prefix}-记录时间`, width: 130 },
      ...group.fieldDefinitions.map((definition) => ({
        key: `${group.key}__${definition.key}`,
        label: `${prefix}-${definition.label}`,
        width: 110
      }))
    ]
  })

const normalizeTelemetryRecord = (record = {}) => {
  const telemetry = record?.telemetry && typeof record.telemetry === 'object' ? record.telemetry : record
  const position = telemetry?.position || {}
  const velocity = telemetry?.velocity || {}
  const battery = telemetry?.battery || {}
  const rawPayload = record?.raw_payload && typeof record.raw_payload === 'object' ? record.raw_payload : {}
  const rawAttitude = rawPayload?.attitude && typeof rawPayload.attitude === 'object' ? rawPayload.attitude : {}
  const timestamp = parseTimestampToSeconds(record?.timestamp ?? telemetry?.timestamp, null)

  return {
    timestamp,
    telemetryTimestamp: timestamp,
    telemetryTimeText: formatDateTime(timestamp),
    latitude: toFiniteNumber(position.latitude ?? telemetry?.latitude ?? telemetry?.lat, null),
    longitude: toFiniteNumber(position.longitude ?? telemetry?.longitude ?? telemetry?.lng ?? telemetry?.lon, null),
    altitudeM: toFiniteNumber(position.altitude ?? telemetry?.altitude ?? telemetry?.relative_altitude, null),
    headingDeg: toFiniteNumber(telemetry?.heading ?? telemetry?.aircraft_heading, null),
    horizontalSpeedMs: toFiniteNumber(
      velocity.horizontal ?? velocity.horizontal_speed ?? telemetry?.horizontal_speed ?? telemetry?.horizontalSpeed,
      null
    ),
    verticalSpeedMs: toFiniteNumber(velocity.vertical ?? telemetry?.vertical_speed ?? telemetry?.verticalSpeed, null),
    batteryPercent: toNullableNumber(battery.percent ?? telemetry?.battery_percent ?? telemetry?.batteryPercent),
    batteryVoltageV: toFiniteNumber(battery.voltage ?? telemetry?.battery_voltage ?? telemetry?.batteryVoltage, null),
    batteryTemperatureC: toFiniteNumber(
      battery.temperature ?? telemetry?.battery_temperature ?? telemetry?.batteryTemperature,
      null
    ),
    gpsSignal: toNullableNumber(telemetry?.gps_signal ?? telemetry?.gpsSignal),
    flightMode: telemetry?.flight_mode || telemetry?.flightMode || telemetry?.flight_mode_string || '',
    isFlying: toBooleanLabel(telemetry?.is_flying ?? telemetry?.isFlying),
    homeDistanceM: toFiniteNumber(telemetry?.home_distance ?? telemetry?.homeDistance, null),
    gimbalPitchDeg: toFiniteNumber(telemetry?.gimbal_pitch ?? telemetry?.gimbalPitch, null),
    rcSignal: toNullableNumber(telemetry?.rc_signal ?? telemetry?.rcSignal),
    attitudePitchDeg: toFiniteNumber(rawAttitude?.pitch, null),
    attitudeRollDeg: toFiniteNumber(rawAttitude?.roll, null),
    attitudeYawDeg: toFiniteNumber(rawAttitude?.yaw, null)
  }
}

const resolveDeviceRecordValue = (record, key) => {
  const parsedData = record?.parsed_data && typeof record.parsed_data === 'object' ? record.parsed_data : {}
  const value = parsedData[key]

  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }

  return value ?? ''
}

const resolveRecordForTimestamp = (records = [], timestamp, cursorRef) => {
  if (!Array.isArray(records) || records.length === 0) {
    return null
  }

  const targetSeconds = parseTimestampToSeconds(timestamp, Number.POSITIVE_INFINITY)

  while (
    cursorRef.index + 1 < records.length &&
    parseTimestampToSeconds(records[cursorRef.index + 1]?.timestamp, Number.POSITIVE_INFINITY) <= targetSeconds
  ) {
    cursorRef.index += 1
  }

  if (cursorRef.index >= 0) {
    return records[cursorRef.index]
  }

  return records[0] || null
}

const buildWorksheetRows = (detail = {}) => {
  const summary = detail?.summary && typeof detail.summary === 'object' ? detail.summary : {}
  const telemetryRecords = sortRecordsByTimestamp(Array.isArray(detail.telemetry_records) ? detail.telemetry_records : [])
  const deviceGroups = buildDeviceGroups(detail)
  const deviceCursors = new Map(deviceGroups.map((group) => [group.key, { index: -1 }]))
  const attachedWeatherDevices = formatSummaryDevices(detail.attached_weather_devices)

  const rows = telemetryRecords.map((record) => {
    const telemetry = normalizeTelemetryRecord(record)
    const row = {
      flight_id: detail.flight_id || '',
      file_name: detail.file_name || '',
      drone_id: detail.drone_id || '',
      takeoff_time_text: formatDateTime(detail.takeoff_time),
      landing_time_text: formatDateTime(detail.landing_time),
      summary_point_count: toNullableNumber(summary.point_count),
      summary_total_distance_m: toFiniteNumber(summary.total_distance_m, null),
      summary_max_altitude_m: toFiniteNumber(summary.max_altitude_m, null),
      summary_max_speed_ms: toFiniteNumber(summary.max_speed_ms, null),
      attached_weather_devices: attachedWeatherDevices,
      telemetry_timestamp: telemetry.telemetryTimestamp,
      telemetry_time_text: telemetry.telemetryTimeText,
      latitude: telemetry.latitude,
      longitude: telemetry.longitude,
      altitude_m: telemetry.altitudeM,
      heading_deg: telemetry.headingDeg,
      horizontal_speed_ms: telemetry.horizontalSpeedMs,
      vertical_speed_ms: telemetry.verticalSpeedMs,
      battery_percent: telemetry.batteryPercent,
      battery_voltage_v: telemetry.batteryVoltageV,
      battery_temperature_c: telemetry.batteryTemperatureC,
      gps_signal: telemetry.gpsSignal,
      flight_mode: telemetry.flightMode,
      is_flying: telemetry.isFlying,
      home_distance_m: telemetry.homeDistanceM,
      gimbal_pitch_deg: telemetry.gimbalPitchDeg,
      rc_signal: telemetry.rcSignal,
      attitude_pitch_deg: telemetry.attitudePitchDeg,
      attitude_roll_deg: telemetry.attitudeRollDeg,
      attitude_yaw_deg: telemetry.attitudeYawDeg
    }

    for (const group of deviceGroups) {
      const resolvedRecord = resolveRecordForTimestamp(group.records, telemetry.timestamp, deviceCursors.get(group.key))
      row[`${group.key}__timestamp_text`] = formatDateTime(resolvedRecord?.timestamp)

      for (const definition of group.fieldDefinitions) {
        row[`${group.key}__${definition.key}`] = resolveDeviceRecordValue(resolvedRecord, definition.key)
      }
    }

    return row
  })

  return {
    rows,
    deviceGroups
  }
}

const toColumnName = (index) => {
  let columnIndex = index + 1
  let name = ''

  while (columnIndex > 0) {
    const remainder = (columnIndex - 1) % 26
    name = String.fromCharCode(65 + remainder) + name
    columnIndex = Math.floor((columnIndex - 1) / 26)
  }

  return name
}

const toXlsxColumnWidth = (pixelWidth = 100) => Math.max(8, Math.round((pixelWidth / 7) * 10) / 10)

const toCellXml = (value, rowIndex, columnIndex, styleIndex = 0) => {
  const cellRef = `${toColumnName(columnIndex)}${rowIndex}`

  if (value === null || value === undefined || value === '') {
    return `<c r="${cellRef}" s="${styleIndex}" t="inlineStr"><is><t></t></is></c>`
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return `<c r="${cellRef}" s="${styleIndex}"><v>${value}</v></c>`
  }

  return `<c r="${cellRef}" s="${styleIndex}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(value)}</t></is></c>`
}

const buildWorksheetXml = (columns, rows) => {
  const rowCount = rows.length + 1
  const columnCount = columns.length
  const lastCellRef = `${toColumnName(Math.max(columnCount - 1, 0))}${Math.max(rowCount, 1)}`
  const columnXml = columns
    .map((column, index) => {
      const columnIndex = index + 1
      return `<col min="${columnIndex}" max="${columnIndex}" width="${toXlsxColumnWidth(column.width)}" customWidth="1"/>`
    })
    .join('')

  const headerRow = `<row r="1">${columns.map((column, index) => toCellXml(column.label, 1, index, 1)).join('')}</row>`
  const bodyRows = rows
    .map((row, rowIndex) => {
      const excelRowIndex = rowIndex + 2
      return `<row r="${excelRowIndex}">${columns.map((column, columnIndex) =>
        toCellXml(row[column.key], excelRowIndex, columnIndex, 0)
      ).join('')}</row>`
    })
    .join('')

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:${lastCellRef}"/>
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
      <selection pane="bottomLeft"/>
    </sheetView>
  </sheetViews>
  <cols>${columnXml}</cols>
  <sheetData>${headerRow}${bodyRows}</sheetData>
  <autoFilter ref="A1:${lastCellRef}"/>
</worksheet>`
}

const buildWorkbookXml = (sheetName) => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="${escapeXml(sheetName)}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>`

const buildWorkbookRelationshipsXml = () => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`

const buildPackageRelationshipsXml = () => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`

const buildContentTypesXml = () => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>`

const buildStylesXml = () => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="10"/><name val="Microsoft YaHei"/></font>
    <font><b/><sz val="10"/><name val="Microsoft YaHei"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE2E8F0"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD4DCE8"/></left>
      <right style="thin"><color rgb="FFD4DCE8"/></right>
      <top style="thin"><color rgb="FFD4DCE8"/></top>
      <bottom style="thin"><color rgb="FFD4DCE8"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1">
      <alignment vertical="center" wrapText="1"/>
    </xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1">
      <alignment horizontal="center" vertical="center" wrapText="1"/>
    </xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`

const buildCorePropertiesXml = () => {
  const createdAt = new Date().toISOString()
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>DJI Drone Monitor</dc:creator>
  <cp:lastModifiedBy>DJI Drone Monitor</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">${createdAt}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">${createdAt}</dcterms:modified>
</cp:coreProperties>`
}

const buildAppPropertiesXml = () => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>DJI Drone Monitor</Application>
</Properties>`

const createCrc32Table = () => {
  const table = new Uint32Array(256)
  for (let index = 0; index < 256; index += 1) {
    let value = index
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1
    }
    table[index] = value >>> 0
  }
  return table
}

const CRC32_TABLE = createCrc32Table()

const calculateCrc32 = (bytes) => {
  let crc = 0xffffffff
  for (let index = 0; index < bytes.length; index += 1) {
    crc = CRC32_TABLE[(crc ^ bytes[index]) & 0xff] ^ (crc >>> 8)
  }
  return (crc ^ 0xffffffff) >>> 0
}

const writeUInt16 = (bytes, offset, value) => {
  bytes[offset] = value & 0xff
  bytes[offset + 1] = (value >>> 8) & 0xff
}

const writeUInt32 = (bytes, offset, value) => {
  bytes[offset] = value & 0xff
  bytes[offset + 1] = (value >>> 8) & 0xff
  bytes[offset + 2] = (value >>> 16) & 0xff
  bytes[offset + 3] = (value >>> 24) & 0xff
}

const buildLocalFileHeader = (nameBytes, dataBytes, crc32) => {
  const header = new Uint8Array(30)
  writeUInt32(header, 0, 0x04034b50)
  writeUInt16(header, 4, 20)
  writeUInt16(header, 6, 0x0800)
  writeUInt16(header, 8, 0)
  writeUInt16(header, 10, 0)
  writeUInt16(header, 12, 0)
  writeUInt32(header, 14, crc32)
  writeUInt32(header, 18, dataBytes.length)
  writeUInt32(header, 22, dataBytes.length)
  writeUInt16(header, 26, nameBytes.length)
  writeUInt16(header, 28, 0)
  return header
}

const buildCentralDirectoryHeader = (entry) => {
  const header = new Uint8Array(46)
  writeUInt32(header, 0, 0x02014b50)
  writeUInt16(header, 4, 20)
  writeUInt16(header, 6, 20)
  writeUInt16(header, 8, 0x0800)
  writeUInt16(header, 10, 0)
  writeUInt16(header, 12, 0)
  writeUInt16(header, 14, 0)
  writeUInt32(header, 16, entry.crc32)
  writeUInt32(header, 20, entry.dataBytes.length)
  writeUInt32(header, 24, entry.dataBytes.length)
  writeUInt16(header, 28, entry.nameBytes.length)
  writeUInt16(header, 30, 0)
  writeUInt16(header, 32, 0)
  writeUInt16(header, 34, 0)
  writeUInt16(header, 36, 0)
  writeUInt32(header, 38, 0)
  writeUInt32(header, 42, entry.localHeaderOffset)
  return header
}

const buildEndOfCentralDirectory = (entryCount, centralDirectorySize, centralDirectoryOffset) => {
  const footer = new Uint8Array(22)
  writeUInt32(footer, 0, 0x06054b50)
  writeUInt16(footer, 4, 0)
  writeUInt16(footer, 6, 0)
  writeUInt16(footer, 8, entryCount)
  writeUInt16(footer, 10, entryCount)
  writeUInt32(footer, 12, centralDirectorySize)
  writeUInt32(footer, 16, centralDirectoryOffset)
  writeUInt16(footer, 20, 0)
  return footer
}

const buildZipBlob = (files) => {
  const parts = []
  const entries = []
  let offset = 0

  for (const file of files) {
    const nameBytes = textEncoder.encode(file.path)
    const dataBytes = textEncoder.encode(file.content)
    const crc32 = calculateCrc32(dataBytes)
    const localHeader = buildLocalFileHeader(nameBytes, dataBytes, crc32)

    entries.push({
      nameBytes,
      dataBytes,
      crc32,
      localHeaderOffset: offset
    })
    parts.push(localHeader, nameBytes, dataBytes)
    offset += localHeader.length + nameBytes.length + dataBytes.length
  }

  const centralDirectoryOffset = offset
  let centralDirectorySize = 0

  for (const entry of entries) {
    const centralHeader = buildCentralDirectoryHeader(entry)
    parts.push(centralHeader, entry.nameBytes)
    centralDirectorySize += centralHeader.length + entry.nameBytes.length
  }

  parts.push(buildEndOfCentralDirectory(entries.length, centralDirectorySize, centralDirectoryOffset))
  return new Blob(parts, { type: XLSX_MIME_TYPE })
}

const buildXlsxBlob = (columns, rows, sheetName = '历史航迹') => {
  const safeSheetName = sanitizeSheetName(sheetName)
  return buildZipBlob([
    { path: '[Content_Types].xml', content: buildContentTypesXml() },
    { path: '_rels/.rels', content: buildPackageRelationshipsXml() },
    { path: 'docProps/app.xml', content: buildAppPropertiesXml() },
    { path: 'docProps/core.xml', content: buildCorePropertiesXml() },
    { path: 'xl/workbook.xml', content: buildWorkbookXml(safeSheetName) },
    { path: 'xl/_rels/workbook.xml.rels', content: buildWorkbookRelationshipsXml() },
    { path: 'xl/styles.xml', content: buildStylesXml() },
    { path: 'xl/worksheets/sheet1.xml', content: buildWorksheetXml(columns, rows) }
  ])
}

const triggerDownload = (blob, fileName) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

export const exportFlightSessionExcel = (detail = {}) => {
  const { rows, deviceGroups } = buildWorksheetRows(detail)

  if (!rows.length) {
    throw new Error('当前架次没有可导出的遥测记录')
  }

  const columns = [...BASE_COLUMNS, ...buildDeviceColumns(deviceGroups)]
  const workbookBlob = buildXlsxBlob(columns, rows)
  const baseName = sanitizeFileName((detail.file_name || detail.flight_id || 'flight-session').replace(/\.json$/i, ''))
  const fileName = `${baseName}-history-export.xlsx`

  triggerDownload(workbookBlob, fileName)

  return {
    fileName,
    format: 'xlsx',
    rowCount: rows.length,
    columnCount: columns.length,
    deviceGroupCount: deviceGroups.length
  }
}
