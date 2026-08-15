"""Chart type definitions for HistoryView custom charts."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

CUSTOM_PREFIX = "custom:"
ENGINES = frozenset({"options_merge", "js"})
BUILTIN_PRESETS = frozenset(
    {
        "media",
        "line",
        "column",
        "spline",
        "area",
        "step",
        "timeline",
        "scatter",
        "pie",
    }
)

_IMAGE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|gif|webp|bmp|svg|avif)(\?.*)?$", re.IGNORECASE)


def list_chart_types(config: dict) -> List[dict]:
    return list(config.get("chart_types") or [])


def get_chart_type(config: dict, type_id: str) -> Optional[dict]:
    if not type_id:
        return None
    for item in list_chart_types(config):
        if str(item.get("id")) == str(type_id):
            return item
    return None


def parse_chart_selection(
    value: Optional[str],
    custom_chart_type_id: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Split UI/storage chart selection into (builtin_chart_type, custom_id).

    Accepts:
    - ``custom:<id>`` (unified select value)
    - separate ``custom_chart_type_id`` (legacy widget storage)
    - plain builtin id (``line``, ``step``, ...)
    """
    raw = str(value or "").strip()
    legacy_custom = str(custom_chart_type_id or "").strip() or None

    if raw.startswith(CUSTOM_PREFIX):
        custom_id = raw[len(CUSTOM_PREFIX) :].strip() or None
        return "line", custom_id

    if legacy_custom:
        return (raw or "line"), legacy_custom

    return (raw or "line"), None


def format_chart_selection(
    chart_type: Optional[str] = None,
    custom_chart_type_id: Optional[str] = None,
) -> str:
    """Build unified select value for UI."""
    custom_id = str(custom_chart_type_id or "").strip()
    if custom_id:
        return f"{CUSTOM_PREFIX}{custom_id}"
    return str(chart_type or "line").strip() or "line"


def normalize_chart_type(payload: dict, type_id: Optional[str] = None) -> dict:
    data = dict(payload or {})
    engine = str(data.get("engine") or "js").strip().lower()
    if engine == "preset":
        raise ValueError("engine=preset is no longer supported; use js or options_merge")
    if engine not in ENGINES:
        raise ValueError(f"Unsupported engine: {engine}")

    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Chart type name is required")

    options = data.get("options")
    if options in (None, ""):
        options = {}
    if isinstance(options, str):
        try:
            options = json.loads(options) if options.strip() else {}
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid options JSON: {exc}") from exc
    if not isinstance(options, dict):
        raise ValueError("options must be a JSON object")

    transform_js = data.get("transform_js")
    if transform_js in (None, ""):
        transform_js = None
    else:
        transform_js = str(transform_js)

    if engine == "js" and not transform_js:
        raise ValueError("transform_js is required for engine=js")
    if engine == "options_merge" and not options:
        raise ValueError("options are required for engine=options_merge")

    return {
        "id": str(type_id or data.get("id") or uuid.uuid4()),
        "name": name,
        "engine": engine,
        "options": options,
        "transform_js": transform_js,
        "schema_version": int(data.get("schema_version") or 1),
    }


def upsert_chart_type(config: dict, payload: dict, type_id: Optional[str] = None) -> dict:
    normalized = normalize_chart_type(payload, type_id=type_id)
    items = list_chart_types(config)
    replaced = False
    for idx, item in enumerate(items):
        if str(item.get("id")) == str(normalized["id"]):
            items[idx] = normalized
            replaced = True
            break
    if not replaced:
        items.append(normalized)
    config["chart_types"] = items
    return normalized


def delete_chart_type(config: dict, type_id: str) -> bool:
    """Remove chart type and unlink widgets that referenced it."""
    if not type_id:
        return False
    items = list_chart_types(config)
    filtered = [item for item in items if str(item.get("id")) != str(type_id)]
    if len(filtered) == len(items):
        return False
    config["chart_types"] = filtered
    for widget in config.get("widgets") or []:
        if str(widget.get("custom_chart_type_id") or "") == str(type_id):
            widget.pop("custom_chart_type_id", None)
    return True


def is_image_url(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    if not _IMAGE_URL_RE.match(text):
        return False
    return bool(_IMAGE_EXT_RE.search(text)) or "/image" in text.lower() or "snapshot" in text.lower()


def suggest_media_preset(entries: List[dict]) -> bool:
    if not entries:
        return False
    values = []
    for entry in entries:
        raw = entry.get("value")
        if raw is None:
            raw = entry.get("display_value")
        if raw is not None:
            values.append(raw)
    if not values:
        return False
    image_like = sum(1 for value in values if is_image_url(value))
    return image_like >= max(1, len(values) * 0.5)


def resolve_chart_definition(
    config: dict,
    custom_chart_type_id: Optional[str] = None,
    chart_type: str = "line",
) -> dict:
    builtin, custom_id = parse_chart_selection(chart_type, custom_chart_type_id)
    if custom_id:
        custom = get_chart_type(config, custom_id)
        if custom:
            return {
                "source": "custom",
                "id": custom.get("id"),
                "name": custom.get("name"),
                "engine": custom.get("engine") or "js",
                "options": custom.get("options") or {},
                "transform_js": custom.get("transform_js"),
                "schema_version": custom.get("schema_version") or 1,
            }
    return {
        "source": "builtin",
        "id": None,
        "name": builtin,
        "engine": "builtin",
        "preset": builtin,
        "options": {},
        "transform_js": None,
        "schema_version": 1,
        "chart_type": builtin,
    }


def list_builtin_presets() -> List[dict]:
    return [
        {"id": "media", "title": "Media (image URL timeline)", "engine": "builtin"},
        {"id": "line", "title": "Line", "engine": "builtin"},
        {"id": "step", "title": "Step", "engine": "builtin"},
        {"id": "timeline", "title": "Event Timeline", "engine": "builtin"},
        {"id": "column", "title": "Column", "engine": "builtin"},
        {"id": "spline", "title": "Spline", "engine": "builtin"},
        {"id": "area", "title": "Area", "engine": "builtin"},
        {"id": "scatter", "title": "Scatter", "engine": "builtin"},
        {"id": "pie", "title": "Pie", "engine": "builtin"},
    ]


def chart_type_public_dict(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "engine": item.get("engine"),
        "options": item.get("options") or {},
        "has_transform_js": bool((item.get("transform_js") or "").strip()),
        "schema_version": item.get("schema_version") or 1,
    }


def chart_type_name_map(config: dict) -> Dict[str, str]:
    return {
        str(item.get("id")): str(item.get("name") or item.get("id"))
        for item in list_chart_types(config)
        if item.get("id")
    }
