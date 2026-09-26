import asyncio
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from leon_control_plane.marketplace_browser_mcp import BrowserBridge, build_server, validate_url


URL = "https://www.marktplaats.nl/messages/123"
SNAPSHOT = '- textbox "Typ een bericht" [ref=e1]\n- button "Versturen" [ref=e2]'


def bridge(tmp_path, *, allow=True, fail_click=False):
    result = BrowserBridge(Path("/unused"), "http://127.0.0.1:9222", tmp_path / "audit.jsonl", allow_messages=allow)
    calls = []
    def run(*args):
        calls.append(args)
        if args == ("get", "url"):
            return URL
        if args == ("snapshot",):
            return SNAPSHOT
        if args[0] == "click" and fail_click:
            raise RuntimeError("ambiguous")
        return ""
    result.run = run
    return result, calls


@pytest.mark.parametrize("url", [
    "https://evil.example/", "https://www.marktplaats.nl.evil.example/",
    "https://www.marktplaats.nl@evil.example/", "http://www.marktplaats.nl/",
    "https://www.marktplaats.nl:444/", "https://www.marktplaats.nl/checkout",
])
def test_url_boundary(url):
    with pytest.raises(ValueError):
        validate_url("marktplaats", url)


def test_protocol_hides_write_tool_without_authorization(tmp_path):
    instance, _ = bridge(tmp_path, allow=False)
    async def check():
        async with Client(build_server(instance)) as client:
            listed = await client.list_tools()
            status = await client.call_tool("marketplace_capabilities")
            return {item.name for item in listed.tools}, status.structured_content
    names, status = asyncio.run(check())
    assert names == {"marketplace_capabilities", "marketplace_open", "marketplace_read_page"}
    assert not status["messages_enabled"]


def test_send_claim_survives_restart_and_ambiguous_click(tmp_path):
    instance, calls = bridge(tmp_path, fail_click=True)
    result = instance.send("marktplaats", "@e1", "@e2", "Hoi, is dit beschikbaar?", URL)
    assert result["status"] == "unknown" and not result["retry_allowed"]
    assert sum(call[0] == "click" for call in calls) == 1
    restarted, _ = bridge(tmp_path)
    with pytest.raises(ValueError):
        restarted.send("marktplaats", "@e1", "@e2", "Hoi, is dit beschikbaar?", URL)
    audit = (tmp_path / "audit.jsonl").read_text()
    assert "unknown" in audit and "Hoi" not in audit and URL not in audit


@pytest.mark.parametrize("field_ref,button_ref,url", [
    ("@e1", "@e99", URL), ("@e1;evil", "@e2", URL),
    ("@e1", "@e2", "https://www.marktplaats.nl/messages/456"),
])
def test_ref_and_conversation_checks_prevent_click(tmp_path, field_ref, button_ref, url):
    instance, calls = bridge(tmp_path)
    with pytest.raises(ValueError):
        instance.send("marktplaats", field_ref, button_ref, "Hoi", url)
    assert not any(call[0] == "click" for call in calls)


def test_cdp_is_loopback_only(tmp_path):
    with pytest.raises(ValueError):
        BrowserBridge(Path("/unused"), "http://192.168.1.1:9222", tmp_path / "audit")


def test_stdio_entrypoint_exposes_authorized_tools_without_browser_login(tmp_path):
    root = Path(__file__).resolve().parents[1]
    async def check():
        params = StdioServerParameters(
            command=str(root / ".venv/bin/python"),
            args=["-m", "leon_control_plane.marketplace_browser_mcp", "--agent-browser", "/unused",
                  "--allow-messages", "--audit", str(tmp_path / "audit")],
            cwd=root,
        )
        async with Client(params, read_timeout_seconds=10) as client:
            tools = await client.list_tools()
            return {item.name: item.annotations.read_only_hint for item in tools.tools}
    tools = asyncio.run(check())
    assert "marketplace_send_message" in tools
    assert not tools["marketplace_send_message"]
    assert tools["marketplace_read_page"]
