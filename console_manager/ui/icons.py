from __future__ import annotations

"""
图标封装（基于 QStyle.standardIcon 系统原生图标）。

- ``icon(name)``：按语义别名取系统图标；无对应图标返回空 QIcon，界面
  自动退化为纯文字（标准 Win32 程序的常见做法）。
- ``set_button_icon()`` / ``refresh_buttons()``：兼容接口，按钮图标只设置
  一次即可（原生外观下图标不随主题变化）。
- ``status_icon(status)``：状态圆点图标（运行=绿色 / 停止=灰色）。
"""

import logging
from functools import lru_cache

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle

from .theme import status_color

logger = logging.getLogger(__name__)

# 语义别名 → QStyle.StandardPixmap
_ICON_MAP: dict[str, QStyle.StandardPixmap] = {
    "play":       QStyle.StandardPixmap.SP_MediaPlay,
    "pause":      QStyle.StandardPixmap.SP_MediaPause,
    "stop":       QStyle.StandardPixmap.SP_MediaStop,
    "restart":    QStyle.StandardPixmap.SP_BrowserReload,
    "refresh":    QStyle.StandardPixmap.SP_BrowserReload,
    "settings":   QStyle.StandardPixmap.SP_FileDialogInfoView,
    "info":       QStyle.StandardPixmap.SP_MessageBoxInformation,
    "question":   QStyle.StandardPixmap.SP_MessageBoxQuestion,
    "warning":    QStyle.StandardPixmap.SP_MessageBoxWarning,
    "critical":   QStyle.StandardPixmap.SP_MessageBoxCritical,
    "add":        QStyle.StandardPixmap.SP_FileDialogNewFolder,
    "delete":     QStyle.StandardPixmap.SP_TrashIcon,
    "close":      QStyle.StandardPixmap.SP_DialogCloseButton,
    "check":      QStyle.StandardPixmap.SP_DialogOkButton,
    "quit":       QStyle.StandardPixmap.SP_DialogCloseButton,
    "open":       QStyle.StandardPixmap.SP_DialogOpenButton,
    "save":       QStyle.StandardPixmap.SP_DialogSaveButton,
    "services":   QStyle.StandardPixmap.SP_ComputerIcon,
    "console":    QStyle.StandardPixmap.SP_DesktopIcon,
    "folder":     QStyle.StandardPixmap.SP_DirIcon,
    "folder_open": QStyle.StandardPixmap.SP_DirOpenIcon,
    "file":       QStyle.StandardPixmap.SP_FileIcon,
    "arrow_up":   QStyle.StandardPixmap.SP_ArrowUp,
    "arrow_down": QStyle.StandardPixmap.SP_ArrowDown,
    "list":       QStyle.StandardPixmap.SP_FileDialogListView,
}


def is_available() -> bool:
    """QApplication 已创建时恒为 True。"""
    return QApplication.instance() is not None


@lru_cache(maxsize=64)
def _native_icon(sp: QStyle.StandardPixmap) -> QIcon:
    """取系统原生图标（带缓存；app 未创建或图标无效时返回空 QIcon）。"""
    app = QApplication.instance()
    if app is None:
        return QIcon()
    style = app.style()
    if style is None:
        return QIcon()
    return style.standardIcon(sp)


def _resolve_name(name: str) -> QStyle.StandardPixmap | None:
    """语义别名 → StandardPixmap；未知返回 None（界面降级为纯文字）。"""
    return _ICON_MAP.get(name)


def icon(name: str, color: str | None = None) -> QIcon:
    """按语义别名获取系统原生图标。"""
    sp = _resolve_name(name)
    if sp is None:
        return QIcon()
    return _native_icon(sp)


def status_icon(status: str) -> QIcon:
    """按运行状态获取圆点图标（running 绿 / stopped 灰 / error 红）。"""
    return _dot_icon(status_color(status))


def _dot_pixmap(color: str, size: int = 12) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)
    p.end()
    return pm


@lru_cache(maxsize=32)
def _dot_icon(color: str) -> QIcon:
    return QIcon(_dot_pixmap(color))


# ---------------------------------------------------------------------------
# 兼容接口：登记/刷新机制保留签名，原生外观下图标无需随主题重建
# ---------------------------------------------------------------------------

def set_button_icon(button, name: str, color: str = "auto") -> None:
    """给按钮设置系统图标（保留登记以兼容 refresh_buttons 调用）。"""
    button.setIcon(icon(name))


def refresh_buttons() -> None:
    """兼容接口：原生外观下图标固定，无需重建。"""


def refresh_all() -> None:
    """兼容接口：清理图标缓存。"""
    _native_icon.cache_clear()
    _dot_icon.cache_clear()
