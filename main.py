import csv
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


API_URL = "https://api.hh.ru/vacancies"


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


def fetch_page(
    text: str,
    area: Optional[str],
    page: int,
    per_page: int,
    user_agent: str,
) -> Dict[str, Any]:
    params = {
        "text": text,
        "page": page,
        "per_page": per_page,
    }
    if area:
        params["area"] = area

    headers = {"User-Agent": user_agent}

    r = requests.get(API_URL, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def collect_vacancies(
    text: str,
    area: Optional[str],
    pages: int,
    per_page: int,
    delay_sec: float = 0.3,
) -> List[Dict[str, Any]]:
    user_agent = "hh-vacancy-parser (learning project)"
    all_items: List[Dict[str, Any]] = []

    for page in range(pages):
        data = fetch_page(text, area, page, per_page, user_agent)
        items = data.get("items", [])
        all_items.extend(items)

        # чтобы не долбить API слишком быстро
        time.sleep(delay_sec)

        # если страниц меньше, чем мы попросили — выходим
        total_pages = data.get("pages")
        if isinstance(total_pages, int) and page + 1 >= total_pages:
            break

    return all_items


def save_csv(items: List[Dict[str, Any]], path: str) -> None:
    fields = [
        "name",
        "employer",
        "salary",
        "area",
        "published_at",
        "url",
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()

        for v in items:
            name = v.get("name", "")
            employer = (v.get("employer") or {}).get("name", "")
            salary = format_salary(v.get("salary"))
            area = (v.get("area") or {}).get("name", "")
            published_at = v.get("published_at", "")
            url = v.get("alternate_url", "")

            w.writerow(
                {
                    "name": name,
                    "employer": employer,
                    "salary": salary,
                    "area": area,
                    "published_at": published_at,
                    "url": url,
                }
            )


def main() -> None:
    print("HH Vacancy Parser -> CSV")

    text = input("Запрос (например: python junior): ").strip()
    area = input("Area id (например 1=Москва, 2=СПб, пусто=вся РФ): ").strip() or None

    pages_str = input("Сколько страниц взять (например 2): ").strip()
    per_page_str = input("Вакансий на страницу (1..100, например 50): ").strip()

    pages = int(pages_str) if pages_str else 2
    per_page = int(per_page_str) if per_page_str else 50
    if per_page < 1:
        per_page = 1
    if per_page > 100:
        per_page = 100

    items = collect_vacancies(text=text, area=area, pages=pages, per_page=per_page)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"vacancies_{ts}.csv"
    save_csv(items, out)

    print(f"Готово: {out}")
    print(f"Найдено вакансий: {len(items)}")


if __name__ == "__main__":
    main()
