from leon_control_plane.agent_assignment import build_agent_assignment_proposal, infer_task_type


def _task(title: str) -> dict:
    return {
        "id": "task-shopper",
        "title": title,
        "goal": "Vind beste prijs en lever shortlist.",
        "owner": "Leon",
        "acceptance_criteria": "Bron, prijs en tijdstip zichtbaar.",
        "priority": "P1",
        "risk_level": "medium",
        "status": "planned",
        "source_refs": [],
    }


def test_marketplace_task_routes_to_shopper_without_external_execution():
    task = _task("Vergelijk Vinted en Marktplaats deals")
    assert infer_task_type(task) == "shopping_research"
    proposal = build_agent_assignment_proposal(task=task)
    assert proposal["agent_role"] == "Shopper"
    assert proposal["task_packet"]["role"] == "Shopper"
    assert proposal["model_route"]["route"] == "balanced"
    assert proposal["external_calls_allowed"] is False
    assert "spend_money" in proposal["forbidden_actions"]


def test_specialized_tasks_route_to_requested_gaia_agents():
    cases = {
        "Analyseer Rabobank transacties": ("financial_analysis", "Manager"),
        "Controleer server containers en errors": ("server_operations", "Server Manager"),
        "Maak 3D model reference uit foto's": ("model_reference", "3D Model Reference Maker"),
        "Controleer 3D printer via Moonraker": ("printer_monitoring", "3D Printer Manager"),
    }
    for title, (task_type, role) in cases.items():
        proposal = build_agent_assignment_proposal(task=_task(title))
        assert proposal["task_type"] == task_type
        assert proposal["agent_role"] == role
        assert proposal["task_packet"]["role"] == role


def test_investigate_does_not_trigger_financial_manager():
    assert infer_task_type(_task("Investigate server logs")) == "server_operations"
