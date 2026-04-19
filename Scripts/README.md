# Windows 打包说明

## 目录结构

`Scripts/` 用来存放会提交到 Git 的打包脚本、辅助源码和打包方案。  
`Scripts/release/` 用来存放每次执行打包后生成的运行版本、编译中间文件和运行时数据，这个目录已经在仓库 `.gitignore` 中忽略，不会污染提交。

推荐结构如下：

```text
Scripts/
  README.md
  build_release.bat
  start.bat
  stop.bat
  release.env.example
  _src/
    backend_entry.py
    frontend_static_server.py
  release/
    backend/
    frontend/
    tools/
    data/
    logs/
    _build/
```

## 打包方案

当前方案按照“最少依赖、最方便迁移到另一台 Windows 电脑”来设计：

- 前端：使用 `Vite build` 生成静态文件。
- 后端：使用 `PyInstaller --onedir` 打包成独立目录版可执行程序。
- 前端静态服务：额外打包一个很小的 `frontend-server.exe`，避免目标机器再安装 Node.js 或额外 Web 服务。
- 启动方式：保留 `Scripts/start.bat` 和 `Scripts/stop.bat`，通过批处理一键启动和停止。
- 运行目录：打包后的实际交付文件都落在 `Scripts/release/` 下，便于整体复制到其他 Windows 电脑。

这个方案的优点：

- 目标机器不需要安装 Node.js。
- 目标机器不需要手工创建 Python 虚拟环境。
- 调试和排查问题比单文件 exe 更容易。
- 前后端仍然保持现有结构，改动最小。

## 打包前准备

执行打包前，先确认本机开发环境已经准备好：

1. 已安装 Python `3.11.x`。
2. 已安装 Node.js `20 LTS`，并确保 `npm.cmd` 在 `PATH` 中可用。
3. 仓库后端虚拟环境已创建在 `backend/.venv/`。
4. 后端虚拟环境中已安装项目依赖和 `PyInstaller`。
5. 前端依赖已在 `frontend/node_modules/` 中安装完成。

建议先做这几个检查：

```powershell
python --version
node --version
npm --version
.\backend\.venv\Scripts\python.exe -m PyInstaller --version
```

如果 `PyInstaller` 未安装，可以执行：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install pyinstaller
```

如果当前终端暂时识别不到 `npm.cmd`，也可以在打包前临时指定：

```powershell
$env:NPM_CMD='C:\Users\你的用户名\AppData\Local\Programs\node-v20.20.2-win-x64\npm.cmd'
.\Scripts\build_release.bat
```

## 前端打包教程

前端最终会被构建成静态资源，供 `frontend-server.exe` 提供访问。

当前打包脚本会自动注入这些生产参数：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_WS_URL=ws://127.0.0.1:8000/ws
VITE_API_HOST=127.0.0.1
VITE_API_PORT=8000
```

如果你只想单独验证前端构建，可以手工执行：

```powershell
cd E:\github_project\DJI_MSDK_SoftWare\frontend
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
$env:VITE_WS_URL='ws://127.0.0.1:8000/ws'
$env:VITE_API_HOST='127.0.0.1'
$env:VITE_API_PORT='8000'
npm run build
```

执行成功后，会生成 `frontend/dist/`，随后 `Scripts/build_release.bat` 会把它复制到 `Scripts/release/frontend/dist/`。

## 后端打包教程

后端打包使用的是 `PyInstaller --onedir`，入口脚本是：

- [backend_entry.py](E:/github_project/DJI_MSDK_SoftWare/Scripts/_src/backend_entry.py)

它会直接启动现有 FastAPI 应用，不启用 `reload`，适合发布版。

如果你只想单独验证后端打包，可以手工执行类似命令：

```powershell
cd E:\github_project\DJI_MSDK_SoftWare
.\backend\.venv\Scripts\python.exe -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name drone-backend `
  --distpath .\Scripts\release\backend `
  --workpath .\Scripts\release\_build\backend `
  --specpath .\Scripts\release\_build\spec `
  --paths .\backend `
  --collect-submodules uvicorn `
  --collect-submodules websockets `
  --collect-submodules sqlalchemy `
  --collect-submodules pydantic_settings `
  --hidden-import aiosqlite `
  .\Scripts\_src\backend_entry.py
```

后端运行时配置由 `Scripts/release/.env` 提供。  
这个文件不是手工维护的源文件，而是打包时由 [release.env.example](E:/github_project/DJI_MSDK_SoftWare/Scripts/release.env.example) 自动复制生成。

当前默认端口如下：

- API / WebSocket：`8000`
- TCP 遥测接入：`9001`
- 前端静态服务：`3000`

## 一键打包

在仓库根目录执行：

```powershell
.\Scripts\build_release.bat
```

脚本会完成这些事情：

1. 检查后端虚拟环境和 `npm.cmd` 是否可用。
2. 构建前端静态资源。
3. 清理旧的二进制和旧的编译中间文件。
4. 打包后端 `drone-backend.exe`。
5. 打包前端静态服务 `frontend-server.exe`。
6. 复制 `release.env.example` 到 `Scripts/release/.env`。
7. 补齐 `data/`、`logs/`、`flights/` 等运行目录。

## 打包后如何运行

打包完成后，不要进入 `Scripts/release/` 手工找 exe 运行，统一使用根脚本：

启动：

```powershell
.\Scripts\start.bat
```

停止：

```powershell
.\Scripts\stop.bat
```

启动脚本会自动做这些事情：

1. 从 `Scripts/release/` 下启动后端 exe。
2. 从 `Scripts/release/` 下启动前端静态服务 exe。
3. 自动打开浏览器访问 `http://127.0.0.1:3000`。

## 迁移到另一台 Windows 电脑

如果只是把项目打包后给另一台 Windows 电脑本机使用，最简单的方式是直接复制整个 `Scripts/` 文件夹。

目标机器上的使用步骤：

1. 复制整个 `Scripts/` 文件夹。
2. 双击 `Scripts/start.bat`。
3. 浏览器打开 `http://127.0.0.1:3000`。
4. 使用结束后，双击 `Scripts/stop.bat`。

## 常见调整

### 1. 修改发布版后端配置

编辑：

- [Scripts/release/.env](E:/github_project/DJI_MSDK_SoftWare/Scripts/release/.env)

常见可调整项：

- `API_HOST`
- `API_PORT`
- `TCP_SERVER_HOST`
- `TCP_SERVER_PORT`
- `MQTT_BROKER_HOST`
- `LOG_LEVEL`

### 2. 让局域网内其他设备访问前端

默认情况下，前端静态服务只监听 `127.0.0.1:3000`。  
如果要让局域网其他设备访问，可以修改：

- [start.bat](E:/github_project/DJI_MSDK_SoftWare/Scripts/start.bat)

把：

```text
--host 127.0.0.1
```

改成：

```text
--host 0.0.0.0
```

如果浏览器也需要直接访问后端接口，还需要把 `Scripts/release/.env` 中的：

```text
API_HOST=127.0.0.1
```

改成：

```text
API_HOST=0.0.0.0
```

## 提交建议

建议提交到 Git 的内容只有：

- `Scripts/README.md`
- `Scripts/build_release.bat`
- `Scripts/start.bat`
- `Scripts/stop.bat`
- `Scripts/release.env.example`
- `Scripts/_src/*`
- `.gitignore` 中新增的 `Scripts/release/`

不要提交：

- `Scripts/release/` 下的 exe
- `Scripts/release/` 下的 `frontend/dist`
- `Scripts/release/_build`
- `Scripts/release/data` 中的数据库和历史数据
