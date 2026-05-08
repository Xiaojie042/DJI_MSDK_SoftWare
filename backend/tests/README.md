# 后端测试与联调环境说明

这里的“测试”分成两类：

- **联调测试环境**：默认连接已经启动的后端和前端，检查 API、WebSocket、TCP、直播转发等链路，并可选启动模拟遥测发送器。
- **单元/逻辑测试**：只运行 `pytest` 或单文件测试，不依赖正在运行的前后端服务。

日常联调优先使用 `run_test_environment.py`。注意：默认不会启动后端或前端，因为实际调试时通常已经手动启动好了。

## 检查已启动的测试环境

先按项目正常方式启动后端和前端，然后在仓库根目录执行：

```powershell
python backend\tests\run_test_environment.py --with-frontend --smoke
```

默认检查：

- 后端 API：`http://127.0.0.1:8000/api/health`
- WebSocket 地址提示：`ws://127.0.0.1:8000/ws`
- TCP 遥测端口提示：`0.0.0.0:8888`
- 前端页面：`http://127.0.0.1:3000`

如果只检查后端：

```powershell
python backend\tests\run_test_environment.py --smoke
```

## 连接已启动后端并发送模拟遥测

后端已经启动后，可以只启动模拟器：

```powershell
python backend\tests\run_test_environment.py --with-simulator --scenario m400_mixed --loop-forever
```

可选场景：

- `random`
- `m400_mission`
- `m400_faults`
- `m400_mixed`
- `m400_weather`

只发送有限轮次：

```powershell
python backend\tests\run_test_environment.py --with-simulator --scenario m400_mission --loop-count 3
```

按 `Ctrl+C` 只会停止脚本启动的辅助进程，例如模拟器；不会停止你已经手动启动的后端或前端。

## 端口和地址

默认端口：

- API：`8000`
- TCP：`8888`
- 前端：`3000`

如果后端不是默认端口：

```powershell
python backend\tests\run_test_environment.py --api-port 18000 --with-frontend --frontend-port 13000 --smoke
```

如果局域网其他设备访问，请把客户端地址改成 PC 的局域网 IP：

```powershell
python backend\tests\run_test_environment.py --api-client-host 192.168.1.100 --with-frontend --smoke
```

查看将要检查或启动的内容：

```powershell
python backend\tests\run_test_environment.py --dry-run --with-frontend --with-simulator
```

## 特殊情况：由脚本启动服务

一般不推荐日常使用，但保留给临时隔离联调：

```powershell
python backend\tests\run_test_environment.py --start-backend
```

如果确实需要脚本一起启动前端：

```powershell
python backend\tests\run_test_environment.py --start-backend --start-frontend
```

这种模式会使用隔离数据目录 `backend/data/test_env`，避免污染当前正式调试用的 `data` 目录。脚本退出时会停止它自己启动的后端和前端。

## 直播转发联调

直播转发建议使用你当前正在运行的后端配置，不再由测试环境复制或覆盖配置。

需要确认的依赖：

- ZLMediaKit：`tools/zlmediakit/MediaServer.exe`
- GB28181 主动注册桥接工具：在前端直播转发面板配置 `bridge_executable_path`
- FFmpeg：用于手动推测试流，不等同于完整 GB28181 设备侧链路

测试 RTMP 输入：

```powershell
ffmpeg -re -i test.mp4 -an -c:v libx264 -f flv rtmp://127.0.0.1/live/drone
```

前端直播管理面板中应能看到 RTMP 流在线、HTTP-FLV/WebRTC 预览状态、GB28181 注册和推流状态。

## 单元/逻辑测试

这些命令只验证代码逻辑，不启动完整服务：

```powershell
python backend\tests\run_tests.py
```

或：

```powershell
cd backend
python -m pytest tests -q
```

单文件运行：

```powershell
cd backend
python tests\test_parser.py
python tests\test_m400_scenarios.py
python tests\test_dispatcher.py
python tests\test_runtime_config.py
python tests\test_flight_sessions.py
python tests\test_live_gateway.py
```

测试文件说明：

- `test_parser.py`：验证 TCP JSON 拆包、飞控遥测解析、气象仪和能见度仪 `psdk_data` 解析。
- `test_m400_scenarios.py`：验证 M400 任务、故障、混合流、气象设备场景生成和解析。
- `test_dispatcher.py`：验证 PSDK 数据能分发到 MQTT、WebSocket 和本地存储。
- `test_runtime_config.py`：验证运行时配置持久化、TCP 端口切换和双 MQTT 目标路由。
- `test_flight_sessions.py`：验证飞行架次落盘、摘要缓存、详情查询、删除和原始历史清理。
- `test_live_gateway.py`：验证 RTMP/GB28181 配置持久化、ZLMediaKit/Happytime 桥接配置、国标 ID 校验、日志状态推断和错误过滤。
- `run_tests.py`：单元/逻辑测试入口。
- `run_test_environment.py`：联调环境检查与辅助模拟器入口。

## 常见问题

- 后端检查失败：确认后端已经启动，并且 `--api-port` 与实际端口一致。
- 前端检查失败：确认前端已经启动，并且 `--frontend-port` 与实际端口一致。
- 前端能打开但没有数据：确认遥控器或 `--with-simulator` 正在向 TCP 端口发送遥测。
- RTMP 在线但国标平台看不到：先确认 GB28181 桥接工具能完成 SIP REGISTER、心跳、INVITE、RTP/PS 推送；FFmpeg 只推视频不算完整 GB28181 链路。
