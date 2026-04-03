# HistoryView

![HistoryView Icon](static/HistoryView.png "HistoryView plugin")

`HistoryView` is the osysHome module for property history exploration, trend analysis, and reusable widget-based history dashboards.

## Documentation

- [Module index](docs/index.md)
- [User Guide](docs/USER_GUIDE.md)
- [Technical Reference](docs/TECHNICAL_REFERENCE.md)

## What Is Covered In v2.0

- dedicated property history page with chart, analytics, table, and summary;
- automatic handling of numeric, boolean, and state-like data;
- previous-period comparison and CSV export;
- configurable multi-series widgets with per-series type/color overrides;
- fullscreen widget pages and global search integration.

## Entry Points

```text
/admin/HistoryView
/page/HistoryView
/page/HistoryView?widget_id=<widget-id>
/HistoryView/api/history_data
```

## Admin Operations

`/admin/HistoryView` supports these operation modes:

- `op=create_widget`: open empty widget form;
- `op=edit_widget&widget_id=<id>`: edit widget;
- `op=save_widget` (`POST`): create/update widget config;
- `op=delete_widget&widget_id=<id>`: remove widget;
- `op=delete&id=<history-id>`: delete one history row.

## History API Quick Reference

Endpoint: `GET /HistoryView/api/history_data`

Required query params:

- `object`
- `property`

Common optional params:

- `period` (`1`, `24`, `168`, `720`)
- `from` and `to` (`YYYY-MM-DD HH:MM`)
- `bucket` (`auto`, `5m`, `15m`, `1h`, `6h`, `1d`)
- `include_compare` (`true` or `false`)

For full payload schema and internal behavior, see [Technical Reference](docs/TECHNICAL_REFERENCE.md#history-api).

## Version

`2.0`
