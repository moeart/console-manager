from __future__ import annotations

"""
主题兼容层。

界面已回归 Qt/Windows 原生外观（不加载任何自定义 QSS），本模块只保留
状态色常量与少量兼容函数，供托盘图标圆点、列表状态图标等继续使用。
"""

import logging

logger = logging.getLogger(__name__)

# 兼容常量（历史调用点仍在引用）
THEME_DARK = "dark"
THEME_LIGHT_MODE = "light"
THEME_AUTO = "auto"


def set_theme_mode(mode: str) -> None:
    """兼容接口：不再有任何主题可切换，忽略。"""


def get_theme_mode() -> str:
    """兼容接口：恒返回默认值。"""
    return THEME_DARK


def apply_theme(app=None) -> None:
    """兼容接口：使用 Qt 默认样式（Windows 上即原生外观），无需处理。"""


def get_active_theme() -> dict[str, str]:
    """状态色表（托盘圆点 / 列表状态图标使用）。

    停止态用红色突出（Win 原生深红 #C50F1F），运行态为系统绿。
    """
    return {
        "running": "#107C10",   # 系统绿
        "stopped": "#C50F1F",   # 停止=红（用户要求突出区别）
        "starting": "#B26A00",  # 启动中=橙（过渡态）
        "stopping": "#B26A00",
        "error": "#C50F1F",
        "warning": "#B26A00",
        "success": "#107C10",
        "primary": "#0078D4",
        "text": "#1F1F1F",
        "text_disabled": "#767676",
        "text_light": "#FFFFFF",
    }


def is_dark_active() -> bool:
    return False


def on_system_scheme_changed() -> bool:
    """兼容接口：无主题跟随逻辑，恒返回未变化。"""
    return False


def status_color(status: str) -> str:
    """运行状态 → 状态色。"""
    return get_active_theme().get(status, "#767676")


def status_text_zh(status: str) -> str:
    """运行状态 → 中文文案。"""
    return {
        "running": "运行中",
        "stopped": "已停止",
        "starting": "启动中",
        "stopping": "停止中",
        "error": "异常",
        "unknown": "未知",
    }.get(status, "未知")
