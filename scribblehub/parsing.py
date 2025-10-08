from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http_utils import perform_request
from .models import ChapterListing

BR_PLACEHOLDER = "__BR_BREAK__"


def parse_series_metadata(html: str) -> tuple[str, Optional[int]]:
    soup = BeautifulSoup(html, "html.parser")
    post_input = soup.select_one("#mypostid")
    if not post_input or not post_input.get("value"):
        raise RuntimeError("Series post ID not found. Is this a ScribbleHub series page?")
    post_id = post_input["value"].strip()

    expected_total: Optional[int] = None
    counter_input = soup.select_one("#chpcounter")
    if counter_input and counter_input.get("value"):
        try:
            expected_total = int(counter_input["value"].strip())
        except (TypeError, ValueError):
            expected_total = None

    return post_id, expected_total


def parse_list_style_entries(container: BeautifulSoup, series_url: str) -> list[tuple[Optional[int], str, str]]:
    entries: list[tuple[Optional[int], str, str]] = []
    seen_urls: set[str] = set()

    for li in container.select("li"):
        link = li.find("a", href=True)
        if not link:
            continue
        href = urljoin(series_url, link["href"])
        if href in seen_urls:
            continue
        seen_urls.add(href)
        title_text = link.get_text(strip=True)

        order_val: Optional[int] = None
        order_attr = li.get("order")
        if order_attr:
            try:
                order_val = int(order_attr)
            except ValueError:
                order_val = None

        entries.append((order_val, href, title_text))

    return entries


def parse_table_entries(container: BeautifulSoup, series_url: str) -> list[tuple[Optional[int], str, str]]:
    entries: list[tuple[Optional[int], str, str]] = []
    table = container.select_one("table#myTable")
    if not table:
        return entries

    seen_urls: set[str] = set()
    for row in table.select("tbody tr"):
        link = row.find("a", href=True)
        if not link:
            continue
        href = urljoin(series_url, link["href"])
        if href in seen_urls:
            continue
        seen_urls.add(href)
        title_text = link.get_text(strip=True)

        number_value: Optional[int] = None
        number_cell = row.find("td")
        if number_cell:
            text = number_cell.get_text(strip=True)
            first_token = text.split()[0] if text else ""
            if first_token:
                try:
                    number_value = int(first_token)
                except ValueError:
                    number_value = None

        entries.append((number_value, href, title_text))

    return entries


def collect_chapter_listings(
    scraper,
    series_url: str,
    retries: int,
    backoff: float,
    timeout: float,
    *,
    ui=None,
) -> tuple[list[ChapterListing], Optional[int]]:
    if ui:
        ui.update_status("Collecting chapter listings...", level="info")
        ui.update_detail(None)
    series_response = perform_request(
        scraper,
        "GET",
        series_url,
        retries=retries,
        backoff=backoff,
        timeout=timeout,
        purpose="Series page request",
        ui=ui,
    )
    post_id, expected_total = parse_series_metadata(series_response.text)

    toc_response = perform_request(
        scraper,
        "POST",
        "https://www.scribblehub.com/wp-admin/admin-ajax.php",
        retries=retries,
        backoff=backoff,
        timeout=timeout,
        purpose="TOC request",
        log_prefix="  ",
        data={"action": "wi_getreleases_pagination", "pagenum": "-1", "mypostid": post_id},
        referer=series_url,
        validator=lambda resp: bool(resp.text.strip()),
        ui=ui,
    )

    toc_html = toc_response.text.strip()
    soup = BeautifulSoup(toc_html, "html.parser")
    container = soup.select_one("div.wi_fic_table.main") or soup

    entries = parse_list_style_entries(container, series_url)
    if not entries:
        entries = parse_table_entries(container, series_url)

    if not entries:
        raise RuntimeError("No chapter links were detected in the table of contents.")

    entries.sort(
        key=lambda entry: (
            entry[0] if entry[0] is not None else float("inf"),
            entry[1],
        )
    )

    listings = [
        ChapterListing(position=index + 1, url=url, toc_title=title)
        for index, (_, url, title) in enumerate(entries)
    ]

    if expected_total and len(listings) != expected_total and ui:
        ui.log_event(
            f"Expected {expected_total} chapters but collected {len(listings)}.",
            level="warning",
        )

    return listings, expected_total


def normalize_text(raw_text: str) -> str:
    cleaned = (
        raw_text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
    )
    placeholder_pattern = re.escape(BR_PLACEHOLDER)
    single_newline_pattern = re.compile(
        rf"(?<!\n)(?<!{placeholder_pattern})\n(?!\n|{placeholder_pattern})"
    )
    cleaned = single_newline_pattern.sub(" ", cleaned)
    cleaned = cleaned.replace(f"\n{BR_PLACEHOLDER}\n", "\n")
    cleaned = cleaned.replace(BR_PLACEHOLDER, "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    lines = [line.rstrip() for line in cleaned.split("\n")]
    return "\n".join(lines).strip()


def remove_navigation_snippets(raw_text: str) -> str:
    navigation_keywords = {"previous", "next", "index", "advertisements", "shortcut:"}
    lines: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        lower_line = stripped.lower()
        if len(stripped) <= 30 and any(keyword in lower_line for keyword in navigation_keywords):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def extract_chapter_content(html: str, *, ui=None) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = ["#chp_raw", "#chapter-content", "div.chapter-content", "#chp_contents"]

    node = None
    for selector in selectors:
        candidate = soup.select_one(selector)
        if candidate and candidate.get_text(strip=True):
            node = candidate
            break

    if node is None:
        node = soup.body or soup
        if ui:
            ui.log_event("Falling back to <body> for chapter content extraction.", level="warning")
        else:
            print("    Warning: falling back to <body> for chapter content extraction.", flush=True)

    for br in node.find_all("br"):
        br.replace_with(f"\n{BR_PLACEHOLDER}\n")

    raw_body = node.get_text("\n")
    cleaned_body = remove_navigation_snippets(normalize_text(raw_body))
    if not cleaned_body:
        raise RuntimeError("Chapter body extraction resulted in empty text.")

    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else "Untitled Chapter"
    suffix = " \u2013 Scribble Hub"
    if title_text.endswith(suffix):
        title_text = title_text[: -len(suffix)]

    return title_text, cleaned_body
