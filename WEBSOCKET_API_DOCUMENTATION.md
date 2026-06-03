# WebSocket 数据字段文档

## 概述

本文档描述了无人机地面站系统中 WebSocket 传输的数据格式和字段定义。前端通过 WebSocket 实时接收无人机遥测数据。

## 数据格式

WebSocket 消息采用 JSON 格式，每条消息为一个完整的 JSON 对象。

---

## 顶层字段

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `type` | String | 是 | 消息类型标识 | `"flight_data"` |
| `schema_version` | Number | 否 | 数据模式版本号 | `2` |
| `timestamp` | String/Number | 是 | 时间戳（字符串或 Unix 时间戳） | `"2026-04-13 16:01:52.538"` 或 `1681392112.538` |

---

## 姿态数据 (attitude)

描述无人机的三轴姿态角度。

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `attitude.pitch` | Number | 度 (°) | 俯仰角，向下为正 | `2.4` |
| `attitude.roll` | Number | 度 (°) | 横滚角，右倾为正 | `0.2` |
| `attitude.yaw` | Number | 度 (°) | 偏航角，顺时针为正 | `-15.1` |

---

## 速度数据 (velocity)

描述无人机的三维速度和合成速度。

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `velocity.x` | Number | m/s | X 轴速度（东西方向） | `0` |
| `velocity.y` | Number | m/s | Y 轴速度（南北方向） | `0` |
| `velocity.z` | Number | m/s | Z 轴速度（垂直方向） | `0` |
| `velocity.horizontal_speed` | Number | m/s | 水平速度 | `0` |
| `velocity.total_speed` | Number | m/s | 总速度 | `0` |
| `horizontal_speed` | Number | m/s | 水平速度（顶层字段，兼容） | `0` |
| `speed_total` | Number | m/s | 总速度（顶层字段，兼容） | `0` |

---

## 飞行模式与状态

| 字段名 | 类型 | 说明 | 可能值 |
|--------|------|------|--------|
| `flight_mode` | String | 飞行模式 | `"GPS_NORMAL"`, `"ATTI"`, `"MANUAL"` 等 |
| `flight_mode_string` | String | 飞行模式字符串（UI 显示用） | `"P-GPS"`, `"A-ATTI"` 等 |
| `fc_flight_mode` | String | 飞控飞行模式 | `"GPS_ATTI"`, `"GPS_NORMAL"` 等 |
| `is_flying` | Boolean | 是否正在飞行 | `true` / `false` |
| `are_motors_on` | Boolean | 电机是否启动 | `true` / `false` |
| `is_in_landing_mode` | Boolean | 是否处于降落模式 | `true` / `false` |
| `is_landing_confirmation_needed` | Boolean | 是否需要降落确认 | `true` / `false` |
| `flight_time_in_seconds` | Number | 飞行时长（秒） | `0` |

---

## 位置与导航

### 当前位置

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `position.latitude` | Number | 度 | 纬度 | `31.2304` |
| `position.longitude` | Number | 度 | 经度 | `121.4737` |
| `position.altitude` | Number | 米 | 相对高度 | `0` |
| `relative_altitude` | Number | 米 | 相对起飞点高度 | `0` |
| `aircraft_heading` | Number | 度 (°) | 机头朝向 | `-15.1` |
| `heading` | Number | 度 (°) | 航向角 | `-15.1` |

### 返航点 (home_location)

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `home_location.latitude` | Number | 度 | 返航点纬度 | `31.2304` |
| `home_location.longitude` | Number | 度 | 返航点经度 | `121.4737` |
| `home_distance` | Number | 米 | 距离返航点距离 | `0` |

### 高度与限制

| 字段名 | 类型 | 单位 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `go_home_height` | Number | 米 | 返航高度 | `100` |
| `height_limit` | Number | 米 | 限高 | `120` |
| `distance_limit_enabled` | Boolean | - | 是否启用限距 | `false` |
| `distance_limit` | Number | 米 | 限距距离 | `5000` |

---

## 无人机信息

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `aircraft_name` | String | 无人机型号名称 | `"Matrice 400"` |
| `product_type` | String | 产品类型 | `"DJI_MATRICE_400"` |
| `product_firmware_version` | String | 固件版本 | `"16.00.0813"` |
| `flight_controller_serial_number` | String | 飞控序列号 | `"1581F8DBW256G00A2PXY"` |
| `flight_controller_connected` | Boolean | 飞控是否连接 | `true` / `false` |
| `drone_id` | String | 无人机 ID（前端生成） | `"DJI-M400-001"` |

---

## GPS 与定位

| 字段名 | 类型 | 说明 | 可能值 |
|--------|------|------|--------|
| `gps_satellite_count` | Number | GPS 卫星数量 | `0` - `20+` |
| `gps_signal_level` | String | GPS 信号等级 | `"LEVEL_0"` - `"LEVEL_5"` |
| `gps_signal` | Number | GPS 信号强度（0-5） | `0` - `5` |

---

## 电池状态 (battery_status)

### 主电池 (main_battery)

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `battery_status.connected_count` | Number | - | 已连接电池数量 | `1` |
| `battery_status.main_battery.index` | Number | - | 电池索引 | `0` |
| `battery_status.main_battery.connected` | Boolean | - | 是否连接 | `true` |
| `battery_status.main_battery.percentage` | Number | % | 电量百分比 | `78` |
| `battery_status.main_battery.temperature_celsius` | Number | °C | 电池温度 | `29.3` |
| `battery_status.main_battery.voltage_mv` | Number | mV | 电压（毫伏） | `52306` |
| `battery_status.main_battery.serial_number` | String | - | 电池序列号 | `"8DAPP2TEA00173"` |
| `battery_status.main_battery.cell_voltages_mv` | Array | mV | 各电芯电压 | `[4025, 4025, ...]` |

### 副电池 (secondary_battery)

| 字段路径 | 类型 | 说明 | 示例值 |
|----------|------|------|--------|
| `battery_status.secondary_battery.index` | Number | 电池索引 | `1` |
| `battery_status.secondary_battery.connected` | Boolean | 是否连接 | `false` |
| `battery_status.secondary_battery.percentage` | Number | 电量百分比 | `0` |

### 电池概览 (overview)

| 字段路径 | 类型 | 说明 | 示例值 |
|----------|------|------|--------|
| `battery_status.overview[].index` | Number | 电池索引 | `0` |
| `battery_status.overview[].is_connected` | Boolean | 是否连接 | `true` |

### 电池告警阈值

| 字段名 | 类型 | 单位 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `low_battery_warning_threshold` | Number | % | 低电量警告阈值 | `15` |
| `serious_low_battery_warning_threshold` | Number | % | 严重低电量警告阈值 | `10` |
| `battery_threshold_behavior` | String | - | 低电量行为 | `"FLY_NORMALLY"`, `"LAND"`, `"RTH"` |

---

## 图传状态 (air_link_status)

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `air_link_status.connected` | Boolean | - | 图传是否连接 | `true` |
| `air_link_status.down_link_quality` | Number | % | 下行链路质量 | `100` |
| `air_link_status.down_link_quality_raw` | Number | % | 下行链路原始质量 | `90` |
| `air_link_status.up_link_quality` | Number | % | 上行链路质量 | `100` |
| `air_link_status.up_link_quality_raw` | Number | % | 上行链路原始质量 | `90` |
| `air_link_status.link_signal_quality` | Number | 1-5 | 链路信号质量（1-5档） | `5` |
| `air_link_status.dynamic_data_rate` | Number | Mbps | 动态数据速率 | `23.59` |
| `air_link_status.frequency_point` | Number | MHz | 频点 | `5804` |
| `air_link_status.frequency_band` | String | - | 频段 | `"BAND_MULTI"`, `"BAND_2_4G"`, `"BAND_5_8G"` |

---

## 遥控器状态 (remote_controller_status)

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `remote_controller_status.connected` | Boolean | - | 遥控器是否连接 | `true` |
| `remote_controller_status.mode` | String | - | 遥控器模式 | `"CHANNEL_A"`, `"CHANNEL_B"` |
| `remote_controller_status.serial_number` | String | - | 遥控器序列号 | `"7CACN880010UE1"` |
| `remote_controller_status.battery_percentage` | Number | % | 遥控器电量 | `12` |
| `remote_controller_connected` | Boolean | - | 遥控器连接状态（顶层） | `true` |
| `rc_signal` | Number | % | 遥控器信号强度 | `0` - `100` |

---

## 云台状态

| 字段名 | 类型 | 单位 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `gimbal_pitch` | Number | 度 (°) | 云台俯仰角 | `-90` - `30` |
| `gimbal_roll` | Number | 度 (°) | 云台横滚角 | `0` |
| `gimbal_yaw` | Number | 度 (°) | 云台偏航角 | `0` |

---

## 视觉定位系统 (vps_status)

| 字段路径 | 类型 | 单位 | 说明 | 示例值 |
|----------|------|------|------|--------|
| `vps_status.vision_positioning_enabled` | Boolean | - | 视觉定位是否启用 | `true` |
| `vps_status.ultrasonic_used` | Boolean | - | 是否使用超声波 | `false` |
| `vps_status.ultrasonic_height_cm` | Number | cm | 超声波高度 | `1` |

---

## 风速信息 (wind)

| 字段路径 | 类型 | 单位 | 说明 | 可能值 |
|----------|------|------|------|--------|
| `wind.speed` | Number | m/s | 风速 | `0` - `20+` |
| `wind.direction` | String | - | 风向 | `"WINDLESS"`, `"NORTH"`, `"SOUTH"`, `"EAST"`, `"WEST"` 等 |
| `wind.warning` | String | - | 风速警告等级 | `"LEVEL_0"` - `"LEVEL_2"` |

---

## 返航与故障保护

| 字段名 | 类型 | 说明 | 可能值 |
|--------|------|------|--------|
| `auto_rth_reason` | String | 自动返航原因 | `"NONE"`, `"LOW_BATTERY"`, `"LOST_SIGNAL"`, `"SMART_RTH"` |
| `failsafe_action` | String | 失联保护动作 | `"GOHOME"`, `"HOVER"`, `"LAND"` |

---

## 飞行器状态 (aircraft_status)

| 字段路径 | 类型 | 说明 | 示例值 |
|----------|------|------|--------|
| `aircraft_status.home_location.latitude` | Number | 返航点纬度 | `31.2304` |
| `aircraft_status.home_location.longitude` | Number | 返航点经度 | `121.4737` |

---

## 前端使用的字段映射

### TopBar 状态栏使用的字段

| UI 显示 | 数据源字段 | 说明 |
|---------|-----------|------|
| 飞行状态 | `is_flying` + `flight_mode_string` | 显示飞行模式或"待命" |
| 图传信号 | `air_link_status.link_signal_quality` | 1-5档信号强度 |
| GPS 卫星 | `gps_satellite_count` | 卫星数量 |
| 遥控器电量 | `remote_controller_status.battery_percentage` | 遥控器电量百分比 |
| 无人机电池 | `battery_status.main_battery.percentage` | 主电池电量百分比 |

### Popup 弹窗使用的字段

| UI 显示 | 数据源字段 | 说明 |
|---------|-----------|------|
| 无人机型号 | `aircraft_name` 或 `product_type` | 型号名称 |
| 俯仰角 | `attitude.pitch` | 姿态角度 |
| 横滚角 | `attitude.roll` | 姿态角度 |
| 偏航角 | `attitude.yaw` | 姿态角度 |
| 航向角 | `aircraft_heading` 或 `heading` | 机头朝向 |
| 真实高度 | `relative_altitude` 或 `position.altitude` | 相对起飞点高度 |
| 海拔高度 | `position.altitude` | 海拔高度 |
| 纬度 | `position.latitude` | GPS 纬度 |
| 经度 | `position.longitude` | GPS 经度 |

---

## 数据示例

### 完整 JSON 示例

```json
{
  "type": "flight_data",
  "schema_version": 2,
  "timestamp": "2026-04-13 16:01:52.538",
  "attitude": {
    "pitch": 2.4,
    "roll": 0.2,
    "yaw": -15.1
  },
  "velocity": {
    "x": 0,
    "y": 0,
    "z": 0,
    "horizontal_speed": 0,
    "total_speed": 0
  },
  "horizontal_speed": 0,
  "speed_total": 0,
  "flight_mode": "GPS_NORMAL",
  "flight_mode_string": "P-GPS",
  "fc_flight_mode": "GPS_ATTI",
  "is_flying": false,
  "are_motors_on": false,
  "is_in_landing_mode": false,
  "is_landing_confirmation_needed": false,
  "flight_time_in_seconds": 0,
  "aircraft_name": "Matrice 400",
  "product_type": "DJI_MATRICE_400",
  "product_firmware_version": "16.00.0813",
  "flight_controller_serial_number": "1581F8DBW256G00A2PXY",
  "flight_controller_connected": true,
  "remote_controller_connected": true,
  "aircraft_heading": -15.1,
  "heading": -15.1,
  "relative_altitude": 0,
  "gps_satellite_count": 12,
  "gps_signal_level": "LEVEL_4",
  "go_home_height": 100,
  "height_limit": 120,
  "distance_limit_enabled": false,
  "distance_limit": 5000,
  "low_battery_warning_threshold": 15,
  "serious_low_battery_warning_threshold": 10,
  "battery_threshold_behavior": "FLY_NORMALLY",
  "auto_rth_reason": "NONE",
  "failsafe_action": "GOHOME",
  "home_location": {
    "latitude": 31.2304,
    "longitude": 121.4737
  },
  "position": {
    "latitude": 31.2304,
    "longitude": 121.4737,
    "altitude": 0
  },
  "wind": {
    "speed": 0,
    "direction": "WINDLESS",
    "warning": "LEVEL_0"
  },
  "vps_status": {
    "vision_positioning_enabled": true,
    "ultrasonic_used": false,
    "ultrasonic_height_cm": 1
  },
  "battery_status": {
    "connected_count": 1,
    "overview": [
      {
        "index": 0,
        "is_connected": true
      }
    ],
    "main_battery": {
      "index": 0,
      "connected": true,
      "percentage": 78,
      "temperature_celsius": 29.3,
      "voltage_mv": 52306,
      "serial_number": "8DAPP2TEA00173",
      "cell_voltages_mv": [4025, 4025, 4024, 4022, 4023, 4024, 4023, 4023, 4024, 4023, 4025, 4022, 4024]
    },
    "secondary_battery": {
      "index": 1
    }
  },
  "air_link_status": {
    "connected": true,
    "down_link_quality": 100,
    "down_link_quality_raw": 90,
    "up_link_quality": 100,
    "up_link_quality_raw": 90,
    "link_signal_quality": 5,
    "dynamic_data_rate": 23.59,
    "frequency_point": 5804,
    "frequency_band": "BAND_MULTI"
  },
  "remote_controller_status": {
    "connected": true,
    "mode": "CHANNEL_A",
    "serial_number": "7CACN880010UE1",
    "battery_percentage": 85
  },
  "aircraft_status": {
    "home_location": {
      "latitude": 31.2304,
      "longitude": 121.4737
    }
  }
}
```

---

## 注意事项

### 数据类型兼容性

1. **时间戳格式**：支持字符串（ISO 8601）或 Unix 时间戳（秒）
2. **布尔值**：支持 `true/false`、`1/0`、`"true"/"false"` 等多种格式
3. **数值字段**：前端会自动处理 `null`、`undefined` 和非法数值

### 字段优先级

当存在多个相似字段时，前端按以下优先级读取：

1. **高度**：`relative_altitude` > `position.altitude` > `altitude`
2. **航向**：`aircraft_heading` > `heading`
3. **水平速度**：`velocity.horizontal_speed` > `horizontal_speed`

### 必需字段

以下字段是前端正常运行的最低要求：

- `timestamp`：时间戳
- `is_flying`：飞行状态
- `position.latitude`：纬度
- `position.longitude`：经度
- `battery_status.main_battery.percentage`：电池电量

### 可选字段

所有其他字段均为可选，前端会使用默认值或显示 `--`。

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 2.0 | 2026-04-17 | 当前版本，支持完整遥测数据 |
| 1.0 | 2026-01-01 | 初始版本 |

---

## 联系方式

如有疑问或需要补充字段，请联系前端开发团队。
