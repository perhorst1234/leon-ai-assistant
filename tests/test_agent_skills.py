import json
from pathlib import Path

import pytest

from leon_control_plane.agent_skills import load_agent_skills, select_agent_skill
from leon_control_plane.agent_run_model import normalize_agent_run_role


ROOT = Path(__file__).resolve().parents[1]


def test_committed_agent_skills_are_valid_and_cover_core_roles():
    skills = load_agent_skills(ROOT / "config" / "agent-skills.json")
    assert {item["role"] for item in skills} >= {
        "Planner", "Research", "Manager", "Shopper", "Server Manager",
        "3D Model Reference Maker", "3D Printer Manager", "Code/Improvement",
        "Review", "Memory", "Tool/Connector",
    }
    research = select_agent_skill(skills, role="Research", task_type="routine_research")
    assert research["id"] == "research"
    assert "read_approved_sources" in research["allowed_actions"]
    shopper = select_agent_skill(skills, role="Shopper", task_type="shopping_research")
    assert shopper["id"] == "shopping-research"
    assert shopper["allowed_actions"] == (
        "read_task_context",
        "read_approved_marketplace_listings",
        "produce_reviewable_comparison",
    )


def test_agent_skill_loader_rejects_ambiguous_and_unknown_entries(tmp_path):
    path = tmp_path / "skills.json"
    entry = {
        "id": "research",
        "role": "Research",
        "task_types": ["routine_research"],
        "instructions": "Use reviewed sources.",
        "allowed_actions": ["read_approved_sources"],
        "output_kind": "research",
    }
    path.write_text(json.dumps({"version": 1, "skills": [entry, entry]}))
    with pytest.raises(ValueError, match="invalid"):
        load_agent_skills(path)
    path.write_text(json.dumps({"version": 1, "skills": [{**entry, "unexpected": True}]}))
    with pytest.raises(ValueError, match="schema"):
        load_agent_skills(path)


@pytest.mark.parametrize("alias", ["shopper", "shopper agent", "shopping agent", "marketplace agent"])
def test_shopper_role_aliases(alias):
    assert normalize_agent_run_role(alias) == "Shopper"


def test_shopper_role_aliases_do_not_match_untrusted_free_text():
    assert normalize_agent_run_role("not a shopper") == "Code/Improvement"
    assert normalize_agent_run_role("untrusted shopper-like text") == "Code/Improvement"
