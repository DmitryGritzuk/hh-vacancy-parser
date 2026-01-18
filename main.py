import argparse
import csv
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


API_VACANCIES = "https://api.hh.ru/vacancies"


def format_salary(s: Optional[Dict[str, Any]]) -> str:
    """Красивое форматирование зарплаты из поля salary."""
    if not s:
        return ""
    frm = s.get("from")
    to = s.get("to")
    cur = s.get("currency") or ""
    gross = s.get("gross")
    tax = "gross" if gross else "net"

    if frm is None and to is None:
        return ""
    if frm is None:
        return f"до {to} {cur} ({tax})"
    if to is None:
        return f"от {frm} {cur} ({tax})"
    return f"{frm}–{to} {cur} ({tax})"


def hh_get(url: str, params: Optional[Dict[str, Any]] = None, retries: int = 5) -> Dict[str, Any]:
    """
    GET к API hh.ru с обработкой лимитов (429) и ретраями.
    """
    headers = {"User-Agent": "hh-vacancy-parser (learning project)"}

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=25)

            # Rate limit
            if r.status_code == 429:
                wait = 1.5 * (attempt + 1)
                time.sleep(wait)
                continue

            r.raise_for_status()
            return r.json()

        except requests.RequestException as e:
            last_err = e
            # небольшой backoff на сетевые/5xx
            time.sleep(0.8 * (attempt + 1))

    raise requests.HTTPError(f"Request failed after {retries} retries: {last_err}") from last_err


def collect_vacancies(
    text: str,
    area: Optional[str],
    pages: int,
    per_page: int,
    delay: float,
) -> List[Dict[str, Any]]:
    """Собираем вакансии из поиска (items)."""
    items: List[Dict[str, Any]] = []

    for page in range(pages):
        params: Dict[str, Any] = {"text": text, "page": page, "per_page": per_page}
        if area:
            params["area"] = area

        data = hh_get(API_VACANCIES, params=params)
        items.extend(data.get("items", []))

        total_pages = data.get("pages")
        if isinstance(total_pages, int) and page + 1 >= total_pages:
            break

        time.sleep(delay)

    return items


def enrich_with_details(items: List[Dict[str, Any]], delay: float) -> List[Dict[str, Any]]:
    """
    Дотягиваем детали по каждой вакансии из detail endpoint:
    опыт / график / занятость / ключевые навыки / description snippet.
    """
    enriched: List[Dict[str, Any]] = []

    for v in items:
        url = v.get("url")
        if not url:
            enriched.append(v)
            continue

        try:
            d = hh_get(url)

            v["experience_name"] = (d.get("experience") or {}).get("name", "")
            v["schedule_name"] = (d.get("schedule") or {}).get("name", "")
            v["employment_name"] = (d.get("employment") or {}).get("name", "")

            skills = [ks.get("name", "") for ks in (d.get("key_skills") or []) if ks.get("name")]
            v["key_skills"] = ", ".join(skills)

            # HH возвращает HTML. Делаем аккуратный короткий snippet.
            desc = d.get("description") or ""
            desc = " ".join(desc.split())  # убираем лишние пробелы/переносы
            v["description_snippet"] = desc[:300]

        except requests.RequestException:
            v["experience_name"] = ""
            v["schedule_name"] = ""
            v["employment_name"] = ""
            v["key_skills"] = ""
            v["description_snippet"] = ""

        enriched.append(v)
        time.sleep(delay)

    return enriched


def save_csv(
    items: List[Dict[str, Any]],
    path: str,
    include_details: bool,
    query_text: str,
    area_id: Optional[str],
    collected_at: str,
) -> None:
    """
    Сохраняем в CSV (utf-8-sig) + добавляем метаданные (запрос/регион/время сборки).
    """
    base_fields = [
        "name",
        "employer",
        "salary",
        "area",
        "published_at",
        "hh_url",
        "query_text",
        "area_id",
        "collected_at",
    ]

    details_fields = [
        "experience_name",
        "schedule_name",
        "employment_name",
        "key_skills",
        "description_snippet",
    ]

    fields = base_fields + (details_fields if include_details else [])

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()

        for v in items:
            row = {
                "name": v.get("name", ""),
                "employer": (v.get("employer") or {}).get("name", ""),
                "salary": format_salary(v.get("salary")),
                "area": (v.get("area") or {}).get("name", ""),
                "published_at": v.get("published_at", ""),
                "hh_url": v.get("alternate_url", ""),
                "query_text": query_text,
                "area_id": area_id or "",
                "collected_at": collected_at,
            }

            if include_details:
                row.update(
                    {
                        "experience_name": v.get("experience_name", ""),
                        "schedule_name": v.get("schedule_name", ""),
                        "employment_name": v.get("employment_name", ""),
                        "key_skills": v.get("key_skills", ""),
                        "description_snippet": v.get("description_snippet", ""),
                    }
                )

            w.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="HH Vacancy Parser -> CSV (official API)")
    p.add_argument("--text", required=True, help='Поисковый запрос, например: "python junior"')
    p.add_argument("--area", default="", help="Area id, например 1=Москва, 2=СПб. Пусто = без фильтра")
    p.add_argument("--pages", type=int, default=2, help="Сколько страниц взять (по 0..pages-1)")
    p.add_argument("--per-page", type=int, default=50, help="Вакансий на страницу (1..100)")
    p.add_argument("--delay", type=float, default=0.3, help="Пауза между запросами (сек)")
    p.add_argument("--out", default="vacancies.csv", help="Имя CSV файла")
    p.add_argument("--details", action="store_true", help="Дозагружать детали по каждой вакансии (медленнее)")
    p.add_argument("--timestamp", action="store_true", help="Добавить timestamp к имени файла")
    return p


def main() -> None:
    args = build_parser().parse_args()

    query_text = args.text.strip()
    if not query_text:
        raise SystemExit("ERROR: --text is empty")

    per_page = max(1, min(100, args.per_page))
    pages = max(1, args.pages)
    delay = max(0.0, args.delay)
    area_id = args.area.strip() or None

    collected_at = datetime.now().isoformat(timespec="seconds")

    items = collect_vacancies(query_text, area_id, pages, per_page, delay)

    if args.details and items:
        items = enrich_with_details(items, delay=max(0.2, delay))

    out = args.out
    if args.timestamp:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if out.lower().endswith(".csv"):
            out = out[:-4] + f"_{ts}.csv"
        else:
            out = out + f"_{ts}.csv"

    save_csv(
        items=items,
        path=out,
        include_details=args.details,
        query_text=query_text,
        area_id=area_id,
        collected_at=collected_at,
    )

    print(f"OK: {out}")
    print(f"Vacancies: {len(items)}")
    if args.details:
        print("Details: enabled (extra requests per vacancy)")
    if area_id:
        print(f"Area: {area_id}")


if __name__ == "__main__":
    main()
