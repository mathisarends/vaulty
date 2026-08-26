"""Start the daemon: `python -m daemon` or the `vaulty-daemon` script."""

import argparse
import asyncio
import logging
from pathlib import Path

from daemon.daemon import serve
from vaulty.config import DEFAULT_CONFIG_PATH, load_config, load_environment


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    load_environment()

    parser = argparse.ArgumentParser(prog="vaulty-daemon")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()

    try:
        asyncio.run(serve(load_config(args.config)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
