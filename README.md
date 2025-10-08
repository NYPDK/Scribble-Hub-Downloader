# ScribbleHub Downloader

Terminal helper that mirrors an entire ScribbleHub series into chapter bundles you can read offline. It drives a polite `cloudscraper` session through ScribbleHub's AJAX table of contents, walks every chapter in order, and writes tidy plain-text chunks while keeping you up to date with a rich progress display.

## Quick Start
1. Ensure Python 3.9+ is available (`python --version`).
2. Install runtime dependencies:

   ```powershell
   python -m pip install cloudscraper requests beautifulsoup4 colorama
   ```

3. Run the downloader with a series URL:

   ```powershell
   python scribblehub_downloader.py https://www.scribblehub.com/series/12345/example-story/
   ```

The first run creates an `output/` directory next to the script and begins writing bundled text files.

## Usage

```powershell
python scribblehub_downloader.py <scribblehub-series-url> [options]
```

### Options
| Flag | Description | Default |
| ---- | ----------- | ------- |
| `url` (positional) | ScribbleHub series URL, e.g. `https://www.scribblehub.com/series/.../` | required |
| `-o`, `--output` | Destination directory created if missing. | `output/` |
| `-g`, `--group-size` | Chapters per text file. Filenames follow `####-####.txt`. | `15` |
| `--retries` | Attempts per HTTP request before aborting. | `3` |
| `--backoff` | Base wait (seconds) between retry attempts. | `3.0` |
| `--delay` | Optional pause (seconds) after each chapter download. | `5` |
| `--timeout` | Request timeout (seconds) for the scraper session. | `60.0` |

Invalid combinations (negative delays, zero retries, output paths that are regular files, etc.) are rejected up front with a clear message.

### Example Run

```powershell
python scribblehub_downloader.py https://www.scribblehub.com/series/12345/example-story/ `
    --output "My Story" `
    --group-size 10 `
    --delay 3
```

The command above writes bundles such as `0001-0010.txt`, `0011-0020.txt`, each holding the chapter title, source URL, and cleaned body text with divider lines between chapters.

## Output Layout
- `output/` (or your chosen directory) is created automatically.
- Files are numbered by the first and last chapter index they contain.
- Each file is UTF-8 encoded and formatted as:

  ```text
  Chapter 1: Chapter Title
  URL: https://www.scribblehub.com/read/...

  ...chapter body...
  --------------------------------------------------------------------------------
  Chapter 2: Next Chapter
  URL: ...
  ```

  The trailing separator is omitted after the final chapter in the bundle so files stay clean.

## Progress UI
- Uses a dedicated `ConsoleUI` that renders color-coded boxes on terminals with ANSI support.
- Falls back to a single-line plain output when ANSI is unavailable (e.g. basic Windows consoles).
- Shows current chapter, percentage, elapsed time, rolling ETA, and remaining chapters.
- Logs significant events (chunk writes, warnings, errors) without mangling the progress area.
- Handles `Ctrl+C` gracefully by flushing the UI and exiting with `"Download interrupted by user."`.

## Under the Hood
- Retrieves the series page to discover the ScribbleHub post ID, then calls the AJAX endpoint (`wi_getreleases_pagination`) to pull the complete table of contents in one request.
- Deduplicates and sorts listings whether the site returns list-based or table-based markup.
- Downloads chapters with automatic retries and exponential backoff, reusing a single `cloudscraper` session with desktop headers.
- Cleans chapter HTML by replacing `<br>` tags with hard line breaks, trimming navigation boilerplate, and normalizing whitespace for readable plain text.
- Writes chunked files atomically once a bundle reaches your configured size or the run finishes.

## Troubleshooting
- If the parser cannot find the chapter list, check the logs; ScribbleHub layout changes may require parser tweaks.
- Increase `--delay` to be extra gentle if you encounter rate limiting.
- Raise `--retries` or `--timeout` for unstable connections.
- Install `colorama` on Windows to enable ANSI colors in otherwise plain consoles.

## Responsible Use
Respect ScribbleHub's terms of service and individual authors. Stick to reasonable request delays, keep personal backups, and avoid heavy automation that could burden the platform.
