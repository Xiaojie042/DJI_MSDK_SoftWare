# GB28181 device-side bridge options

This note tracks components that may help a Windows PC actively register to an upstream GB28181 platform as a device, using local RTMP/RTSP input as the media source.

## Best fit for this project

### Happytime GB28181 Device

Website:

- https://www.happytimesoft.com/products/gb28181-device/index.html
- https://www.happytimesoft.com/howto/how-to-convert-rtsp-rtmp-to-ps.html

Why it fits:

- It is explicitly a GB28181 device-side component.
- It supports Windows.
- It has a built-in SIP stack for registration and signaling.
- It supports RTSP/RTMP/SRT input and converts streams to GB28181 PS.

Suggested local placement:

```text
tools/gb28181-bridge/gb28181-device.exe
```

If its executable name differs, configure `bridge_executable_path` or `bridge_command_template` from the frontend live forwarding panel.

### EasyGBD

Website:

- https://www.easydarwin.org/tools/169.html
- https://github.com/EasyDarwin/EasyGBD

Why it fits:

- It is described as a GB28181 device-side implementation.
- It supports Windows and other platforms.
- It supports RTSP/RTMP/SRT conversion to GB28181-compatible streams.
- It is positioned for IPC/device simulation and third-party platform integration.

Suggested local placement:

```text
tools/gb28181-bridge/easygbd.exe
```

## Heavier platform-level alternatives

These can be useful if the PC should become a small video platform/gateway rather than a lightweight device bridge.

### wvp-GB28181-pro

Website:

- https://github.com/648540858/wvp-GB28181-pro

Notes:

- Open-source Java platform based on GB28181-2016.
- Integrates with ZLMediaKit.
- Supports ordinary camera/live stream/live push forwarding to other GB28181 platforms.
- Heavier than a single bridge executable, but strong if web management and upstream platform cascading are desired.

### LiveGBS

Website:

- https://www.liveqing.com/docs/download/LiveGBS.html

Notes:

- Commercial/try-before-license GB28181 platform package.
- Supports Windows/Linux deployment, device/platform access, upstream GB28181 cascading, RTSP/RTMP output, and APIs.
- More suitable as a standalone GB28181 platform/gateway than as a tiny process under this FastAPI app.

### AKStream

Website:

- https://github.com/chatop2020/AKStream

Notes:

- Open-source C#/.NET streaming control platform integrating ZLMediaKit.
- Supports GB28181, RTSP, RTMP, HTTP and REST APIs.
- Useful when a larger NVR-style management layer is acceptable.

## Not sufficient alone

### ZLMediaKit

Website:

- https://docs.zlmediakit.com/guide/protocol/gb28181/push_streaming.html

Notes:

- Good for RTMP ingress and RTP/PS media handling.
- It is not, by itself, the full PC-as-GB28181-device bridge needed here unless paired with SIP registration/signaling logic.

### FFmpeg

Notes:

- Useful for testing RTMP input or transcoding.
- Not a GB28181 device-side implementation because it does not provide SIP REGISTER, heartbeat, INVITE, authentication, catalog, and GB28181 session negotiation.
