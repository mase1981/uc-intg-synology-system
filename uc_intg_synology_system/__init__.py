"""
Synology System Integration for Unfolded Circle Remote Two/3.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path


def _find_driver_json() -> str:
    here = Path(__file__).parent.absolute()
    candidates = [here.parent / "driver.json", here / "driver.json", Path.cwd() / "driver.json"]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(Path(bundle) / "driver.json")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


try:
    with open(_find_driver_json(), "r", encoding="utf-8") as _file:
        __version__ = json.load(_file).get("version", "0.0.0")
except (FileNotFoundError, json.JSONDecodeError):
    __version__ = "0.0.0"

__author__ = "Meir Miyara"
__email__ = "meir.miyara@gmail.com"
__license__ = "MPL-2.0"
__all__ = ["__version__", "main"]

_LOG = logging.getLogger(__name__)


async def main():
    from ucapi import DeviceStates
    from ucapi_framework import get_config_path

    from uc_intg_synology_system.config import SynologyConfig, SynologyConfigManager, migrate_legacy_config
    from uc_intg_synology_system.driver import SynologyDriver
    from uc_intg_synology_system.setup_flow import SynologySetupFlow

    level = os.getenv("UC_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s",
    )
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    _LOG.info("Starting Synology System Integration v%s", __version__)

    driver = SynologyDriver()
    config_path = get_config_path(driver.api.config_dir_path or "")
    migrate_legacy_config(config_path)

    config_manager = SynologyConfigManager(
        config_path,
        add_handler=driver.on_device_added,
        remove_handler=driver.on_device_removed,
        config_class=SynologyConfig,
    )
    driver.config_manager = config_manager

    setup_handler = SynologySetupFlow.create_handler(driver)
    await driver.api.init(_find_driver_json(), setup_handler)
    await driver.register_all_device_instances(connect=False)

    count = len(list(config_manager.all()))
    await driver.api.set_device_state(DeviceStates.CONNECTED if count > 0 else DeviceStates.DISCONNECTED)
    _LOG.info("Synology System integration started - %d device(s) configured", count)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
