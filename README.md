# HH Vacancy Parser (Python) → CSV

Мини-проект: получает вакансии с hh.ru через официальный API и сохраняет результат в CSV.

## Возможности

- Поиск по текстовому запросу (`--text`)
- Фильтр по региону (`--area`, например: 1 = Москва, 2 = Санкт-Петербург)
- Пагинация (`--pages`, `--per-page`)
- Экспорт в CSV (`utf-8-sig`, удобно для Excel)
- Опционально: дозагрузка деталей по каждой вакансии (`--details`):
  - опыт / график / занятость / ключевые навыки / description snippet
- Метаданные в CSV: `query_text`, `area_id`, `collected_at`
- Защита от rate limit (429): ретраи + backoff

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
