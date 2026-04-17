# 测试指令说明

本目录下的测试主要覆盖以下内容：

- `test_parser.py`
  用于验证飞控 JSON、气象仪 `psdk_data`、能见度仪 `psdk_data` 的解析逻辑。
- `test_m400_scenarios.py`
  用于验证 `M400` 飞行任务场景、故障场景、混发场景、气象设备专用场景。
- `test_flight_sessions.py`
  用于验证历史飞行架次的落盘、查询和删除接口。

## 1. 推荐运行方式

如果本机已经安装 `pytest`：

```powershell
cd backend
pytest tests -q
```

## 2. 未安装 `pytest` 时的运行方式

项目已兼容直接执行测试文件：

```powershell
cd backend
python tests\test_parser.py
python tests\test_m400_scenarios.py
python tests\test_flight_sessions.py
```

## 3. 场景说明

当前脚本化飞行场景统一遵循以下规则：

- 起始状态为地面待机，首帧为 `preflight_ready`
- 结束状态为自动降落完成，末帧为 `landed_shutdown`
- 默认时间戳使用生成当下的真实时间
- `30s` 场景按 `1s` 一帧生成飞控数据
- 支持根据时长拉长航迹，平均水平速度保持在约 `10 m/s`
- 支持湖南省范围内随机起点、飞行动作扰动、气象数据变化

## 4. 单独验证气象设备场景

只验证气象仪和能见度仪场景：

```powershell
cd backend
python tests\test_m400_scenarios.py
```

该文件中已经包含：

- `weather` 气象仪专用场景
- `visibility` 能见度仪数据检查
- `flight + psdk_data` 混发链路检查

## 5. 联调模拟脚本

如果需要把测试数据直接发送到后端 TCP 服务端，可以使用：

```powershell
cd backend
python simulate_drone.py --scenario m400_mission --duration-seconds 30
python simulate_drone.py --scenario m400_faults --duration-seconds 30
python simulate_drone.py --scenario m400_mixed --duration-seconds 30
python simulate_drone.py --scenario m400_weather --duration-seconds 30
```

支持循环测试：

```powershell
cd backend
python simulate_drone.py --scenario m400_mission --duration-seconds 30 --loop-count 5
python simulate_drone.py --scenario m400_mixed --duration-seconds 30 --loop-forever
```

说明：

- 每一轮回放都会按当前真实时间重新生成场景起点时间
- `m400_mission` / `m400_faults` / `m400_mixed` 都是从地面待机开始，到降落结束
- `m400_weather` 是纯气象设备数据流，不包含飞控起降过程

## 6. 只查看场景内容

不连接后端，只打印场景内容：

```powershell
cd backend
python simulate_drone.py --scenario m400_mission --duration-seconds 30 --dry-run
python simulate_drone.py --scenario m400_weather --duration-seconds 30 --dry-run
```
