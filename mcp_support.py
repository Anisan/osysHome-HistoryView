"""MCP integration for HistoryView plugin."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.core.lib.mcp_contract import (
    build_plugin_mcp_descriptors,
    revision_from_dict,
    validate_entity_payload,
)

from plugins.HistoryView.services import chart_types as chart_types_service

CHART_TYPES = "chart_types"
WIDGETS = "widgets"


def _collection_meta(collection: str) -> dict:
    for item in mcp_capabilities()["collections"]:
        if item["id"] == collection:
            return item
    raise ValueError(f"Unsupported collection: {collection}")


def _save_config(plugin, key: str, items: List[dict]) -> None:
    plugin.config[key] = items
    plugin.saveConfig()


def _widget_public(widget: dict) -> dict:
    return {
        "id": widget.get("id"),
        "name": widget.get("name"),
        "period": widget.get("period"),
        "properties": widget.get("properties") or [],
        "chart_type": widget.get("chart_type", "line"),
        "custom_chart_type_id": widget.get("custom_chart_type_id"),
        "chart_palette": widget.get("chart_palette", "classic"),
        "chart_bucket": widget.get("chart_bucket", "auto"),
        "show_legend": widget.get("show_legend", True),
        "show_navigator": widget.get("show_navigator", True),
        "show_range_selector": widget.get("show_range_selector", True),
        "show_context_menu": widget.get("show_context_menu", False),
        "use_color_theme": widget.get("use_color_theme", True),
    }


def mcp_capabilities() -> dict:
    return {
        "mcp_version": 1,
        "entities": True,
        "config_schema": True,
        "collections": [
            {
                "id": CHART_TYPES,
                "title": "HistoryView Chart Types",
                "binding_mode": "none",
                "writable": True,
                "has_code": True,
                "list_filters": ["query"],
                "default_sort": "name asc",
            },
            {
                "id": WIDGETS,
                "title": "HistoryView Widgets",
                "binding_mode": "none",
                "writable": True,
                "has_code": False,
                "list_filters": ["query"],
                "default_sort": "name asc",
            },
        ],
        "operations": [
            "history_data",
            "list_presets",
            "resolve_chart",
        ],
        "operation_schemas": {
            "history_data": {
                "description": "Build history payload for Object.property (same as /HistoryView/api/history_data)",
                "params": {
                    "type": "object",
                    "properties": {
                        "object": {"type": "string"},
                        "property": {"type": "string"},
                        "dt_begin": {"type": "string"},
                        "dt_end": {"type": "string"},
                        "period": {"type": "string"},
                        "bucket": {"type": "string", "default": "auto"},
                        "include_compare": {"type": "boolean", "default": True},
                    },
                    "required": ["object", "property"],
                },
            },
            "list_presets": {
                "description": "List built-in chart presets and custom chart types",
                "params": {"type": "object", "properties": {}},
            },
            "resolve_chart": {
                "description": "Resolve chart definition for widget or property page",
                "params": {
                    "type": "object",
                    "properties": {
                        "widget_id": {"type": "string"},
                        "custom_chart_type_id": {"type": "string"},
                        "chart_type": {"type": "string", "default": "line"},
                    },
                },
            },
        },
        "notes": [
            "chart_types may include transform_js executed in admin browser only.",
            "widgets.custom_chart_type_id overrides chart_type when set.",
            "Use history_data before authoring custom chart transforms.",
        ],
    }


def mcp_config_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "level_logging": {"type": "string"},
            "chart_types": {
                "type": "array",
                "items": {"$ref": "#/definitions/chart_type"},
            },
            "widgets": {
                "type": "array",
                "items": {"$ref": "#/definitions/widget"},
            },
        },
        "definitions": {
            "chart_type": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "engine": {"type": "string", "enum": ["options_merge", "js"]},
                    "options": {"type": "object"},
                    "transform_js": {"type": "string", "x-code-language": "javascript"},
                    "schema_version": {"type": "integer"},
                },
                "required": ["id", "name", "engine"],
            },
            "widget": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "period": {"type": "integer"},
                    "properties": {"type": "array"},
                    "chart_type": {"type": "string"},
                    "custom_chart_type_id": {"type": "string"},
                },
                "required": ["id", "name"],
            },
        },
    }


def mcp_entity_schema(collection: str) -> dict:
    _collection_meta(collection)
    if collection == CHART_TYPES:
        return {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "UUID; generated on create if omitted"},
                "name": {"type": "string"},
                "engine": {"type": "string", "enum": ["options_merge", "js"]},
                "options": {"type": "object", "description": "Highcharts options JSON merge"},
                "transform_js": {
                    "type": "string",
                    "description": "function(ctx) returning Highcharts options",
                    "x-code-language": "javascript",
                },
                "schema_version": {"type": "integer", "default": 1},
            },
            "required": ["name", "engine"],
        }
    if collection == WIDGETS:
        return {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "period": {"type": "integer"},
                "properties": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "chart_type": {"type": "string"},
                                    "color": {"type": "string"},
                                },
                            },
                        ]
                    },
                },
                "chart_type": {"type": "string", "default": "line"},
                "custom_chart_type_id": {"type": "string"},
                "chart_palette": {"type": "string", "default": "classic"},
                "chart_bucket": {"type": "string", "default": "auto"},
                "show_legend": {"type": "boolean", "default": True},
                "show_navigator": {"type": "boolean", "default": True},
                "show_range_selector": {"type": "boolean", "default": True},
                "show_context_menu": {"type": "boolean", "default": False},
                "use_color_theme": {"type": "boolean", "default": True},
            },
            "required": ["name"],
        }
    raise ValueError(f"Unsupported collection: {collection}")


def _filter_items(items: List[dict], query: Optional[str]) -> List[dict]:
    if not query:
        return items
    needle = query.lower()
    return [item for item in items if needle in json.dumps(item, ensure_ascii=False).lower()]


def mcp_list_entities(plugin, collection: str, query: str = None, limit: int = 100) -> List[dict]:
    _collection_meta(collection)
    if collection == CHART_TYPES:
        items = [chart_types_service.chart_type_public_dict(item) for item in chart_types_service.list_chart_types(plugin.config)]
    elif collection == WIDGETS:
        items = [_widget_public(item) for item in plugin.config.get("widgets", [])]
    else:
        raise ValueError(f"Unsupported collection: {collection}")
    return _filter_items(items, query)[: max(1, int(limit or 100))]


def mcp_get_entity(plugin, collection: str, entity_id) -> dict:
    _collection_meta(collection)
    if collection == CHART_TYPES:
        item = chart_types_service.get_chart_type(plugin.config, entity_id)
        if not item:
            raise ValueError(f"Chart type not found: {entity_id}")
        return item
    if collection == WIDGETS:
        for widget in plugin.config.get("widgets", []):
            if str(widget.get("id")) == str(entity_id):
                return _widget_public(widget)
        raise ValueError(f"Widget not found: {entity_id}")
    raise ValueError(f"Unsupported collection: {collection}")


def mcp_upsert_entity(plugin, collection: str, payload: dict, entity_id=None) -> dict:
    meta = _collection_meta(collection)
    if not meta.get("writable"):
        raise ValueError(f"Collection '{collection}' is read-only")

    if collection == CHART_TYPES:
        normalized = chart_types_service.upsert_chart_type(plugin.config, payload, type_id=entity_id)
        plugin.saveConfig()
        return normalized

    if collection == WIDGETS:
        data = dict(payload or {})
        widget_id = str(entity_id or data.get("id") or "")
        if not widget_id:
            import uuid
            widget_id = str(uuid.uuid4())
        chart_type, custom_chart_type_id = chart_types_service.parse_chart_selection(
            data.get("chart_type"),
            data.get("custom_chart_type_id"),
        )
        widget = {
            "id": widget_id,
            "name": str(data.get("name") or "").strip(),
            "period": int(data.get("period") or 24),
            "properties": data.get("properties") or [],
            "chart_type": chart_type or "line",
            "custom_chart_type_id": custom_chart_type_id,
            "chart_palette": data.get("chart_palette") or "classic",
            "chart_bucket": data.get("chart_bucket") or "auto",
            "show_legend": data.get("show_legend", True),
            "show_navigator": data.get("show_navigator", True),
            "show_range_selector": data.get("show_range_selector", True),
            "show_context_menu": data.get("show_context_menu", False),
            "use_color_theme": data.get("use_color_theme", True),
        }
        if not widget["name"]:
            raise ValueError("Widget name is required")
        items = list(plugin.config.get("widgets", []))
        replaced = False
        for idx, item in enumerate(items):
            if str(item.get("id")) == widget_id:
                items[idx] = widget
                replaced = True
                break
        if not replaced:
            items.append(widget)
        _save_config(plugin, "widgets", items)
        return _widget_public(widget)

    raise ValueError(f"Unsupported collection: {collection}")


def mcp_delete_entity(plugin, collection: str, entity_id) -> bool:
    meta = _collection_meta(collection)
    if not meta.get("writable"):
        raise ValueError(f"Collection '{collection}' is read-only")

    if collection == CHART_TYPES:
        deleted = chart_types_service.delete_chart_type(plugin.config, entity_id)
        if deleted:
            plugin.saveConfig()
        return deleted

    if collection == WIDGETS:
        items = [item for item in plugin.config.get("widgets", []) if str(item.get("id")) != str(entity_id)]
        _save_config(plugin, "widgets", items)
        return True

    raise ValueError(f"Unsupported collection: {collection}")


def mcp_validate_entity_code(collection: str, code: str) -> dict:
    if collection != CHART_TYPES:
        raise ValueError(f"Collection '{collection}' does not support code validation")
    text = str(code or "").strip()
    if not text:
        return {"valid": False, "message": "transform_js is empty"}
    return {"valid": True, "message": "Syntax check is client-side only for JavaScript"}


def mcp_run_entity_dry(collection: str, code: str, context: dict = None) -> dict:
    if collection != CHART_TYPES:
        raise ValueError(f"Collection '{collection}' does not support dry-run code")
    return {
        "valid": bool(str(code or "").strip()),
        "message": "Dry-run executes in browser; pass sample ctx via resolve_chart/history_data",
        "context_keys": list((context or {}).keys()),
    }


def mcp_invoke(plugin, operation: str, params: dict = None) -> dict:
    params = params or {}
    if operation == "history_data":
        object_name = str(params.get("object") or "").strip()
        property_name = str(params.get("property") or "").strip()
        if not object_name or not property_name:
            raise ValueError("object and property are required")
        dt_begin, dt_end = plugin._resolve_range(
            params.get("dt_begin"),
            params.get("dt_end"),
            params.get("period"),
        )
        bucket = str(params.get("bucket") or "auto")
        include_compare = params.get("include_compare", True)
        if isinstance(include_compare, str):
            include_compare = include_compare.lower() != "false"
        payload = plugin._build_property_payload(
            object_name,
            property_name,
            dt_begin,
            dt_end,
            bucket=bucket,
            include_compare=bool(include_compare),
        )
        return {"payload": payload}

    if operation == "list_presets":
        return {
            "builtin": chart_types_service.list_builtin_presets(),
            "custom": [
                chart_types_service.chart_type_public_dict(item)
                for item in chart_types_service.list_chart_types(plugin.config)
            ],
        }

    if operation == "resolve_chart":
        widget_id = params.get("widget_id")
        custom_chart_type_id = params.get("custom_chart_type_id")
        chart_type = params.get("chart_type") or "line"
        if widget_id:
            widget = next(
                (item for item in plugin.config.get("widgets", []) if str(item.get("id")) == str(widget_id)),
                None,
            )
            if not widget:
                raise ValueError(f"Widget not found: {widget_id}")
            custom_chart_type_id = widget.get("custom_chart_type_id")
            chart_type = widget.get("chart_type") or chart_type
        definition = chart_types_service.resolve_chart_definition(
            plugin.config,
            custom_chart_type_id=custom_chart_type_id,
            chart_type=chart_type,
        )
        return {"definition": definition}

    raise ValueError(f"Unsupported operation: {operation}")


def mcp_entity_revision(plugin, collection: str, entity_id) -> str:
    entity = mcp_get_entity(plugin, collection, entity_id)
    return revision_from_dict(entity)


def mcp_validate_entity(collection: str, payload: dict, entity_id=None) -> dict:
    schema = mcp_entity_schema(collection)
    return validate_entity_payload(payload, schema)


def mcp_resources() -> list:
    return mcp_descriptors()[1]


def mcp_descriptors():
    return build_plugin_mcp_descriptors("HistoryView", mcp_capabilities())
