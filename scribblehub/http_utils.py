from __future__ import annotations

import time
from typing import Callable, Optional, TYPE_CHECKING

import cloudscraper
import requests

if TYPE_CHECKING:
    from .ui import ConsoleUI


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def create_scraper() -> cloudscraper.CloudScraper:
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    scraper.headers.update(DEFAULT_HEADERS)
    return scraper


def perform_request(
    scraper: cloudscraper.CloudScraper,
    method: str,
    url: str,
    *,
    retries: int,
    backoff: float,
    timeout: float,
    purpose: str,
    log_prefix: str = "",
    data: Optional[dict[str, str]] = None,
    referer: Optional[str] = None,
    validator: Optional[Callable[[requests.Response], bool]] = None,
    ui: Optional["ConsoleUI"] = None,
    silent: bool = False,
) -> requests.Response:
    last_error: Optional[Exception] = None
    if ui:
        ui.update_detail(None)
    for attempt in range(1, retries + 1):
        try:
            headers: dict[str, str] = {}
            if referer:
                headers["Referer"] = referer
            response = scraper.request(
                method=method,
                url=url,
                data=data,
                headers=headers or None,
                timeout=timeout,
            )
            response.raise_for_status()
            if validator and not validator(response):
                raise ValueError("Response failed validation")
            if ui and attempt > 1:
                ui.update_detail(None)
            return response
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == retries:
                break
            wait_time = max(0.5, backoff * attempt)
            message = str(exc).strip() or exc.__class__.__name__
            if ui:
                ui.update_detail(
                    f"{log_prefix}{purpose} attempt {attempt}/{retries} failed ({message}). "
                    f"Retrying in {wait_time:.1f}s...",
                    level="warning",
                )
            elif not silent:
                print(
                    f"{log_prefix}{purpose} attempt {attempt}/{retries} failed ({message}). "
                    f"Retrying in {wait_time:.1f}s...",
                    flush=True,
                )
            time.sleep(wait_time)
    if ui:
        ui.update_detail(
            f"{log_prefix}{purpose} failed after {retries} attempts.",
            level="error",
        )
        ui.log_event(
            f"{log_prefix}{purpose} failed after {retries} attempts. Aborting.",
            level="error",
        )
    raise RuntimeError(f"Unable to complete {purpose} for {url}") from last_error
