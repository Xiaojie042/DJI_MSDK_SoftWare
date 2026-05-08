# Third-party runtime tools

This directory stores local third-party executables used by the live forwarding feature.

Expected layout:

```text
tools/
  zlmediakit/
    MediaServer.exe
  gb28181-bridge/
    gb28181-bridge.exe
```

`MediaServer.exe` is the ZLMediaKit media server used for RTMP ingress.

`gb28181-bridge.exe` is a device-side GB28181 bridge selected for the deployment site. It must implement SIP registration, heartbeat, authentication, INVITE handling, RTP/PS sending, SSRC, and port negotiation. FFmpeg alone is not a complete GB28181 device bridge.

The backend also allows absolute paths to be entered from the live forwarding panel if the tools are installed elsewhere.
