# TopBar 组件重构说明

## 概述
已完成顶部全局状态栏（TopBar）的重构，专注于右侧状态栏的暗黑科技风格实现。

## 组件位置
- `frontend/src/components/dashboard/TopBar.vue` - 新建的 TopBar 组件
- `frontend/src/views/MonitorView.vue` - 已更新使用新组件

## 数据绑定

组件从 WebSocket 实时数据中绑定以下 5 个核心字段：

1. **飞行状态**: `is_flying` + `flight_mode_string`
   - 显示飞行模式（如 "P-GPS"）或 "待命"
   - 飞行中时文字变为绿色

2. **图传信号**: `air_link_status.link_signal_quality`
   - 范围: 1-5
   - 警告阈值: < 3（黄色警告）

3. **GPS 卫星数**: `gps_satellite_count`
   - 警告阈值: < 8（黄色警告）

4. **遥控器电量**: `remote_controller_status.battery_percentage`
   - 危险阈值: < 20%（红色闪烁）

5. **无人机电池**: `battery_status.main_battery.percentage`
   - 危险阈值: < 20%（红色闪烁）

## 样式特性

### 复用的 CSS 变量
- `var(--bg-panel)` - 毛玻璃背景
- `var(--glass-blur)` - 模糊效果
- `var(--text-main)` / `var(--text-muted)` - 文字颜色
- `var(--success)` - 成功状态（绿色）
- `var(--warning)` - 警告状态（黄色）
- `var(--danger)` - 危险状态（红色）

### 视觉反馈
- **正常状态**: 灰色图标和文字
- **警告状态**: 黄色高亮，边框变色
- **危险状态**: 红色高亮，边框变色，脉冲动画

### 响应式设计
- 桌面: 右侧状态栏占 50% 宽度
- 平板 (< 1100px): 状态栏自动换行
- 移动 (< 900px): 垂直布局，状态项均分宽度

## 测试建议

使用 `backend/replay_sample.py` 测试不同状态：

```bash
# 启动后端服务器
cd backend
python -m uvicorn app.main:app --reload

# 在另一个终端回放测试数据
python replay_sample.py --count 100 --interval 0.5
```

修改 `示例data.txt` 中的值来测试警告状态：
- 设置 `battery_status.main_battery.percentage` < 20 测试电量警告
- 设置 `gps_satellite_count` < 8 测试 GPS 警告
- 设置 `air_link_status.link_signal_quality` < 3 测试信号警告
