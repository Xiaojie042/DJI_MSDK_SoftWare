# 直播转发：RTMP 接收与 GB28181 转发

本项目新增的“直播转发”能力采用外部流媒体服务中转，FastAPI 只负责配置、启动停止、状态探测和日志采集。

## 技术选型

- RTMP 接收：优先使用 ZLMediaKit `MediaServer.exe`。它在 Windows 上易部署，支持 RTMP 发布、HTTP API 查询媒体列表，适合作为 PC 端本地收流服务。
- GB28181 转发：使用外部 GB28181 Device Bridge。该桥接程序必须实现设备侧 SIP REGISTER、心跳、鉴权、INVITE/ACK、RTP/PS、SSRC 和端口协商。
- FastAPI 不直接实现 RTMP Server，也不伪造完整 GB28181 协议栈。

仅使用 FFmpeg 从 RTMP 推一个视频流不等于完成 GB28181。GB28181 平台需要完整 SIP 信令链路和 PS-RTP 媒体链路，因此必须接入支持“PC 主动注册为 GB28181 设备”的成熟桥接组件。

## 后端接口

- `GET /api/live/config`：读取 RTMP 与 GB28181 配置、本机局域网 IP、RTMP 推流地址和依赖检测结果。
- `POST /api/live/config`：保存配置到 `data/live_config.json`。
- `POST /api/live/rtmp/start`：启动 ZLMediaKit RTMP 接收服务。
- `POST /api/live/rtmp/stop`：停止由后端托管启动的 RTMP 进程。
- `GET /api/live/rtmp/status`：查询服务进程、端口、ZLM API、`live/drone` 流在线状态、客户端数量、码率、帧率。
- `POST /api/live/gb28181/start`：启动外部 GB28181 桥接进程。
- `POST /api/live/gb28181/stop`：停止外部 GB28181 桥接进程。
- `GET /api/live/gb28181/status`：返回注册状态、推流状态、码率、帧率和最近错误。
- `GET /api/live/logs`：返回最近直播网关日志。

## 目录约定

推荐把第三方工具放在项目根目录：

```text
tools/
  zlmediakit/
    MediaServer.exe
  gb28181-bridge/
    gb28181-bridge.exe
```

也可以在前端“直播转发”面板里填写绝对路径。

## RTMP 接收配置

默认推流地址：

```text
rtmp://<PC_LAN_IP>/live/drone
```

本机测试地址：

```text
rtmp://127.0.0.1/live/drone
```

ZLMediaKit 默认 HTTP API：

```text
http://127.0.0.1:18080
```

如果 `1935` 或 `18080` 已被占用，请在前端面板中修改 RTMP 端口或 ZLM HTTP 端口，并保存配置后重新启动 RTMP 服务。

## GB28181 配置字段

示例：

```json
{
  "gb28181": {
    "sip_server_ip": "192.168.1.10",
    "sip_server_port": 5060,
    "sip_domain": "3402000000",
    "sip_server_id": "34020000002000000001",
    "device_id": "34020000001320000001",
    "channel_id": "34020000001320000002",
    "local_sip_port": 5062,
    "local_rtp_port_start": 30000,
    "local_rtp_port_end": 30100,
    "password": "12345678",
    "transport": "UDP",
    "ssrc": "1234567890",
    "auto_reconnect": true,
    "heartbeat_interval": 60,
    "rtmp_input_url": "rtmp://127.0.0.1/live/drone",
    "bridge_executable_path": "tools\\gb28181-bridge\\gb28181-bridge.exe",
    "bridge_command_template": ""
  }
}
```

如果桥接程序使用自定义命令行，可以填写命令模板。后端会先生成 `gb28181_bridge_config.json`，再替换模板变量：

```text
tools\gb28181-bridge\gb28181-bridge.exe --config {config_path}
```

可用变量包括：

```text
{config_path}
{rtmp_input_url}
{sip_server_ip}
{sip_server_port}
{sip_domain}
{sip_server_id}
{device_id}
{channel_id}
{local_sip_port}
{local_rtp_port_start}
{local_rtp_port_end}
{password}
{transport}
{ssrc}
{heartbeat_interval}
```

## 验证步骤

1. 启动后端和前端。
2. 打开地图界面左下角“直播转发”面板。
3. 检查 ZLMediaKit 路径，点击“保存配置”。
4. 点击“启动 RTMP”。
5. 用 FFmpeg 推测试流：

```powershell
ffmpeg -re -i test.mp4 -c:v libx264 -f flv rtmp://127.0.0.1/live/drone
```

6. 前端应显示 RTMP 服务在线、无人机视频流在线。
7. 配置远端 GB28181 平台参数和桥接程序路径。
8. 点击“开始转发”，查看日志中是否出现 SIP 注册、心跳、INVITE、RTP 推送等桥接程序输出。

远端平台不可达、鉴权失败、端口冲突或未配置桥接程序时，后端接口会返回明确错误，并在日志窗口显示最近错误。
