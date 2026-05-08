# DJI 无人机地面站监控系统

## 1. 项目介绍

本项目是一个面向 DJI 无人机的地面站监控系统，目标是把遥控器/机载端发送过来的飞控遥测数据、气象设备数据和能见度设备数据统一接入，在前端形成可视化监控界面。

项目当前已经具备以下能力：

- 实时接收飞控 JSON 数据
- 实时接收 PSDK 气象仪、能见度仪数据
- 在地图上显示无人机位置、航向和飞行轨迹
- 显示无人机状态、原始数据明细、气象侧边栏
- 将历史数据持久化到本地 SQLite 和 JSONL
- 提供 M400 场景模拟、故障模拟、气象设备模拟与解析测试

该系统适合用于：

- DJI MSDK/PSDK 数据联调
- 无人机任务态势展示
- 本地演示、测试、内网部署
- 后续接入云端 MQTT 或上层业务系统

---

## 2. 技术架构

### 2.1 前后端组成

- 前端：`Vue 3 + Vite + Pinia + Leaflet`
- 后端：`FastAPI + WebSocket + TCP Server + SQLite`
- 可选消息中间件：`EMQX MQTT`

### 2.2 数据流

```text
DJI 遥控器 / MSDK App
        |
        | TCP JSON
        v
backend/app/tcp_server/server.py
        |
        v
backend/app/tcp_server/parser.py
        |
        +------------------> WebSocket 广播 --> 前端实时界面
        |
        +------------------> SQLite 落库
        |
        +------------------> JSONL 原始历史落盘
        |
        +------------------> MQTT 发布（可选）
```

### 2.3 模块说明

- `backend/app/tcp_server`
  负责 TCP 接收、粘包拆包处理、JSON 解析入口
- `backend/app/services/dispatcher.py`
  负责把解析后的数据分发到 WebSocket、存储、MQTT
- `backend/app/services/storage.py`
  负责本地 SQLite 和 JSONL 持久化
- `backend/app/services/psdk_data_parser.py`
  负责气象仪和能见度仪数据解析
- `backend/app/api/router.py`
  提供健康检查、历史记录查询接口
- `frontend/src/views/MonitorView.vue`
  主监控界面
- `frontend/src/composables/useWebSocket.js`
  前端实时数据接入
- `frontend/src/stores/droneStore.js`
  前端状态管理与本地缓存

---

## 3. 目录结构

```text
DJI_MSDK_SoftWare/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ mqtt/
│  │  ├─ services/
│  │  ├─ tcp_server/
│  │  ├─ utils/
│  │  └─ websocket/
│  ├─ data/
│  ├─ tests/
│  ├─ requirements.txt
│  ├─ simulate_drone.py
│  └─ replay_sample.py
├─ frontend/
│  ├─ src/
│  │  ├─ components/
│  │  ├─ composables/
│  │  ├─ stores/
│  │  └─ views/
│  ├─ package.json
│  └─ vite.config.js
├─ docker-compose.yml
└─ README.md
```

---

## 4. 当前推荐端口

以下说明以仓库当前配置为准：

- `backend/.env`
- `frontend/vite.config.js`

| 模块              | 端口      | 说明                |
| --------------- | -------:| ----------------- |
| 前端开发服务          | `3000`  | 浏览器访问地址           |
| 后端 HTTP API     | `8000`  | `/api/*` 与 `/ws`  |
| 后端 TCP 接收       | `8888`  | 遥控器/Socket 推流目标端口 |
| MQTT Broker（可选） | `1883`  | EMQX 默认 TCP 端口    |
| EMQX 控制台（可选）    | `18083` | Broker 管理页面       |

说明：

- 遥控器应连接 **TCP 接收端口**，不是 HTTP API 端口。
- 如果你修改了 `.env`，请以修改后的端口为准。

---

## 5. 运行环境准备

推荐环境：

- 操作系统：`Windows 10/11`
- Python：`3.9.x`
- Node.js：`18 LTS` 或以上
- npm：`9+`
- Git：可选
- Docker Desktop：可选，仅用于 EMQX 或后续容器化部署

网络要求：

- 遥控器与运行后端的电脑处于同一局域网
- 目标电脑开放对应端口的防火墙访问权限
- 建议至少放行：
  - `3000`
  - `8000`
  - `8888`
  - `1883`（如果启用 MQTT）

---

## 6. 本机启动方式

### 6.1 启动后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

如果需要重新生成环境文件，可参考：

```powershell
cd backend
copy .env.example .env
```

### 6.2 启动前端

```powershell
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

如需单独配置前端环境变量，可参考：

```powershell
cd frontend
copy .env.example .env
```

### 6.3 可选：启动 MQTT

当前系统即使不启动 MQTT，也不影响前端实时显示。

如果需要本地启用 EMQX：

```powershell
docker compose up -d emqx
```

---

## 7. 如何连接遥控器

### 7.1 接入前确认

请先确认：

1. 后端已经启动
2. 运行后端的电脑与遥控器在同一局域网
3. 已知道电脑当前 IPv4 地址
4. 防火墙未拦截 `8888` 端口

### 7.2 查询本机 IP

在运行后端的电脑上执行：

```powershell
ipconfig
```

找到当前网卡的 IPv4 地址，例如：

```text
192.168.1.100
```

### 7.3 在遥控器 / MSDK App 中配置

在遥控器对应的 Socket/TCP 推流配置中填写：

- 目标 IP：运行后端电脑的局域网 IP，例如 `192.168.1.100`
- 目标端口：`8888`

注意：

- 这里填写的是 **TCP 接收端口**
- 不要填 `8000`
- 不要填前端页面端口 `3000`

### 7.4 验证是否连接成功

连接成功后，通常会看到以下现象：

- 后端日志出现 TCP 客户端接入信息
- 前端界面从“未接入”切换为实时状态
- 地图出现无人机位置与轨迹
- 原始数据面板开始刷新 JSON 数据
- 气象侧栏开始显示风向、温湿度、气压、海拔、能见度

---

## 8. 测试与模拟

### 8.1 解析测试

```powershell
cd backend
python tests\test_parser.py
```

### 8.2 M400 场景测试

```powershell
cd backend
python tests\test_m400_scenarios.py
```

### 8.3 统一运行测试

如果环境里已安装 `pytest`：

```powershell
cd backend
pytest tests -q
```

### 8.4 飞控场景模拟

```powershell
cd backend
python simulate_drone.py --scenario m400_mission --duration-seconds 30
python simulate_drone.py --scenario m400_faults --duration-seconds 30
python simulate_drone.py --scenario m400_mixed --duration-seconds 30
```

### 8.5 气象设备专用模拟

```powershell
cd backend
python simulate_drone.py --scenario m400_weather --duration-seconds 30
python simulate_drone.py --scenario m400_weather --duration-seconds 30 --loop-forever
```

### 8.6 样例数据回放

```powershell
cd backend
python replay_sample.py --count 20 --interval 0.5
```

更多测试命令可参考：

- [backend/tests/README.md](/e:/DJI_MSDK_SoftWare/backend/tests/README.md)

---

## 9. 数据存储说明

系统当前会在本地保留两类数据：

### 9.1 SQLite 结构化历史

默认文件：

```text
backend/drone_monitor.db
```

用途：

- 查询飞控历史
- 恢复最近飞行记录
- 为前端初始化提供结构化数据

### 9.2 JSONL 原始历史

默认文件：

```text
backend/data/telemetry_raw.jsonl
```

用途：

- 保存原始转发帧
- 保存 `psdk_data`
- 便于调试、追溯和离线回放

如果你需要迁移历史数据到另一台机器，请一并复制这两个文件。

---

## 10. 迁移到另一台机器

### 10.1 迁移前需要准备

在目标机器上准备：

- Python 3.9
- Node.js 18+
- npm
- 与遥控器同一局域网
- 放行 `3000 / 8000 / 8888`

建议迁移时复制以下内容：

- 整个项目目录
- `backend/.env`
- `frontend/.env`（如果你有自定义）
- `backend/drone_monitor.db`
- `backend/data/telemetry_raw.jsonl`

### 10.2 在新机器上的使用流程

1. 安装 Python 与 Node.js
2. 将项目拷贝到目标机器
3. 后端安装依赖并启动
4. 前端安装依赖并启动
5. 重新确认目标机器局域网 IP
6. 在遥控器中把 Socket 推流目标改为新机器的 IP

### 10.3 新机器启动命令

后端：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

浏览器访问：

```text
http://<目标机器IP>:3000
```

---

## 11. 推荐打包方法

### 11.1 当前阶段最推荐的方案

当前项目最稳妥的打包方式，不是直接做“单文件 exe”，而是做一个 **内网发布包**：

- 前端打包成 `dist`
- 后端保留 Python 服务形态
- 发布时带上 `.env`、数据库、原始历史文件

原因：

- 现阶段最稳定，便于现场排障
- 后续改端口、改设备 IP、改接口配置都更容易
- 对 WebSocket、TCP、SQLite、原始数据落盘这类服务程序更友好

### 11.2 建议的发布包结构

```text
release/
├─ backend/
│  ├─ app/
│  ├─ data/
│  ├─ requirements.txt
│  ├─ .env
│  └─ drone_monitor.db
├─ frontend/
│  └─ dist/
├─ docker-compose.yml
└─ README.md
```

### 11.3 前端打包建议

前端构建前，建议显式写入后端地址：

```powershell
cd frontend
$env:VITE_API_BASE_URL="http://部署机IP:8000"
$env:VITE_WS_URL="ws://部署机IP:8000/ws"
npm run build
```

这样生成的 `dist` 可以直接指向固定后端，不依赖开发代理。

### 11.4 前端发布方式建议

推荐两种方式：

#### 方式 A：继续使用开发模式

适合内部测试和快速迁移：

```powershell
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

优点：

- 最简单
- 不需要额外静态服务器

#### 方式 B：使用静态服务器发布 `dist`

适合交付版本：

- 用 `Caddy`、`Nginx` 或其他轻量静态服务器托管 `frontend/dist`
- 后端继续用 Python/FastAPI 运行
- 前端构建时写死 `VITE_API_BASE_URL` 和 `VITE_WS_URL`

### 11.5 后端发布方式建议

当前阶段建议：

- 后端直接保留源码运行
- 目标机器安装 Python 3.9 后运行

后续如果需要做真正的“免安装交付”，建议再单独推进：

- `PyInstaller onedir` 打包后端
- `Caddy/Nginx` 托管前端静态文件
- 最终组合成一套 Windows 发布目录

也就是说：

- **当前最推荐：前端 `dist` + 后端 Python 服务**
- **后续正式封装：后端可执行文件 + 静态前端服务器**

---

## 12. 常见问题

### 12.1 为什么前端能显示，但 MQTT 没启动？

因为 MQTT 当前是可选链路。系统的主显示链路是：

- TCP -> Parser -> WebSocket -> Frontend

MQTT 不在线不会影响主界面显示。

### 12.2 为什么遥控器连上了但页面没有更新？

优先检查：

1. 遥控器是否连到了 `TCP 接收端口`，不是 `8000`
2. 遥控器和电脑是否同网段
3. 防火墙是否放行 `8888`
4. 后端日志是否出现 TCP 客户端连接记录

### 12.3 为什么迁移到新机器后还是看不到数据？

通常是以下原因：

1. 遥控器仍然在往旧机器 IP 发数据
2. 新机器防火墙未放行
3. `.env` 中端口被改过但前端/遥控器没有同步

---

## 13. 后续建议

如果后续要进入正式交付阶段，建议优先补以下内容：

1. 增加统一启动脚本，例如 `start_backend.bat` / `start_frontend.bat`
2. 增加发布脚本，例如 `package_release.ps1`
3. 增加前端生产静态托管方案
4. 增加 Dockerfile，形成完整容器化部署方案
5. 增加一份“现场部署检查清单”

---

## 14. 默认启动命令速查

后端：

```powershell
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port 3000
```

气象设备场景模拟：

```powershell
cd backend
python simulate_drone.py --scenario m400_weather --duration-seconds 30
```

---

## 15. 直播转发：RTMP 接收与 GB28181 上送

地图界面左下角新增“直播转发”面板，支持显示本机局域网 IP、RTMP 推流地址、RTMP 服务状态、无人机视频流在线状态、GB28181 注册/推流状态和最近日志。

关键边界：

- FastAPI 只做配置、进程控制、状态监控和日志管理。
- RTMP 接收优先使用 ZLMediaKit `MediaServer.exe`。
- GB28181 必须接入支持“PC 主动注册为国标设备”的外部桥接程序。
- 仅用 FFmpeg 推 RTMP 或 RTP 不能视为完整 GB28181，因为缺少 SIP 注册、心跳、鉴权、INVITE、RTP/PS、SSRC 和端口协商。

推荐第三方工具目录：

```text
tools/
  zlmediakit/
    MediaServer.exe
  gb28181-bridge/
    gb28181-bridge.exe
```

本机 RTMP 验证：

```powershell
ffmpeg -re -i test.mp4 -c:v libx264 -f flv rtmp://127.0.0.1/live/drone
```

详细安装说明、配置示例和测试步骤见：

- [docs/live-forwarding.md](/e:/DJI_MSDK_SoftWare/docs/live-forwarding.md)
