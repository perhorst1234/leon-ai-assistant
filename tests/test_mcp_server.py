import asyncio
from pathlib import Path

from mcp import Client, StdioServerParameters

from leon_control_plane.mcp_server import build_mcp_server
from leon_control_plane.store import ControlPlaneStore


ROOT = Path(__file__).resolve().parents[1]


def test_mcp_server_exposes_only_bounded_readonly_tools(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.sqlite", ROOT / "state" / "control-plane.seed.json")
    store.initialize()
    server = build_mcp_server(store.db_path, skills_path=ROOT / "config" / "agent-skills.json")

    async def exercise():
        async with Client(server) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {"leon_status", "list_tasks", "list_agent_skills"}
            assert all(tool.annotations and tool.annotations.read_only_hint for tool in tools.tools)
            status = await client.call_tool("leon_status")
            tasks = await client.call_tool("list_tasks", {"status": "open", "limit": 3})
            skills = await client.call_tool("list_agent_skills")
            return status.structured_content, tasks.structured_content, skills.structured_content

    status, tasks, skills = asyncio.run(exercise())
    assert 0 <= status["progress_percent"] <= 100
    assert tasks["count"] <= 3
    assert all(set(item) == {"id", "title", "status", "priority", "risk_level", "value_score", "owner", "blocked_reason"} for item in tasks["tasks"])
    assert skills["count"] >= 6


def test_mcp_stdio_entrypoint_negotiates_without_protocol_noise(tmp_path):
    db = tmp_path / "control-plane.sqlite"
    ControlPlaneStore(db, ROOT / "state" / "control-plane.seed.json").initialize()
    db.chmod(0o600)

    async def exercise():
        params = StdioServerParameters(
            command=str(ROOT / ".venv" / "bin" / "python"),
            args=[
                "-m", "leon_control_plane.mcp_server",
                "--db", str(db),
            ],
            cwd=ROOT,
        )
        async with Client(params, read_timeout_seconds=10) as client:
            tools = await client.list_tools()
            return {tool.name for tool in tools.tools}, client.server_info.name

    tools, name = asyncio.run(exercise())
    assert tools == {"leon_status", "list_tasks", "list_agent_skills"}
    assert name == "leon-readonly"


def test_mcp_task_strings_are_capped_and_database_is_not_mutated(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.sqlite", ROOT / "state" / "control-plane.seed.json")
    store.initialize()
    with store.connect() as connection:
        task_id = connection.execute("SELECT id FROM tasks LIMIT 1").fetchone()[0]
        connection.execute("UPDATE tasks SET blocked_reason = ? WHERE id = ?", ("x" * 5000, task_id))
        before = connection.total_changes
    server = build_mcp_server(store.db_path, skills_path=ROOT / "config" / "agent-skills.json")

    async def exercise():
        async with Client(server) as client:
            result = await client.call_tool("list_tasks", {"status": "open", "limit": 20})
            return result.structured_content

    result = asyncio.run(exercise())
    assert all(len(item["blocked_reason"]) <= 512 for item in result["tasks"])
    with store.connect() as connection:
        assert connection.total_changes == 0
