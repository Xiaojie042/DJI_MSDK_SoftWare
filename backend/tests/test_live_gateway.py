"""Tests for live gateway configuration and GB28181 orchestration guards."""

import asyncio
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - direct-script fallback
    from tests import _pytest_compat as pytest

from app.services.live_gateway import LiveGatewayError, LiveGatewayService, _is_error_line


def test_live_gateway_persists_config_and_builds_rtmp_urls():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = LiveGatewayService(
                config_path=root / "live_config.json",
                log_path=root / "live.log",
            )

            await service.initialize()
            result = await service.update_config(
                {
                    "rtmp": {
                        "port": 1940,
                        "app": "aircraft",
                        "stream": "m400",
                    },
                    "gb28181": {
                        "sip_server_ip": "192.168.1.10",
                        "sip_domain": "3402000000",
                        "device_id": "34020000001320000001",
                        "channel_id": "34020000001320000002",
                    },
                }
            )

            assert result.rtmp.port == 1940
            assert result.rtmp_push_url.endswith(":1940/aircraft/m400")
            assert result.gb28181.rtmp_input_url == "rtmp://127.0.0.1:1940/aircraft/m400"

            saved = json.loads((root / "live_config.json").read_text(encoding="utf-8"))
            assert saved["rtmp"]["app"] == "aircraft"
            assert saved["gb28181"]["channel_id"] == "34020000001320000002"

    asyncio.run(scenario())


def test_gb28181_start_requires_external_device_bridge():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = LiveGatewayService(
                config_path=root / "live_config.json",
                log_path=root / "live.log",
            )
            await service.initialize()
            await service.update_config(
                {
                    "gb28181": {
                        "sip_server_ip": "192.168.1.10",
                        "sip_domain": "3402000000",
                        "device_id": "34020000001320000001",
                        "channel_id": "34020000001320000002",
                    }
                }
            )
            service._resolve_gb_bridge_executable = lambda config: ""

            with pytest.raises(LiveGatewayError) as exc_info:
                await service.start_gb28181()

            message = str(exc_info.value)
            assert "GB28181 device bridge is not configured" in message
            assert "not a complete GB28181" in message

    asyncio.run(scenario())


def test_gb28181_bridge_command_template_is_rendered_without_starting_process():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = LiveGatewayService(
                config_path=root / "live_config.json",
                log_path=root / "live.log",
            )
            await service.initialize()
            await service.update_config(
                {
                    "gb28181": {
                        "sip_server_ip": "192.168.1.10",
                        "sip_server_port": 15060,
                        "sip_domain": "3402000000",
                        "device_id": "34020000001320000001",
                        "channel_id": "34020000001320000002",
                        "ssrc": "1234567890",
                        "bridge_config_path": str(root / "gb28181_bridge_config.json"),
                        "bridge_command_template": "bridge.exe --config {config_path} --server {sip_server_ip}:{sip_server_port} --ssrc {ssrc}",
                    }
                }
            )

            config = service.get_config()
            config_path = service._write_gb_bridge_config(config)
            command = service._build_gb_bridge_command(config.gb28181, config_path)

            assert isinstance(command, str)
            assert "--server 192.168.1.10:15060" in command
            assert "--ssrc 1234567890" in command
            assert config_path in command

    asyncio.run(scenario())


def test_happytime_bridge_xml_is_detected_and_written_without_cli_config():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bridge_dir = root / "happytime"
            bridge_dir.mkdir()
            executable = bridge_dir / "GB28181Device.exe"
            executable.touch()
            xml_path = bridge_dir / "gb28181device.cfg"
            xml_path.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<config>
    <server_ip>192.168.1.20</server_ip>
    <server_port>15060</server_port>
    <server_id>34020000002000000001</server_id>
    <server_domain>3402000000</server_domain>
    <local_port>0</local_port>
    <device_id>34020000001110000001</device_id>
    <password>12345678</password>
    <protocol>tcp</protocol>
    <heartbeat_interval>30</heartbeat_interval>
    <media_base_port>19000</media_base_port>
    <channel>
        <cid>34020000001310000001</cid>
        <media_url>rtmp://127.0.0.1/live/drone</media_url>
    </channel>
</config>
""",
                encoding="utf-8",
            )
            service = LiveGatewayService(
                config_path=root / "live_config.json",
                log_path=root / "live.log",
            )
            await service.initialize()
            await service.update_config(
                {
                    "gb28181": {
                        "bridge_executable_path": str(executable),
                        "channel_id": "34020000001320000670",
                    }
                }
            )

            config = service._apply_gb_bridge_defaults(service.get_config())
            assert config.gb28181.sip_server_ip == "192.168.1.20"
            assert config.gb28181.sip_server_port == 15060
            assert config.gb28181.sip_domain == "3402000000"
            assert config.gb28181.device_id == "34020000001110000001"
            assert config.gb28181.transport == "TCP"
            assert config.gb28181.local_sip_port == 0
            assert config.gb28181.local_rtp_port_start == 19000
            assert config.gb28181.heartbeat_interval == 30

            written_path = service._write_gb_bridge_config(config)
            command = service._build_gb_bridge_command(config.gb28181, written_path)
            root_xml = ET.parse(xml_path).getroot()

            assert written_path == str(xml_path.resolve())
            assert command == [str(executable.resolve())]
            assert root_xml.findtext("server_ip") == "192.168.1.20"
            assert root_xml.findtext("server_port") == "15060"
            assert root_xml.findtext("local_port") == "0"
            assert root_xml.findtext("protocol") == "tcp"
            assert root_xml.findtext("media_protocol") == "tcp"
            assert root_xml.findtext("media_base_port") == "19000"
            assert root_xml.findtext("channel/cid") == "34020000001320000670"
            assert root_xml.findtext("channel/media_url") == "rtmp://127.0.0.1/live/drone"

    asyncio.run(scenario())


def test_gb28181_digest_401_challenge_is_not_a_registration_failure():
    async def scenario() -> None:
        service = LiveGatewayService(config_path=Path("unused.json"), log_path=Path("unused.log"))

        assert service._infer_registration_status(True, True, "REGISTER\nSIP/2.0 401 Unauthorized") == "registering"
        assert service._infer_registration_status(True, True, "REGISTER\nSIP/2.0 200 OK") == "registered"

    asyncio.run(scenario())


def test_gb28181_waits_for_rtmp_before_treating_play_logs_as_negotiation():
    async def scenario() -> None:
        service = LiveGatewayService(config_path=Path("unused.json"), log_path=Path("unused.log"))

        recent_text = "Invoking play\nNetStream.Play.StreamNotFound\nCRtmpClient::rtmp_connect failed"
        assert service._infer_streaming_status(True, True, False, recent_text) == "waiting_rtmp"
        assert service._infer_streaming_status(True, True, True, "INVITE received") == "negotiating"

    asyncio.run(scenario())


def test_benign_live_gateway_disconnect_warnings_are_not_errors():
    assert not _is_error_line(
        "SSLUtil.cpp:213 makeSSLContext | SSL_CTX_check_private_key failed: no such file or directory"
    )
    assert not _is_error_line(
        "HttpSession.cpp:176 onError | FLV/TS/FMP4播放器(__defaultVhost__/live/drone)断开:4(connection reset by peer)"
    )
    assert not _is_error_line(
        "RtmpSession.cpp:28 onError | RTMP推流器(__defaultVhost__/live/drone)断开:end of file"
    )
    assert not _is_error_line(
        "H264Rtmp.cpp:26 inputRtmp | Assertion failed: (pkt->size() > 9)"
    )


def test_gb28181_start_rejects_invalid_standard_ids():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = LiveGatewayService(
                config_path=root / "live_config.json",
                log_path=root / "live.log",
            )
            await service.initialize()
            await service.update_config(
                {
                    "gb28181": {
                        "sip_server_ip": "192.168.1.10",
                        "sip_domain": "3402000000",
                        "device_id": "3402000000111000671",
                        "channel_id": "3402000000111000671",
                        "bridge_command_template": "bridge.exe --config {config_path}",
                    }
                }
            )

            with pytest.raises(LiveGatewayError) as exc_info:
                await service.start_gb28181()

            message = str(exc_info.value)
            assert "device_id_must_be_20_digits" in message
            assert "channel_id_must_be_20_digits" in message

    asyncio.run(scenario())


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
