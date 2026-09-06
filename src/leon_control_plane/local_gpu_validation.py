from __future__ import annotations

from typing import Any


REQUIRED_LOCAL_GPU_VALIDATION_CHECKS = [
    {
        "id": "hardware_detection",
        "title": "Hardware detection",
        "pass_statuses": {"passed"},
        "required_evidence": ["gpu_detected", "device_name", "vram_mb"],
    },
    {
        "id": "driver_cuda_readiness",
        "title": "Driver or CUDA readiness",
        "pass_statuses": {"passed"},
        "required_evidence": ["driver_version", "cuda_available", "backend_healthcheck"],
    },
    {
        "id": "benchmark_results",
        "title": "Benchmark results",
        "pass_statuses": {"passed"},
        "required_evidence": ["tokens_per_second", "latency_ms", "test_model"],
    },
    {
        "id": "quality_comparison",
        "title": "Quality comparison",
        "pass_statuses": {"passed"},
        "required_evidence": ["eval_set", "cloud_baseline_model", "quality_delta"],
    },
    {
        "id": "cost_comparison",
        "title": "Cost comparison",
        "pass_statuses": {"passed"},
        "required_evidence": ["provider_cost_baseline", "local_resource_cost", "worth_routing"],
    },
]


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_check(check_id: str, configured: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    evidence = _as_mapping(configured.get("evidence"))
    status = str(configured.get("status") or "not_run").strip().lower()
    summary = str(configured.get("summary") or "Validation check has not been run.")
    required_evidence = list(metadata.get("required_evidence") or [])
    missing_evidence = []
    for key in required_evidence:
        value = evidence.get(key)
        if value is None or value == "" or value is False or value == []:
            missing_evidence.append(key)
    passed = status in set(metadata.get("pass_statuses") or {"passed"}) and not missing_evidence
    if status == "passed" and missing_evidence:
        status = "incomplete"
        summary = f"Marked passed but missing required evidence: {', '.join(missing_evidence)}."
    return {
        "id": check_id,
        "title": str(metadata["title"]),
        "required": True,
        "status": status,
        "passed": passed,
        "summary": summary,
        "evidence": evidence,
        "required_evidence": required_evidence,
        "missing_evidence": missing_evidence,
        "last_run_at": configured.get("last_run_at"),
        "source_ref": str(configured.get("source_ref") or ""),
    }


def normalize_local_gpu_policy(local_gpu_policy: dict[str, Any] | None) -> dict[str, Any]:
    """Return a routing-safe local GPU policy with explicit validation gates."""

    policy = _as_mapping(local_gpu_policy)
    configured_validation = _as_mapping(policy.get("validation"))
    configured_checks = _as_mapping(configured_validation.get("checks") or policy.get("validation_checks"))
    checks = [
        _normalize_check(
            str(metadata["id"]),
            _as_mapping(configured_checks.get(str(metadata["id"]))),
            metadata,
        )
        for metadata in REQUIRED_LOCAL_GPU_VALIDATION_CHECKS
    ]
    failed_or_missing = [
        check["id"]
        for check in checks
        if not check["passed"]
    ]
    enabled = bool(policy.get("enabled", False))
    selected_backend = str(policy.get("selected_backend") or "").strip()
    selected_model = str(policy.get("selected_model") or "").strip()
    validation_passed = not failed_or_missing
    route_allowed = enabled and validation_passed and bool(selected_backend) and bool(selected_model)

    reasons: list[str] = []
    if not enabled:
        reasons.append("Local GPU routing is disabled by default.")
    if failed_or_missing:
        reasons.append(f"Validation checks not passed: {', '.join(failed_or_missing)}.")
    if not selected_backend:
        reasons.append("No local GPU backend selected.")
    if not selected_model:
        reasons.append("No local GPU model selected.")
    if not reasons:
        reasons.append("Local GPU validation passed and routing may consider local models for eligible work.")

    validation_status = "passed" if validation_passed else "not_validated"
    if enabled and not validation_passed and any(check["status"] not in {"not_run", ""} for check in checks):
        validation_status = "incomplete"
    if route_allowed:
        validation_status = "validated"

    normalized_validation = {
        "schema_version": 1,
        "status": validation_status,
        "route_allowed": route_allowed,
        "checks": checks,
        "required_check_ids": [str(item["id"]) for item in REQUIRED_LOCAL_GPU_VALIDATION_CHECKS],
        "routing_gate": {
            "can_consider_local_gpu": route_allowed,
            "disabled_by_default": not enabled,
            "reasons": reasons,
        },
    }

    return {
        **policy,
        "enabled": enabled,
        "readiness_status": validation_status,
        "selected_backend": selected_backend,
        "selected_model": selected_model,
        "validation": normalized_validation,
        "route_allowed": route_allowed,
    }


def local_gpu_route_allowed(local_gpu_policy: dict[str, Any] | None) -> bool:
    return bool(normalize_local_gpu_policy(local_gpu_policy).get("route_allowed"))
