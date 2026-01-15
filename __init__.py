from flask import render_template, redirect, request as flask_request
import json
from app.core.main.BasePlugin import BasePlugin
from app.database import session_scope
from app.core.models.Clasess import Object, History
from app.core.main.ObjectsStorage import objects_storage
from app.core.lib.object import getHistory
import datetime
import uuid

class HistoryView(BasePlugin):

    def __init__(self,app):
        super().__init__(app,__name__)
        self.title = "History"
        self.description = """History viewer"""
        self.category = "System"
        self.version = "1.2"
        self.actions = ['widget', 'page', 'search']

    def initialization(self):
        pass

    def widgets(self):
        """Return list of available widgets"""
        widgets_list = self.config.get('widgets', [])
        result = []
        for widget in widgets_list:
            result.append({
                "name": widget.get('id'),
                "description": widget.get('name', 'Unnamed Widget')
            })
        return result

    def _build_widget_context(self, widget_id: str = None):
        """Prepare widget configuration and data for rendering"""
        if not widget_id:
            return None

        widgets_list = self.config.get('widgets', [])
        widget_config = next((w for w in widgets_list if w.get('id') == widget_id), None)
        if not widget_config:
            return None

        # Get period
        period = widget_config.get('period', 24)

        # Calculate datetime range
        dt_end = datetime.datetime.now()
        dt_begin = None
        if period > 0:
            dt_begin = dt_end - datetime.timedelta(hours=period)

        # Get properties data
        raw_properties = widget_config.get('properties', [])
        chart_type = widget_config.get('chart_type', 'line')
        properties_data = {}
        properties_labels = {}  # Dictionary to store labels (descriptions) for each property
        properties = []

        # Normalize properties list (support legacy string list and new dict list)
        for prop in raw_properties:
            prop_name = None
            if isinstance(prop, str):
                prop_name = prop
            elif isinstance(prop, dict):
                prop_name = prop.get('name')
                if not prop_name and prop.get('object') and prop.get('property'):
                    prop_name = f"{prop.get('object')}.{prop.get('property')}"
            if prop_name:
                properties.append(prop_name)

        for prop_name in properties:
            try:
                # Get object and property descriptions
                if '.' in prop_name:
                    object_name, property_name = prop_name.split('.', 1)
                    obj = objects_storage.getObjectByName(object_name)
                    if obj:
                        object_desc = obj.description or object_name
                        if property_name in obj.properties:
                            prop_desc = obj.properties[property_name].description or property_name
                            # Format: "Object Description - Property Description"
                            properties_labels[prop_name] = f"{object_desc} - {prop_desc}"
                        else:
                            properties_labels[prop_name] = f"{object_desc} - {property_name}"
                    else:
                        properties_labels[prop_name] = prop_name
                else:
                    properties_labels[prop_name] = prop_name

                history_data = getHistory(prop_name, dt_begin, dt_end, None, False)
                if history_data:
                    if chart_type == 'pie':
                        # For pie chart, aggregate data by value (count occurrences)
                        value_counts = {}
                        for item in history_data:
                            if 'value' in item:
                                value = item['value']
                                # Convert value to string for grouping
                                value_str = str(value)
                                value_counts[value_str] = value_counts.get(value_str, 0) + 1

                        # Format for pie chart: [['Value1', count1], ['Value2', count2], ...]
                        pie_data = [[str(k), v] for k, v in value_counts.items()]
                        properties_data[prop_name] = pie_data
                    else:
                        # Format data for Highcharts: [[timestamp, value], ...]
                        chart_data = []
                        for item in history_data:
                            if 'added' in item and 'value' in item:
                                # Convert datetime to timestamp (milliseconds)
                                if isinstance(item['added'], str):
                                    dt = datetime.datetime.fromisoformat(item['added'].replace(' ', 'T'))
                                else:
                                    dt = item['added']
                                timestamp = int(dt.timestamp() * 1000)
                                value = item['value']
                                # Try to convert to number if possible
                                try:
                                    if isinstance(value, (int, float)):
                                        chart_data.append([timestamp, value])
                                    elif isinstance(value, bool):
                                        chart_data.append([timestamp, 1 if value else 0])
                                    else:
                                        # Try to parse as number
                                        num_value = float(value)
                                        chart_data.append([timestamp, num_value])
                                except (ValueError, TypeError):
                                    # Skip non-numeric values
                                    continue

                        # Sort by timestamp
                        chart_data.sort(key=lambda x: x[0])
                        properties_data[prop_name] = chart_data
            except Exception as e:
                self.logger.exception("Error loading history for %s: %s", prop_name, e)
                properties_data[prop_name] = []
                if prop_name not in properties_labels:
                    properties_labels[prop_name] = prop_name
        return {
            "widget_config": widget_config,
            "properties_data": properties_data,
            "properties_labels": properties_labels,
        }

    def widget(self, name: str = None, _settings: dict = None):
        """Render widget HTML"""
        context = self._build_widget_context(name)
        if not context:
            return ""

        return render_template(
            'widget_history.html',
            **context,
        )

    def page(self, request):
        """Render full page: list of widgets or selected widget chart"""
        widget_id = request.args.get("widget_id") or request.args.get("id") or request.args.get("name")

        # If widget_id is provided, show the chart
        if widget_id:
            context = self._build_widget_context(widget_id)
            if not context:
                return redirect(f'/page/{self.name}')
            return render_template(
                'widget_page.html',
                **context,
            )

        # Otherwise, show list of widgets
        widgets_list = self.config.get('widgets', [])
        return render_template(
            'widgets_page_list.html',
            widgets=widgets_list,
        )

    def search(self, query: str) -> list:
        """Search widgets by name and object.property"""
        res = []
        query_lower = query.lower()
        widgets_list = self.config.get('widgets', [])

        for widget in widgets_list:
            widget_name = widget.get('name', '')
            widget_id = widget.get('id', '')
            properties = widget.get('properties', [])
            chart_type = widget.get('chart_type', 'line')

            # Search by widget name
            if query_lower in widget_name.lower():
                tags = [
                    {"name": "History Widget", "color": "info"},
                    {"name": chart_type, "color": "secondary"}
                ]
                res.append({
                    "url": f"/page/{self.name}?widget_id={widget_id}",
                    "title": widget_name,
                    "tags": tags
                })
                continue

            # Search by object.property in properties
            matched_properties = []
            for prop in properties:
                if query_lower in prop.lower():
                    matched_properties.append(prop)

            if matched_properties:
                tags = [
                    {"name": "History Widget", "color": "info"},
                    {"name": chart_type, "color": "secondary"}
                ]
                # Add matched properties as tags
                for prop in matched_properties[:3]:  # Limit to 3 properties
                    tags.append({"name": prop, "color": "success"})

                res.append({
                    "url": f"HistoryView?op=edit_widget&widget_id={widget_id}",
                    "title": f"{widget_name} ({', '.join(matched_properties[:2])})",
                    "tags": tags
                })

        return res

    def admin(self, request):
        op = request.args.get("op", None)
        object_id = int(request.args.get("object", 0))
        name = request.args.get("name", None)

        # Widget management operations
        if op == 'create_widget':
            widgets_list = self.config.get('widgets', [])
            return render_template('widget_form.html', widget_edit=None)

        if op == 'edit_widget':
            widget_id = request.args.get("widget_id", None)
            widgets_list = self.config.get('widgets', [])
            widget_edit = None
            for w in widgets_list:
                if w.get('id') == widget_id:
                    widget_edit = w
                    break
            return render_template('widget_form.html', widget_edit=widget_edit)

        if op == 'delete_widget':
            widget_id = request.args.get("widget_id", None)
            widgets_list = self.config.get('widgets', [])
            widgets_list = [w for w in widgets_list if w.get('id') != widget_id]
            self.config['widgets'] = widgets_list
            self.saveConfig()
            return redirect(f'/admin/{self.name}')

        if op == 'save_widget':
            # Handle POST request for saving widget
            if flask_request.method == 'POST':
                widget_id = flask_request.form.get('widget_id')
                widget_name = flask_request.form.get('widget_name', '').strip()
                period = int(flask_request.form.get('period', 24))
                properties_str = flask_request.form.get('properties', '')
                properties_json = flask_request.form.get('properties_json', '')
                chart_type = flask_request.form.get('chart_type', 'line')
                show_legend = flask_request.form.get('show_legend') == 'on'
                show_navigator = flask_request.form.get('show_navigator') == 'on'
                show_range_selector = flask_request.form.get('show_range_selector') == 'on'
                show_context_menu = flask_request.form.get('show_context_menu') == 'on'

                # Parse properties (prefer JSON payload with per-series settings)
                properties = []
                if properties_json:
                    try:
                        parsed = json.loads(properties_json)
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict) and item.get('name'):
                                    properties.append({
                                        'name': item.get('name'),
                                        'chart_type': item.get('chart_type') or None,
                                        'color': item.get('color') or None
                                    })
                    except json.JSONDecodeError:
                        properties = []

                # Fallback to comma-separated list
                if not properties:
                    properties = [p.strip() for p in properties_str.split(',') if p.strip()]

                widgets_list = self.config.get('widgets', [])

                if widget_id and widget_id != 'new':
                    # Edit existing widget
                    for w in widgets_list:
                        if w.get('id') == widget_id:
                            w['name'] = widget_name
                            w['period'] = period
                            w['properties'] = properties
                            w['chart_type'] = chart_type
                            w['show_legend'] = show_legend
                            w['show_navigator'] = show_navigator
                            w['show_range_selector'] = show_range_selector
                            w['show_context_menu'] = show_context_menu
                            # Remove height if it exists (for backward compatibility)
                            if 'height' in w:
                                del w['height']
                            break
                else:
                    # Create new widget
                    new_widget = {
                        'id': str(uuid.uuid4()),
                        'name': widget_name,
                        'period': period,
                        'properties': properties,
                        'chart_type': chart_type,
                        'show_legend': show_legend,
                        'show_navigator': show_navigator,
                        'show_range_selector': show_range_selector,
                        'show_context_menu': show_context_menu
                    }
                    widgets_list.append(new_widget)

                self.config['widgets'] = widgets_list
                self.saveConfig()
                return redirect(f'/admin/{self.name}')

        # Original history view operations
        if op == 'delete':
            history_id = request.args.get("id", None)
            with session_scope() as session:
                session.query(History).filter(History.id == history_id).delete()
                session.commit()
                return redirect(f'{self.name}?object={object_id}&name={name}')

        obj = Object.query.where(Object.id == object_id).one_or_none() if object_id > 0 else None

        # If no object specified, show widgets list
        if not obj:
            widgets_list = self.config.get('widgets', [])
            return render_template('widgets_list.html', widgets=widgets_list)

        return render_template('history.html', object=obj, name=name)
