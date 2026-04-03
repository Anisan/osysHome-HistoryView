# HistoryView

![HistoryView Icon](static/HistoryView.png "Плагин HistoryView")

`HistoryView` — модуль osysHome для просмотра истории свойств, анализа трендов и создания переиспользуемых виджетов истории.

## Документация

- [Индекс модуля](docs/index.ru.md)
- [Руководство пользователя](docs/USER_GUIDE.ru.md)
- [Техническое описание](docs/TECHNICAL_REFERENCE.ru.md)

## Что входит в версию 2.0

- отдельная страница истории свойства с графиком, аналитикой, таблицей и сводкой;
- автоматическая работа с числовыми, булевыми и состоянийными данными;
- сравнение с предыдущим периодом и экспорт таблицы в CSV;
- настраиваемые мультисерийные виджеты с типом/цветом для каждой серии;
- полноэкранные страницы виджетов и интеграция с глобальным поиском.

## Точки входа

```text
/admin/HistoryView
/page/HistoryView
/page/HistoryView?widget_id=<id-виджета>
/HistoryView/api/history_data
```

## Режимы админки

`/admin/HistoryView` поддерживает следующие режимы:

- `op=create_widget`: открыть пустую форму виджета;
- `op=edit_widget&widget_id=<id>`: редактировать виджет;
- `op=save_widget` (`POST`): создать или обновить конфиг виджета;
- `op=delete_widget&widget_id=<id>`: удалить виджет;
- `op=delete&id=<history-id>`: удалить одну запись истории.

## Кратко про History API

Эндпоинт: `GET /HistoryView/api/history_data`

Обязательные параметры:

- `object`
- `property`

Часто используемые необязательные параметры:

- `period` (`1`, `24`, `168`, `720`)
- `from` и `to` (`YYYY-MM-DD HH:MM`)
- `bucket` (`auto`, `5m`, `15m`, `1h`, `6h`, `1d`)
- `include_compare` (`true` или `false`)

Полная структура ответа и детали реализации описаны в [техническом описании](docs/TECHNICAL_REFERENCE.ru.md#history-api).

## Версия

`2.0`
