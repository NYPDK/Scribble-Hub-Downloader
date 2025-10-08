from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Sequence

from .http_utils import create_scraper, perform_request
from .models import Chapter, ChapterListing
from .parsing import collect_chapter_listings, extract_chapter_content
from .ui import ConsoleUI


def write_chunk(chunk: Sequence[Chapter], output_dir: Path) -> Path:
    start_index = chunk[0].index
    end_index = chunk[-1].index
    filename = output_dir / f"{start_index:04d}-{end_index:04d}.txt"

    lines: list[str] = []
    total = len(chunk)
    for offset, chapter in enumerate(chunk):
        lines.append(f"Chapter {chapter.index}: {chapter.title}")
        lines.append(f"URL: {chapter.url}")
        lines.append("")
        lines.append(chapter.body)
        if offset != total - 1:
            lines.append("")
            lines.append("-" * 80)
            lines.append("")

    content = "\n".join(lines).strip() + "\n"
    filename.write_text(content, encoding="utf-8")
    return filename


def fetch_chapter_with_retry(
    scraper,
    listing: ChapterListing,
    chapter_index: int,
    retries: int,
    backoff: float,
    timeout: float,
    *,
    ui: Optional[ConsoleUI] = None,
    delay: float = 0.0,
) -> Chapter:
    response = perform_request(
        scraper,
        "GET",
        listing.url,
        retries=retries,
        backoff=backoff,
        timeout=timeout,
        purpose=f"Chapter {chapter_index} request",
        log_prefix="    ",
        ui=ui,
    )
    title, body = extract_chapter_content(response.text, ui=ui)
    if delay:
        time.sleep(delay)
    return Chapter(index=chapter_index, url=listing.url, title=title, body=body)


def download_series(
    series_url: str,
    output_directory: Path,
    group_size: int,
    retries: int,
    backoff: float,
    delay: float,
    timeout: float,
    *,
    ui: Optional[ConsoleUI] = None,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    internal_ui = ui or ConsoleUI()
    should_finalize = ui is None
    scraper = create_scraper()

    try:
        listings, expected_total = collect_chapter_listings(
            scraper=scraper,
            series_url=series_url,
            retries=retries,
            backoff=backoff,
            timeout=timeout,
            ui=internal_ui,
        )

        total_chapters = len(listings)
        internal_ui.log_event(f"Found {total_chapters} chapters to download.", level="success")
        internal_ui.update_status("Preparing downloads...", level="info")
        internal_ui.update_detail(None)

        chunk: list[Chapter] = []
        written = 0
        start_monotonic = time.perf_counter()
        start_wall = time.time()
        progress_bar_width = 24

        for idx, listing in enumerate(listings, start=1):
            title_preview = listing.toc_title
            if len(title_preview) > 36:
                title_preview = title_preview[:33] + "..."
            internal_ui.update_status(
                f"Downloading chapter {idx}/{total_chapters}: {title_preview}",
                level="info",
            )

            chapter = fetch_chapter_with_retry(
                scraper,
                listing=listing,
                chapter_index=idx,
                retries=retries,
                backoff=backoff,
                timeout=timeout,
                ui=internal_ui,
                delay=delay,
            )
            chunk.append(chapter)

            now = time.perf_counter()
            elapsed = now - start_monotonic
            average = elapsed / idx if idx else 0.0
            remaining = max(total_chapters - idx, 0) * average
            progress_fraction = idx / total_chapters if total_chapters else 0.0
            filled = int(progress_fraction * progress_bar_width)
            bar = "#" * filled + "-" * (progress_bar_width - filled)
            eta_timestamp = start_wall + elapsed + remaining
            eta_str = time.strftime("%I:%M %p", time.localtime(eta_timestamp))
            progress_line = (
                f"[{bar}] {progress_fraction * 100:6.2f}% ({idx}/{total_chapters}) "
                f"{title_preview:<36} elapsed {elapsed:7.1f}s"
            )
            if idx >= 5:
                progress_line += f" | remaining ~ {remaining:7.1f}s | ETA {eta_str}"
            else:
                progress_line += " | estimating ETA..."
            internal_ui.update_progress(progress_line)

            remaining_chapters = max(total_chapters - idx, 0)
            internal_ui.update_detail(
                f"Remaining downloads: {remaining_chapters}",
                level="muted" if remaining_chapters else "info",
            )

            if len(chunk) == group_size or idx == total_chapters:
                internal_ui.update_progress(None)
                output_path = write_chunk(chunk, output_directory)
                written += len(chunk)
                internal_ui.log_event(
                    f"Saved {output_path.name} ({len(chunk)} chapters; {written}/{total_chapters} complete)",
                    level="success",
                )
                chunk = []

        total_elapsed = time.perf_counter() - start_monotonic
        internal_ui.update_status("Download complete", level="success")
        internal_ui.update_progress(None)
        internal_ui.update_detail(None)
        internal_ui.log_event(
            f"All chapters downloaded in {total_elapsed:,.1f}s (~{total_elapsed/60:.2f} min).",
            level="success",
        )
    finally:
        if should_finalize:
            internal_ui.finalize()
