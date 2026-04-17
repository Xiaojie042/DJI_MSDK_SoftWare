# 测试指令说明

本目录下的测试主要覆盖以下内容：

- `test_parser.py`
  用于验证飞控 JSON、气象仪 `psdk_data`、能见度仪 `psdk_data` 的解析逻辑。

- `test_m400_scenarios.py`
  用于验证 `M400` 飞行任务场景、故障场景、混发场景、气象设备专用场景。

## 1. 推荐运行方式

如果本机已经安装 `pytest`：

```powershell
cd backend
pytest tests -q
```

## 2. 未安装 pytest 时的运行方式

项目已经兼容直接执行测试文件：

```powershell
cd backend
python tests\test_parser.py
python tests\test_m400_scenarios.py
```

## 3. 单独验证气象设备场景

仅验证气象仪和能见度仪场景：

```powershell
cd backend
python tests\test_m400_scenarios.py
```

该文件中已经包含：

- `weather` 气象仪专用场景
- `visibility` 能见度仪专用数据检查
- `flight + psdk_data` 混发链路检查

## 4. 联调模拟脚本

如果需要把测试数据直接发送到后端 TCP 服务端，可以使用：

```powershell
cd backend
python simulate_drone.py --scenario m400_weather --duration-seconds 30
python simulate_drone.py --scenario m400_weather --duration-seconds 30 --loop-count 5
python simulate_drone.py --scenario m400_weather --duration-seconds 30 --loop-forever
```

其他常用场景：

```powershell
cd backend
python simulate_drone.py --scenario m400_mission --duration-seconds 30
python simulate_drone.py --scenario m400_faults --duration-seconds 30
python simulate_drone.py --scenario m400_mixed --duration-seconds 30
```

## 5. 仅查看场景内容

不连接后端，仅打印场景内容：

```powershell
cd backend
python simulate_drone.py --scenario m400_weather --duration-seconds 30 --dry-run
```
