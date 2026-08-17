from __future__ import annotations

import json
from typing import Any

from app.core.config import BASE_DIR


def load_rubric(rubric_name: str | None = None) -> dict[str, Any]:
    resolved_rubric_name = rubric_name or "aiml_engineer"
    rubric_path = BASE_DIR / "static" / "rubrics" / f"{resolved_rubric_name}.json"
    with rubric_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, max_value: int) -> int:
    return min(value, max_value)


def _field_score_items(field: dict[str, Any], input_data: dict[str, Any]) -> list[dict[str, Any]]:
    if not field.get("scored"):
        return []

    field_type = field.get("type")
    field_id = field.get("id")
    field_label = field.get("label", field_id)

    if field_type == "rating":
        max_value = _coerce_int(field.get("max"), 5)
        value = _clamp(_coerce_int(input_data.get(field_id)), max_value)
        return [{
            "field_id": field_id,
            "field_label": field_label,
            "value": value,
            "max_value": max_value,
        }]

    if field_type == "rating_group":
        max_value = _coerce_int(field.get("max"), 5)
        subfields = field.get("subfields") or []
        if not subfields:
            return []
        items = []
        for subfield in subfields:
            sub_id = subfield.get("id")
            items.append({
                "field_id": sub_id,
                "field_label": subfield.get("label", sub_id),
                "value": _clamp(_coerce_int(input_data.get(sub_id)), max_value),
                "max_value": max_value,
            })
        return items

    if field_type == "slider":
        max_value = _coerce_int(field.get("max"), 10)
        return [{
            "field_id": field_id,
            "field_label": field_label,
            "value": _clamp(_coerce_int(input_data.get(field_id)), max_value),
            "max_value": max_value,
        }]

    if field_type == "number":
        cap = _coerce_int(field.get("cap"), 0)
        if cap <= 0:
            cap = _coerce_int(field.get("max_input"), 0)
        return [{
            "field_id": field_id,
            "field_label": field_label,
            "value": _clamp(_coerce_int(input_data.get(field_id)), cap),
            "max_value": cap,
        }]

    value = _coerce_int(input_data.get(field_id))
    max_value = _coerce_int(field.get("max"), value)
    return [{
        "field_id": field_id,
        "field_label": field_label,
        "value": _clamp(value, max_value),
        "max_value": max_value,
    }]


def _normalize_input_data(rubric: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(input_data)
    rubric_scores = normalized.get("rubric_scores")

    if isinstance(rubric_scores, list):
        scored_fields: list[dict[str, Any]] = []
        for section in rubric.get("sections", []):
            for field in section.get("fields", []):
                if field.get("scored"):
                    scored_fields.append(field)

        for field, value in zip(scored_fields, rubric_scores):
            field_id = field.get("id")
            if field_id and field_id not in normalized:
                normalized[field_id] = value

    return normalized


def evaluate_rubric(rubric: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
    normalized_input = _normalize_input_data(rubric, input_data)
    categories: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    total_raw = 0.0
    total_max = 0.0

    for section in rubric.get("sections", []):
        section_id = section.get("id", "")
        section_title = section.get("title", section_id)
        category_raw = 0.0
        category_max = 0.0

        for field in section.get("fields", []):
            for item in _field_score_items(field, normalized_input):
                fields.append({
                    "category_id": section_id,
                    "field_id": item["field_id"],
                    "field_label": item["field_label"],
                    "value": float(item["value"]),
                    "max_value": float(item["max_value"]),
                })
                category_raw += item["value"]
                category_max += item["max_value"]

        categories.append({
            "category_id": section_id,
            "category_title": section_title,
            "raw_score": float(category_raw),
            "max_score": float(category_max),
            "percentage": round((category_raw / category_max) * 100, 2) if category_max else 0.0,
        })
        total_raw += category_raw
        total_max += category_max

    return {
        "categories": categories,
        "fields": fields,
        "total_raw": float(total_raw),
        "total_max": float(total_max),
        "percentage": round((total_raw / total_max) * 100, 2) if total_max else 0.0,
    }


def build_score_breakdown(rubric_name: str | None = None, **kwargs) -> dict[str, Any]:
    rubric = load_rubric(rubric_name)
    return evaluate_rubric(rubric, kwargs)


def calculate_score(
    rubric_name: str | None = None,
    **kwargs,
) -> int:
    score_data = build_score_breakdown(rubric_name, **kwargs)
    return round(score_data["percentage"])


def calculate_final_score(
    avg_score: float,
    **kwargs,
) -> float:
    """
    Called by pipeline.advance() once all interviewers have scored.
    The averaging is already done by core.submit_score(); this just
    passes the value through so the orchestrator can apply the threshold.
    """
    return avg_score
