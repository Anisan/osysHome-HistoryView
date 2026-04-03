import datetime
import json
import math
import uuid
from collections import Counter

from flask import jsonify, redirect, render_template, request as flask_request

from app.authentication.handlers import handle_admin_required
from app.core.lib.object import getHistory
from app.core.main.BasePlugin import BasePlugin
from app.core.main.ObjectsStorage import objects_storage
from app.core.models.Clasess import History, Object
from app.database import session_scope


class HistoryView(BasePlugin):

    def __init__(self, app):
        super().__init__(app, __name__)
        self.title = "History"
        self.description = """History viewer"""
        self.category = "System"
        self.version = "2.0"
        self.actions = ["widget", "page", "search"]

    def initialization(self):
        pass

    def route_history_api(self):
        @self.blueprint.route(f"/{self.name}/api/history_data", methods=["GET"])
        @handle_admin_required
        def history_api():
            object_name = flask_request.args.get("object", "").strip()
            property_name = flask_request.args.get("property", "").strip()
            bucket = flask_request.args.get("bucket", "auto").strip() or "auto"
            include_compare = flask_request.args.get("include_compare", "true").lower() != "false"
            if not object_name or not property_name:
                return jsonify({"success": False, "message": "Missing object or property"}), 400

            try:
                dt_begin, dt_end = self._resolve_range(
                    flask_request.args.get("dt_begin"),
                    flask_request.args.get("dt_end"),
                    flask_request.args.get("period"),
                )
                payload = self._build_property_payload(
                    object_name,
                    property_name,
                    dt_begin,
                    dt_end,
                    bucket=bucket,
                    include_compare=include_compare,
                )
                return jsonify({"success": True, "result": payload})
            except ValueError as exc:
                return jsonify({"success": False, "message": str(exc)}), 400
            except Exception as exc:
                self.logger.exception("History API failed for %s.%s: %s", object_name, property_name, exc)
                return jsonify({"success": False, "message": "Failed to build history data"}), 500

    def widgets(self):
        widgets_list = self.config.get("widgets", [])
        return [
            {
                "name": widget.get("id"),
                "description": widget.get("name", "Unnamed Widget"),
            }
            for widget in widgets_list
        ]

    def _resolve_range(self, dt_begin_str=None, dt_end_str=None, period=None):
        dt_end = self._parse_datetime(dt_end_str) or datetime.datetime.now()
        dt_begin = self._parse_datetime(dt_begin_str)
        if dt_begin is None and period not in (None, ""):
            try:
                period_value = int(period)
            except (TypeError, ValueError):
                period_value = None
            if period_value is not None and period_value > 0:
                dt_begin = dt_end - datetime.timedelta(hours=period_value)
        if dt_begin and dt_end and dt_begin > dt_end:
            raise ValueError("The start date must be earlier than the end date.")
        return dt_begin, dt_end

    def _parse_datetime(self, value):
        if not value:
            return None
        normalized = str(value).strip().replace("Z", "")
        if not normalized:
            return None
        return datetime.datetime.fromisoformat(normalized)

    def _parse_numeric(self, value):
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                return None
            return float(value)
        if value is None:
            return None
        try:
            text = str(value).strip()
            if text.lower() in {"true", "false"}:
                return 1.0 if text.lower() == "true" else 0.0
            parsed = float(text)
            if math.isfinite(parsed):
                return parsed
        except (TypeError, ValueError):
            return None
        return None

    def _display_value(self, value):
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, sort_keys=True)
            except TypeError:
                return str(value)
        if value is None:
            return "None"
        return str(value)

    def _format_duration(self, seconds):
        if seconds is None:
            return ""
        total_seconds = int(max(0, round(seconds)))
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs or not parts:
            parts.append(f"{secs}s")
        return " ".join(parts)

    def _serialize_dt(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = self._parse_datetime(value)
        return value.isoformat(timespec="seconds") if value else None

    def _get_property_manager(self, object_name, property_name):
        obj = objects_storage.getObjectByName(object_name)
        if not obj:
            raise ValueError(f"Object '{object_name}' not found.")
        if property_name not in obj.properties:
            raise ValueError(f"Property '{property_name}' not found.")
        return obj, obj.properties[property_name]

    def _get_property_label(self, object_name, property_name):
        obj = objects_storage.getObjectByName(object_name)
        if not obj:
            return f"{object_name}.{property_name}"
        object_desc = obj.description or object_name
        prop = obj.properties.get(property_name)
        prop_desc = prop.description if prop and prop.description else property_name
        return f"{object_desc} - {prop_desc}"

    def _history_rows(self, full_name, dt_begin, dt_end, limit=None, order_desc=False):
        rows = getHistory(full_name, dt_begin, dt_end, limit, order_desc, None) or []
        normalized = []
        for item in rows:
            added = item.get("added")
            if isinstance(added, str):
                added = self._parse_datetime(added.replace(" ", "T"))
            normalized.append(
                {
                    "id": item.get("id"),
                    "added": added,
                    "value": item.get("value"),
                    "source": item.get("source") or "Unknown",
                }
            )
        normalized.sort(key=lambda row: row["added"] or datetime.datetime.min)
        return normalized

    def _determine_mode(self, prop_type, chart_type, entries):
        if chart_type == "pie":
            return "distribution"
        is_boolean = str(prop_type).lower() == "bool"
        has_numeric = any(entry["numeric_value"] is not None for entry in entries)
        if is_boolean:
            return "boolean"
        if has_numeric:
            return "numeric"
        return "state"

    def _choose_bucket(self, bucket, dt_begin, dt_end, count):
        if bucket and bucket != "auto":
            return bucket
        if count <= 500:
            return "raw"
        if not dt_begin or not dt_end:
            return "1h"
        span_seconds = max(1, (dt_end - dt_begin).total_seconds())
        target = span_seconds / 240
        if target <= 300:
            return "5m"
        if target <= 900:
            return "15m"
        if target <= 3600:
            return "1h"
        if target <= 21600:
            return "6h"
        return "1d"

    def _bucket_seconds(self, bucket):
        mapping = {
            "raw": None,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "6h": 21600,
            "1d": 86400,
        }
        return mapping.get(bucket, None)

    def _build_numeric_series(self, entries, dt_begin, dt_end, bucket):
        numeric_entries = [entry for entry in entries if entry["numeric_value"] is not None]
        if not numeric_entries:
            return {"series": [], "bucket": "raw"}

        resolved_bucket = self._choose_bucket(bucket, dt_begin, dt_end, len(numeric_entries))
        bucket_seconds = self._bucket_seconds(resolved_bucket)
        if bucket_seconds is None:
            return {
                "series": [[entry["timestamp"], entry["numeric_value"]] for entry in numeric_entries],
                "bucket": "raw",
            }

        grouped = {}
        for entry in numeric_entries:
            bucket_key = int(entry["timestamp"] / 1000 // bucket_seconds)
            grouped.setdefault(bucket_key, []).append(entry)

        points = []
        for bucket_key in sorted(grouped):
            group = grouped[bucket_key]
            ts = bucket_key * bucket_seconds * 1000
            avg_value = sum(item["numeric_value"] for item in group) / len(group)
            points.append([int(ts), round(avg_value, 4)])

        return {"series": points, "bucket": resolved_bucket}

    def _build_state_series(self, timeline_entries):
        if not timeline_entries:
            return {"series": [], "categories": []}

        categories = []
        category_index = {}
        series = []
        for entry in timeline_entries:
            state = entry["display_value"]
            if state not in category_index:
                category_index[state] = len(categories)
                categories.append(state)
            series.append([entry["timestamp"], category_index[state]])
        return {"series": series, "categories": categories}

    def _build_timeline_entries(self, full_name, rows, dt_begin, dt_end):
        timeline_entries = list(rows)
        if dt_begin:
            previous_rows = self._history_rows(full_name, None, dt_begin, limit=1, order_desc=True)
            if previous_rows:
                previous = previous_rows[0]
                previous_added = previous.get("added")
                if previous_added and previous_added < dt_begin:
                    timeline_entries.insert(
                        0,
                        {
                            "id": None,
                            "added": dt_begin,
                            "value": previous.get("value"),
                            "source": previous.get("source") or "Unknown",
                            "synthetic": True,
                        },
                    )
        result = [item for item in timeline_entries if item.get("added")]
        result.sort(key=lambda row: row["added"])
        if dt_end:
            result = [row for row in result if row["added"] <= dt_end]
        return result

    def _entries_with_context(self, rows, timeline_entries, dt_end):
        now_dt = datetime.datetime.now()
        timeline_end = dt_end or now_dt
        timeline_lookup = []
        for idx, item in enumerate(timeline_entries):
            added = item["added"]
            display_value = self._display_value(item.get("value"))
            numeric_value = self._parse_numeric(item.get("value"))
            next_added = timeline_entries[idx + 1]["added"] if idx + 1 < len(timeline_entries) else timeline_end
            duration_seconds = None
            if next_added and added:
                duration_seconds = max(0, (next_added - added).total_seconds())
            timeline_lookup.append(
                {
                    **item,
                    "display_value": display_value,
                    "numeric_value": numeric_value,
                    "timestamp": int(added.timestamp() * 1000),
                    "duration_seconds": duration_seconds,
                    "duration_label": self._format_duration(duration_seconds),
                }
            )

        previous_value = None
        if timeline_lookup:
            first_real = next((entry for entry in timeline_lookup if not entry.get("synthetic")), None)
            if first_real:
                first_index = timeline_lookup.index(first_real)
                if first_index > 0:
                    previous_value = timeline_lookup[first_index - 1]["value"]

        entries = []
        last_value = previous_value
        timeline_by_added = {}
        for item in timeline_lookup:
            timeline_by_added.setdefault(item["added"], []).append(item)

        for row in rows:
            added = row["added"]
            display_value = self._display_value(row.get("value"))
            numeric_value = self._parse_numeric(row.get("value"))
            previous_display = self._display_value(last_value) if last_value is not None else ""
            delta_numeric = None
            previous_numeric = self._parse_numeric(last_value)
            if numeric_value is not None and previous_numeric is not None:
                delta_numeric = round(numeric_value - previous_numeric, 4)
            timeline_match = None
            for candidate in timeline_by_added.get(added, []):
                if candidate.get("value") == row.get("value"):
                    timeline_match = candidate
                    break
            timeline_match = timeline_match or {"duration_seconds": None, "duration_label": ""}
            changed_for_seconds = max(0, (now_dt - added).total_seconds()) if added else None
            entries.append(
                {
                    "id": row.get("id"),
                    "added": self._serialize_dt(added),
                    "timestamp": int(added.timestamp() * 1000) if added else None,
                    "value": row.get("value"),
                    "display_value": display_value,
                    "source": row.get("source") or "Unknown",
                    "previous_value": last_value,
                    "previous_display_value": previous_display,
                    "transition": f"{previous_display} -> {display_value}" if previous_display else display_value,
                    "changed": previous_display != display_value if previous_display else True,
                    "numeric_value": numeric_value,
                    "delta_numeric": delta_numeric,
                    "delta_display": f"{delta_numeric:+g}" if delta_numeric is not None else "",
                    "duration_seconds": timeline_match.get("duration_seconds"),
                    "duration_label": timeline_match.get("duration_label"),
                    "changed_for_seconds": changed_for_seconds,
                    "changed_for_label": self._format_duration(changed_for_seconds),
                }
            )
            last_value = row.get("value")
        return entries, timeline_lookup

    def _build_summary(self, entries, timeline_entries, dt_begin, dt_end):
        last_entry = entries[-1] if entries else None
        first_entry = entries[0] if entries else None
        numeric_entries = [entry for entry in entries if entry["numeric_value"] is not None]
        source_counts = Counter(entry["source"] or "Unknown" for entry in entries)
        value_counts = Counter(entry["display_value"] for entry in entries)
        durations = Counter()
        for entry in timeline_entries:
            if entry.get("duration_seconds"):
                durations[entry["display_value"]] += entry["duration_seconds"]

        span_seconds = None
        if dt_begin and dt_end:
            span_seconds = max(1, (dt_end - dt_begin).total_seconds())
        elif entries:
            first_added = self._parse_datetime(first_entry["added"]) if first_entry else None
            last_added = self._parse_datetime(last_entry["added"]) if last_entry else None
            if first_added and last_added:
                span_seconds = max(1, (last_added - first_added).total_seconds())

        numeric_values = [entry["numeric_value"] for entry in numeric_entries]
        summary = {
            "count": len(entries),
            "changes_count": sum(1 for entry in entries if entry["changed"]),
            "distinct_values_count": len(value_counts),
            "distinct_sources_count": len(source_counts),
            "last_value": last_entry["display_value"] if last_entry else "",
            "last_source": last_entry["source"] if last_entry else "",
            "last_changed": last_entry["added"] if last_entry else None,
            "changed_for_seconds": last_entry["changed_for_seconds"] if last_entry else None,
            "changed_for_label": last_entry["changed_for_label"] if last_entry else "",
            "first_value": first_entry["display_value"] if first_entry else "",
            "first_changed": first_entry["added"] if first_entry else None,
            "change_rate_per_hour": round((len(entries) / max(1, span_seconds / 3600)), 3) if span_seconds else None,
            "min_value": min(numeric_values) if numeric_values else None,
            "max_value": max(numeric_values) if numeric_values else None,
            "avg_value": round(sum(numeric_values) / len(numeric_values), 4) if numeric_values else None,
            "delta_total": (
                round(numeric_entries[-1]["numeric_value"] - numeric_entries[0]["numeric_value"], 4)
                if len(numeric_entries) >= 2
                else None
            ),
            "top_source": source_counts.most_common(1)[0][0] if source_counts else "",
            "top_source_count": source_counts.most_common(1)[0][1] if source_counts else 0,
            "top_value": value_counts.most_common(1)[0][0] if value_counts else "",
            "top_value_count": value_counts.most_common(1)[0][1] if value_counts else 0,
        }
        return summary, source_counts, value_counts, durations

    def _percentile(self, values, percentile):
        if not values:
            return None
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * percentile
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            return ordered[lower]
        weight = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * weight

    def _build_analytics(self, entries, timeline_entries):
        hourly_counts = [0] * 24
        for entry in entries:
            added = self._parse_datetime(entry.get("added"))
            if added:
                hourly_counts[added.hour] += 1

        top_jumps = []
        numeric_entries = [entry for entry in entries if entry.get("numeric_value") is not None and entry.get("delta_numeric") is not None]
        for entry in sorted(numeric_entries, key=lambda item: abs(item.get("delta_numeric") or 0), reverse=True)[:10]:
            top_jumps.append(
                {
                    "added": entry.get("added"),
                    "value": entry.get("display_value"),
                    "previous_value": entry.get("previous_display_value"),
                    "delta": entry.get("delta_numeric"),
                    "delta_display": entry.get("delta_display"),
                    "source": entry.get("source"),
                }
            )

        numeric_values = [entry["numeric_value"] for entry in entries if entry.get("numeric_value") is not None]
        min_point = None
        max_point = None
        numeric_points = [entry for entry in entries if entry.get("numeric_value") is not None]
        if numeric_points:
            min_entry = min(numeric_points, key=lambda item: item["numeric_value"])
            max_entry = max(numeric_points, key=lambda item: item["numeric_value"])
            min_point = {"value": min_entry["numeric_value"], "added": min_entry.get("added")}
            max_point = {"value": max_entry["numeric_value"], "added": max_entry.get("added")}

        daily_profile_buckets = {}
        for entry in numeric_points:
            added = self._parse_datetime(entry.get("added"))
            if not added:
                continue
            daily_profile_buckets.setdefault(added.hour, []).append(entry["numeric_value"])
        daily_profile = []
        for hour in range(24):
            values = daily_profile_buckets.get(hour, [])
            daily_profile.append([hour, round(sum(values) / len(values), 4) if values else None])

        stddev = None
        if numeric_values:
            avg_value = sum(numeric_values) / len(numeric_values)
            variance = sum((value - avg_value) ** 2 for value in numeric_values) / len(numeric_values)
            stddev = round(math.sqrt(variance), 4)

        trend = None
        if len(numeric_points) >= 2:
            first_numeric = numeric_points[0]["numeric_value"]
            last_numeric = numeric_points[-1]["numeric_value"]
            delta_total = round(last_numeric - first_numeric, 4)
            trend = {
                "delta_total": delta_total,
                "direction": "up" if delta_total > 0 else "down" if delta_total < 0 else "flat",
            }

        positive_deltas = [entry["delta_numeric"] for entry in numeric_entries if entry.get("delta_numeric") is not None and entry["delta_numeric"] >= 0]
        negative_deltas = [entry["delta_numeric"] for entry in numeric_entries if entry.get("delta_numeric") is not None and entry["delta_numeric"] < 0]
        counter_like = False
        if numeric_entries:
            non_negative_share = len(positive_deltas) / len(numeric_entries)
            delta_total = (numeric_points[-1]["numeric_value"] - numeric_points[0]["numeric_value"]) if len(numeric_points) >= 2 else 0
            counter_like = non_negative_share >= 0.8 and delta_total >= 0

        increment_profile_buckets = {}
        for entry in numeric_entries:
            added = self._parse_datetime(entry.get("added"))
            delta = entry.get("delta_numeric")
            if not added or delta is None or delta <= 0:
                continue
            increment_profile_buckets[added.hour] = increment_profile_buckets.get(added.hour, 0) + delta
        increment_profile = [[hour, round(increment_profile_buckets.get(hour, 0), 4)] for hour in range(24)]

        counter_stats = None
        if counter_like and numeric_points:
            positive_total = round(sum(positive_deltas), 4)
            span_hours = 0
            first_added = self._parse_datetime(numeric_points[0].get("added"))
            last_added = self._parse_datetime(numeric_points[-1].get("added"))
            if first_added and last_added:
                span_hours = max((last_added - first_added).total_seconds() / 3600, 0)
            counter_stats = {
                "is_counter_like": True,
                "increment_total": positive_total,
                "avg_increment_per_hour": round(positive_total / span_hours, 4) if span_hours > 0 else None,
                "increment_profile": increment_profile,
            }

        binary_stats = None
        binary_timeline = [entry for entry in timeline_entries if entry.get("numeric_value") in (0.0, 1.0, 0, 1)]
        if binary_timeline:
            active_entries = [entry for entry in binary_timeline if entry.get("numeric_value") in (1.0, 1)]
            active_seconds = round(sum(entry.get("duration_seconds") or 0 for entry in active_entries), 2)
            active_profile_buckets = {}
            for entry in active_entries:
                added = self._parse_datetime(entry.get("added"))
                duration_seconds = entry.get("duration_seconds") or 0
                if not added or duration_seconds <= 0:
                    continue
                active_profile_buckets[added.hour] = active_profile_buckets.get(added.hour, 0) + duration_seconds
            activation_events = 0
            for idx, entry in enumerate(binary_timeline):
                if entry.get("numeric_value") not in (1.0, 1):
                    continue
                previous_value = binary_timeline[idx - 1].get("numeric_value") if idx > 0 else 0
                if previous_value in (0.0, 0, None):
                    activation_events += 1
            active_durations = [entry.get("duration_seconds") or 0 for entry in active_entries if entry.get("duration_seconds") is not None]
            binary_stats = {
                "active_seconds": active_seconds,
                "active_label": self._format_duration(active_seconds),
                "activation_count": activation_events,
                "avg_active_seconds": round(sum(active_durations) / len(active_durations), 2) if active_durations else None,
                "avg_active_label": self._format_duration(sum(active_durations) / len(active_durations)) if active_durations else "",
                "longest_active_seconds": max(active_durations) if active_durations else None,
                "longest_active_label": self._format_duration(max(active_durations)) if active_durations else "",
                "active_profile": [[hour, round(active_profile_buckets.get(hour, 0), 2)] for hour in range(24)],
            }

        stats = {
            "median": round(self._percentile(numeric_values, 0.5), 4) if numeric_values else None,
            "p90": round(self._percentile(numeric_values, 0.9), 4) if numeric_values else None,
            "p10": round(self._percentile(numeric_values, 0.1), 4) if numeric_values else None,
            "stddev": stddev,
        }

        return {
            "hourly_activity": [[hour, count] for hour, count in enumerate(hourly_counts)],
            "top_jumps": top_jumps,
            "stats": stats,
            "min_point": min_point,
            "max_point": max_point,
            "daily_profile": daily_profile,
            "trend": trend,
            "counter": counter_stats,
            "binary": binary_stats,
        }

    def _comparison_summary(self, object_name, property_name, dt_begin, dt_end):
        if not dt_begin or not dt_end:
            return None
        span = dt_end - dt_begin
        if span.total_seconds() <= 0:
            return None
        previous_begin = dt_begin - span
        previous_end = dt_begin
        previous_payload = self._build_property_payload(
            object_name,
            property_name,
            previous_begin,
            previous_end,
            bucket="auto",
            include_compare=False,
        )
        previous_summary = previous_payload.get("summary", {})
        return {
            "dt_begin": self._serialize_dt(previous_begin),
            "dt_end": self._serialize_dt(previous_end),
            "count": previous_summary.get("count"),
            "avg_value": previous_summary.get("avg_value"),
            "last_value": previous_summary.get("last_value"),
            "change_rate_per_hour": previous_summary.get("change_rate_per_hour"),
        }

    def _build_property_payload(self, object_name, property_name, dt_begin, dt_end, bucket="auto", include_compare=True):
        obj, prop = self._get_property_manager(object_name, property_name)
        full_name = f"{object_name}.{property_name}"
        rows = self._history_rows(full_name, dt_begin, dt_end)
        timeline_rows = self._build_timeline_entries(full_name, rows, dt_begin, dt_end)
        entries, timeline_entries = self._entries_with_context(rows, timeline_rows, dt_end)
        mode = self._determine_mode(prop.type, None, entries)
        numeric_series = self._build_numeric_series(entries, dt_begin, dt_end, bucket)
        state_series = self._build_state_series(timeline_entries)
        summary, source_counts, value_counts, durations = self._build_summary(entries, timeline_entries, dt_begin, dt_end)

        value_distribution = [{"name": name, "count": count} for name, count in value_counts.most_common()]
        source_distribution = [{"name": name, "count": count} for name, count in source_counts.most_common()]
        duration_distribution = [
            {"name": name, "seconds": round(seconds, 2), "label": self._format_duration(seconds)}
            for name, seconds in durations.most_common()
        ]

        comparison = self._comparison_summary(object_name, property_name, dt_begin, dt_end) if include_compare else None
        if comparison:
            summary["count_vs_previous"] = (
                summary["count"] - comparison["count"]
                if comparison.get("count") is not None and summary.get("count") is not None
                else None
            )
            summary["avg_vs_previous"] = (
                round(summary["avg_value"] - comparison["avg_value"], 4)
                if summary.get("avg_value") is not None and comparison.get("avg_value") is not None
                else None
            )

        analytics = self._build_analytics(entries, timeline_entries)

        return {
            "object_name": object_name,
            "object_description": obj.description or object_name,
            "property_name": property_name,
            "property_description": prop.description or property_name,
            "property_label": self._get_property_label(object_name, property_name),
            "property_type": prop.type,
            "history_enabled": prop.history,
            "mode": mode,
            "range": {"dt_begin": self._serialize_dt(dt_begin), "dt_end": self._serialize_dt(dt_end)},
            "entries": entries,
            "summary": summary,
            "compare_previous": comparison,
            "series": {
                "numeric": numeric_series["series"],
                "numeric_bucket": numeric_series["bucket"],
                "state": state_series["series"],
                "state_categories": state_series["categories"],
                "source_pie": [[item["name"], item["count"]] for item in source_distribution],
                "value_pie": [[item["name"], item["count"]] for item in value_distribution],
                "duration_column": [[item["name"], item["seconds"]] for item in duration_distribution],
            },
            "distributions": {
                "sources": source_distribution,
                "values": value_distribution,
                "durations": duration_distribution,
            },
            "analytics": analytics,
        }

    def _build_widget_context(self, widget_id: str = None):
        if not widget_id:
            return None

        widgets_list = self.config.get("widgets", [])
        widget_config = next((w for w in widgets_list if w.get("id") == widget_id), None)
        if not widget_config:
            return None

        dt_begin, dt_end = self._resolve_range(period=widget_config.get("period", 24))
        raw_properties = widget_config.get("properties", [])
        properties = []
        for prop in raw_properties:
            prop_name = None
            meta = {}
            if isinstance(prop, str):
                prop_name = prop
            elif isinstance(prop, dict):
                prop_name = prop.get("name")
                if not prop_name and prop.get("object") and prop.get("property"):
                    prop_name = f"{prop.get('object')}.{prop.get('property')}"
                meta = {"chart_type": prop.get("chart_type"), "color": prop.get("color")}
            if prop_name:
                properties.append({"name": prop_name, **meta})

        properties_payloads = {}
        for item in properties:
            object_name, property_name = item["name"].split(".", 1)
            payload = self._build_property_payload(object_name, property_name, dt_begin, dt_end, include_compare=False)
            payload["widget_meta"] = {"chart_type": item.get("chart_type"), "color": item.get("color")}
            properties_payloads[item["name"]] = payload

        return {"widget_config": widget_config, "properties_payloads": properties_payloads}

    def widget(self, name: str = None, _settings: dict = None):
        context = self._build_widget_context(name)
        if not context:
            return ""
        return render_template("widget_history.html", **context)

    def page(self, request):
        widget_id = request.args.get("widget_id") or request.args.get("id") or request.args.get("name")
        if widget_id:
            context = self._build_widget_context(widget_id)
            if not context:
                return redirect(f"/page/{self.name}")
            return render_template("widget_page.html", **context)

        widgets_list = self.config.get("widgets", [])
        return render_template("widgets_page_list.html", widgets=widgets_list)

    def search(self, query: str) -> list:
        res = []
        query_lower = query.lower()
        widgets_list = self.config.get("widgets", [])

        for widget in widgets_list:
            widget_name = widget.get("name", "")
            widget_id = widget.get("id", "")
            properties = widget.get("properties", [])
            chart_type = widget.get("chart_type", "line")

            if query_lower in widget_name.lower():
                res.append(
                    {
                        "url": f"/page/{self.name}?widget_id={widget_id}",
                        "title": widget_name,
                        "tags": [
                            {"name": "History Widget", "color": "info"},
                            {"name": chart_type, "color": "secondary"},
                        ],
                    }
                )
                continue

            matched_properties = []
            for prop in properties:
                if query_lower in json.dumps(prop).lower():
                    matched_properties.append(str(prop.get("name") if isinstance(prop, dict) else prop))

            if matched_properties:
                tags = [
                    {"name": "History Widget", "color": "info"},
                    {"name": chart_type, "color": "secondary"},
                ]
                for prop_name in matched_properties[:3]:
                    tags.append({"name": prop_name, "color": "success"})
                res.append(
                    {
                        "url": f"/page/{self.name}?widget_id={widget_id}",
                        "title": f"{widget_name} ({', '.join(matched_properties[:2])})",
                        "tags": tags,
                    }
                )

        return res

    def admin(self, request):
        op = request.args.get("op", None)
        object_arg = (request.args.get("object", "") or "").strip()
        object_id = 0
        obj = None
        if object_arg:
            if object_arg.isdigit():
                object_id = int(object_arg)
            else:
                obj = Object.query.where(Object.name == object_arg).one_or_none()
                if obj:
                    object_id = obj.id
        name = request.args.get("name", None)

        if op == "create_widget":
            return render_template("widget_form.html", widget_edit=None)

        if op == "edit_widget":
            widget_id = request.args.get("widget_id", None)
            widgets_list = self.config.get("widgets", [])
            widget_edit = next((w for w in widgets_list if w.get("id") == widget_id), None)
            return render_template("widget_form.html", widget_edit=widget_edit)

        if op == "delete_widget":
            widget_id = request.args.get("widget_id", None)
            widgets_list = self.config.get("widgets", [])
            self.config["widgets"] = [w for w in widgets_list if w.get("id") != widget_id]
            self.saveConfig()
            return redirect(f"/admin/{self.name}")

        if op == "save_widget" and flask_request.method == "POST":
            widget_id = flask_request.form.get("widget_id")
            widget_name = flask_request.form.get("widget_name", "").strip()
            period = int(flask_request.form.get("period", 24))
            properties_str = flask_request.form.get("properties", "")
            properties_json = flask_request.form.get("properties_json", "")
            chart_type = flask_request.form.get("chart_type", "line")
            show_legend = flask_request.form.get("show_legend") == "on"
            show_navigator = flask_request.form.get("show_navigator") == "on"
            show_range_selector = flask_request.form.get("show_range_selector") == "on"
            show_context_menu = flask_request.form.get("show_context_menu") == "on"

            properties = []
            if properties_json:
                try:
                    parsed = json.loads(properties_json)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and item.get("name"):
                                properties.append(
                                    {
                                        "name": item.get("name"),
                                        "chart_type": item.get("chart_type") or None,
                                        "color": item.get("color") or None,
                                    }
                                )
                except json.JSONDecodeError:
                    properties = []

            if not properties:
                properties = [p.strip() for p in properties_str.split(",") if p.strip()]

            widgets_list = self.config.get("widgets", [])
            if widget_id and widget_id != "new":
                for widget in widgets_list:
                    if widget.get("id") == widget_id:
                        widget.update(
                            {
                                "name": widget_name,
                                "period": period,
                                "properties": properties,
                                "chart_type": chart_type,
                                "show_legend": show_legend,
                                "show_navigator": show_navigator,
                                "show_range_selector": show_range_selector,
                                "show_context_menu": show_context_menu,
                            }
                        )
                        widget.pop("height", None)
                        break
            else:
                widgets_list.append(
                    {
                        "id": str(uuid.uuid4()),
                        "name": widget_name,
                        "period": period,
                        "properties": properties,
                        "chart_type": chart_type,
                        "show_legend": show_legend,
                        "show_navigator": show_navigator,
                        "show_range_selector": show_range_selector,
                        "show_context_menu": show_context_menu,
                    }
                )

            self.config["widgets"] = widgets_list
            self.saveConfig()
            return redirect(f"/admin/{self.name}")

        if op == "delete":
            history_id = request.args.get("id", None)
            with session_scope() as session:
                session.query(History).filter(History.id == history_id).delete()
                session.commit()
            return redirect(f"{self.name}?object={object_id}&name={name}")

        if obj is None:
            obj = Object.query.where(Object.id == object_id).one_or_none() if object_id > 0 else None
        if not obj:
            widgets_list = self.config.get("widgets", [])
            return render_template("widgets_list.html", widgets=widgets_list)

        return render_template("history.html", object=obj, name=name)
