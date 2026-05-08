# GB28181 device bridge

Place the selected GB28181 device-side bridge executable here:

```text
tools/gb28181-bridge/gb28181-bridge.exe
```

The bridge must support PC-side active registration as a GB28181 device and must handle:

- SIP REGISTER and authentication
- heartbeat / keepalive
- INVITE / ACK signaling
- RTP/PS packaging
- SSRC
- UDP/TCP media transport
- local RTP port negotiation

If the bridge uses a different filename or command-line format, fill `bridge_executable_path` or `bridge_command_template` in the frontend live forwarding panel.

Candidate components are tracked in:

```text
docs/gb28181-device-bridge-options.md
```
