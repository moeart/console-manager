"""配置与设置读写模块。

配置文件保持与旧版完全兼容：
- config.yaml：控制台与服务配置（YAML）
- settings.json：程序设置（JSON）

写入采用原子写（先写临时文件再 os.replace），避免程序崩溃或断电
导致配置文件被写坏。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .constants import APP_DIR, CONFIG_FILE, SETTINGS_FILE

logger = logging.getLogger(__name__)


def _atomic_write(path: Path, data: str) -> None:
    """原子写入：先写同目录临时文件，再 os.replace 覆盖。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_name, path)
    except Exception:
        # 写失败时清理临时文件
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_config() -> dict[str, Any]:
    """加载 config.yaml。

    :return: {"consoles": {...}, "services": [...]}
    """
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            consoles = data.get("consoles") or {}
            services = data.get("services") or []
            logger.info("已加载配置: %s（控制台 %d 个，服务 %d 个）",
                        CONFIG_FILE, len(consoles), len(services))
            return {"consoles": consoles, "services": services}
        logger.info("未找到配置文件 %s，使用空配置", CONFIG_FILE)
    except Exception:
        logger.exception("加载配置失败，使用空配置")
    return {"consoles": {}, "services": []}


def save_config(consoles: dict, services: list) -> None:
    """保存控制台与服务配置到 config.yaml（原子写）。"""
    data = {"consoles": consoles, "services": services}
    text = yaml.dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    _atomic_write(CONFIG_FILE, text)
    logger.info("配置已保存到 %s", CONFIG_FILE)


def load_settings() -> dict[str, Any]:
    """加载 settings.json。"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            if isinstance(settings, dict):
                logger.info("已加载设置: %s", SETTINGS_FILE)
                return settings
    except Exception:
        logger.exception("加载设置失败，使用默认设置")
    return {}


def save_settings(settings: dict) -> None:
    """保存设置到 settings.json（原子写）。"""
    text = json.dumps(settings, indent=2, ensure_ascii=False)
    _atomic_write(SETTINGS_FILE, text)
