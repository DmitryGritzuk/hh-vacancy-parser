# HH Vacancy Parser (Python) → CSV

Мини-проект: получает вакансии с hh.ru через официальный API и сохраняет в CSV.

## Возможности
- Поиск по текстовому запросу
- Фильтр по региону (area id)
- Экспорт в CSV (utf-8-sig)
- Опционально: дозагрузка деталей (опыт, график, навыки) по каждой вакансии

## Установка
python -m venv .venv
source .venv/bin/activate  # mac/linux
pip install -r requirements.txt
python main.py
