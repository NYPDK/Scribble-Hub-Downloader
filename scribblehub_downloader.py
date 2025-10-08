from __future__ import annotations

from pathlib import Path

from scribblehub import download_series, parse_args, validate_args
from scribblehub.ui import ConsoleUI


def main() -> None:
    args = parse_args()
    validate_args(args)

    output_dir = Path(args.output)
    ui = ConsoleUI()

    try:
        download_series(
            series_url=args.url,
            output_directory=output_dir,
            group_size=args.group_size,
            retries=args.retries,
            backoff=args.backoff,
            delay=args.delay,
            timeout=args.timeout,
            ui=ui,
        )
    except KeyboardInterrupt:
        ui.log_event("Download interrupted by user.", level="error")
        raise SystemExit("Download interrupted by user.")
    except Exception as exc:
        ui.log_event(str(exc), level="error")
        raise SystemExit(str(exc)) from None
    finally:
        ui.finalize()


if __name__ == "__main__":
    main()
