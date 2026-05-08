# ZLMediaKit

Place the ZLMediaKit Windows server executable here:

```text
tools/zlmediakit/MediaServer.exe
```

The backend looks for this path automatically when starting the RTMP service.

ZLMediaKit official docs currently describe building or installing the project rather than downloading a prebuilt GitHub release:

- https://docs.zlmediakit.com/zh/tutorial/
- https://github.com/ZLMediaKit/ZLMediaKit/releases

After placing the executable, start it from the frontend live forwarding panel, or verify manually:

```powershell
.\tools\zlmediakit\MediaServer.exe -h
```
