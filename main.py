import argparse
import csv
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


API_VACANCIES = "https://api.hh.ru/vacancies"


def format_salary(s: Optional[Dict[str, Any]]) -> str:
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


def hh_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {"User-Agent": "hh-vacancy-parser (learning project)"}
    r = requests.get(url, params=params, headers=headers, timeout=25)
    r.raise_for_status()
    return r.json()


def collect_vacancies(text: str, area: Optional[str], pages: int, per_page: int, delay: float) -> List[Dict[str, Any]]:
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
    """Дотягиваем описание/ключевые навыки/опыт из detail endpoint."""
    enriched: List[Dict[str, Any]] = []

    for i, v in enumerate(items, start=1):
        url = v.get("url")
        if not url:
            enriched.append(v)
            continue

        try:
            d = hh_get(url)
            v["experience_name"] = (d.get("experience") or {}).get("name", "")
            v["schedule_name"] = (d.get("schedule") or {}).get("name", "")
            v["employment_name"] = (d.get("employment") or {}).get("name", "")
            v["key_skills"] = ", ".join([ks.get("name", "") for ks in (d.get("key_skills") or []) if ks.get("name")])
            v["description_snippet"] = (d.get("description") or "")
        except requests.RequestException:
            v["experience_name"] = ""
            v["schedule_name"] = ""
            v["employment_name"] = ""
            v["key_skills"] = ""
            v["description_snippet"] = ""

        enriched.append(v)
        time.sleep(delay)

    return enriched


def save_csv(items: List[Dict[str, Any]], path: str, include_details: bool) -> None:
    base_fields = [
        "name",
        "employer",
        "salary",
        "area",
        "published_at",
        "url",
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
                "url": v.get("alternate_url", ""),
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

    per_page = max(1, min(100, args.per_page))
    pages = max(1, args.pages)
    delay = max(0.0, args.delay)
    area = args.area.strip() or None

    items = collect_vacancies(args.text.strip(), area, pages, per_page, delay)

    if args.details and items:
        items = enrich_with_details(items, delay=max(0.2, delay))

    out = args.out
    if args.timestamp:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if out.lower().endswith(".csv"):
            out = out[:-4] + f"_{ts}.csv"
        else:
            out = out + f"_{ts}.csv"

    save_csv(items, out, include_details=args.details)

    print(f"OK: {out}")
    print(f"Vacancies: {len(items)}")


if __name__ == "__main__":
    main()
