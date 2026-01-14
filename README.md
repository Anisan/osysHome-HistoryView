# HistoryView - History Visualization Module

![HistoryView Icon](static/HistoryView.png)

A history visualization system for viewing object property history with customizable charts and widgets.

## Description

The `HistoryView` module provides history visualization capabilities for the osysHome platform. It enables you to view historical data of object properties, create custom widgets with charts, and analyze trends over time.

## Main Features

- ✅ **History Viewing**: View property history for objects
- ✅ **Chart Widgets**: Create customizable chart widgets
- ✅ **Chart Types**: Line charts, pie charts
- ✅ **Multiple Properties**: Display multiple properties in one widget
- ✅ **Time Periods**: Configurable time periods (hours)
- ✅ **Widget Management**: Create, edit, delete widgets
- ✅ **Fullscreen Widget Pages**: Open widgets in dedicated fullscreen pages
- ✅ **Widget Search**: Search widgets by name and object properties
- ✅ **Highcharts Integration**: Professional charting library

## Admin Panel

The module provides a comprehensive admin interface:

### Main View
- **Widgets List**: View all created widgets
- **Widget Management**: Create, edit, delete widgets
- **History View**: View property history for specific objects

### Widget Configuration
- **Widget Name**: Display name
- **Time Period**: Hours to display (0 for all)
- **Properties**: Comma-separated list of properties (Object.Property)
- **Chart Type**: Line or pie chart
- **Chart Options**: Legend, navigator, range selector, context menu

## Widget Types

### Line Chart
- Time series visualization
- Multiple properties support
- Interactive zoom and pan
- Value tooltips

### Pie Chart
- Value distribution
- Aggregated data display
- Percentage display

## Usage

### Creating a Widget

1. Navigate to HistoryView module
2. Click "Create Widget"
3. Enter widget name
4. Set time period
5. Add properties (Object.Property format)
6. Select chart type
7. Configure chart options
8. Save widget

### Viewing History

1. Navigate to HistoryView module
2. Select object from list
3. View property history
4. Delete history entries if needed

### Viewing Widget Charts

1. Navigate to `/page/HistoryView` to see all widgets
2. Click on a widget card to open its chart in fullscreen
3. Use the back button to return to the widgets list

### Searching Widgets

The module supports search functionality:
- Search by widget name
- Search by object properties (e.g., "Object.Property")
- Search results link directly to widget pages

## Technical Details

- **Chart Library**: Highcharts
- **Data Format**: Timestamp-value pairs
- **Property Format**: Object.Property
- **Time Handling**: UTC to local time conversion
- **Widget Storage**: Configuration stored in module config

## Version

Current version: **1.2**

## Category

System

## Actions

The module provides the following actions:
- `widget` - Render history widgets for dashboard
- `page` - Render fullscreen widget pages (list or individual widget chart)
- `search` - Search widgets by name and object properties

## Requirements

- Flask
- SQLAlchemy
- Highcharts (JavaScript library)
- osysHome core system

## Author

osysHome Team

## License

See the main osysHome project license

