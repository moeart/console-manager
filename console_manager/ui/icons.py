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

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
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
    """按语义别名获取图标：自绘彩色图标优先，系统图标兜底。"""
    painter = _CUSTOM_PAINTERS.get(name)
    if painter is not None:
        return _custom_icon(name, painter)
    sp = _resolve_name(name)
    if sp is None:
        return QIcon()
    return _native_icon(sp)


# ---------------------------------------------------------------------------
# 自绘工具栏图标（统一 24px 画布 / 线宽 / 边距，彩色语义化）
# ---------------------------------------------------------------------------

_CANVAS = 24  # 逻辑画布（QIcon 按 DPR 自动渲染高分屏）
_STROKE = QColor("#3B3B3B")      # 中性图形描边色（近黑）
_ACCENT = QColor("#0078D4")      # Windows 强调蓝
_GREEN = QColor("#107C10")
_RED = QColor("#C50F1F")
_WFolder = QColor("#FFB900")     # 文件夹黄


def _pm_canvas(size: int) -> tuple[QPixmap, QPainter]:
    """开一块透明画布，预置抗锯齿与圆头画笔。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pm, p


def _stroke_pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _paint_new_console(p: QPainter, s: float) -> None:
    """新建控制台：终端窗口（>_ 命令提示符）。"""
    p.setPen(_stroke_pen(_STROKE, 1.8))
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 窗口圆角框
    p.drawRoundedRect(QRectF(2.5, 4, 19, 16), 2.5, 2.5)
    # >_ 提示符
    p.drawLine(QPointF(6.5, 9), QPointF(10, 12.5))
    p.drawLine(QPointF(10, 12.5), QPointF(6.5, 16))
    p.drawLine(QPointF(12.5, 16.5), QPointF(16.5, 16.5))


def _paint_add_service(p: QPainter, s: float) -> None:
    """添加服务：黄色文件夹 + 绿色加号（延续原 SP_FileDialogNewFolder 语义）。"""
    p.setPen(_stroke_pen(QColor("#B28700"), 1.4))
    p.setBrush(_WFolder)
    # 文件夹主体
    path = QPolygonF([
        QPointF(2.5, 6.5),
        QPointF(9, 6.5),
        QPointF(11, 9),
        QPointF(21.5, 9),
        QPointF(21.5, 19),
        QPointF(2.5, 19),
    ])
    p.drawPolygon(path)
    # 加号
    p.setPen(_stroke_pen(_GREEN, 2.2))
    p.drawLine(QPointF(16.5, 12), QPointF(16.5, 17))
    p.drawLine(QPointF(14, 14.5), QPointF(19, 14.5))


def _paint_play(p: QPainter, s: float) -> None:
    """启动：绿色实心播放三角。"""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_GREEN)
    p.drawPolygon(QPolygonF([
        QPointF(7, 4.5),
        QPointF(20, 12),
        QPointF(7, 19.5),
    ]))


def _paint_stop(p: QPainter, s: float) -> None:
    """停止：红色实心方块。"""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_RED)
    p.drawRoundedRect(QRectF(6, 6, 12, 12), 1.5, 1.5)


def _paint_reboot(p: QPainter, s: float) -> None:
    """重启：双箭头循环（Win11 风格），与刷新的单向环形箭头明显区分。"""
    p.setPen(_stroke_pen(_ACCENT, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 上半弧（左→右），末端画箭头
    p.drawArc(QRectF(5, 5.5, 14, 13), 15 * 16, 150 * 16)
    # 下半弧（右→左）
    p.drawArc(QRectF(5, 5.5, 14, 13), 195 * 16, 150 * 16)
    # 两个箭头头部（右上 / 左下）
    p.setBrush(_ACCENT)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(17.2, 4.2),
        QPointF(20.8, 6.2),
        QPointF(17.4, 8.6),
    ]))
    p.drawPolygon(QPolygonF([
        QPointF(6.8, 19.8),
        QPointF(3.2, 17.8),
        QPointF(6.6, 15.4),
    ]))


def _paint_refresh(p: QPainter, s: float) -> None:
    """刷新：单向环形箭头（顺时针，接近闭合圆）。"""
    p.setPen(_stroke_pen(_ACCENT, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(4.5, 4.5, 15, 15), 40 * 16, 300 * 16)
    # 箭头头部（顶部偏右）
    p.setBrush(_ACCENT)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(17.5, 2.5),
        QPointF(21.5, 5.5),
        QPointF(16.8, 8.0),
    ]))


def _paint_delete(p: QPainter, s: float) -> None:
    """删除：垃圾桶（中性描边，区别于移除服务的彩色语义）。"""
    p.setPen(_stroke_pen(_STROKE, 1.8))
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 桶身
    p.drawRoundedRect(QRectF(6, 7, 12, 13.5), 1.5, 1.5)
    # 桶口横线与提手
    p.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
    p.drawLine(QPointF(10, 4.5), QPointF(14, 4.5))
    # 内部两竖线
    p.drawLine(QPointF(10.2, 10), QPointF(10.2, 17.5))
    p.drawLine(QPointF(13.8, 10), QPointF(13.8, 17.5))


def _paint_remove(p: QPainter, s: float) -> None:
    """移除服务：垃圾桶 + 红色减号（与"删除控制台"区分）。"""
    p.setPen(_stroke_pen(_STROKE, 1.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(5, 6.5, 10.5, 12), 1.5, 1.5)
    p.drawLine(QPointF(3.5, 6.5), QPointF(17, 6.5))
    p.drawLine(QPointF(8, 4.2), QPointF(11.5, 4.2))
    p.drawLine(QPointF(7.6, 9.5), QPointF(7.6, 15.5))
    p.drawLine(QPointF(10.6, 9.5), QPointF(10.6, 15.5))
    # 红色减号
    p.setPen(_stroke_pen(_RED, 2.2))
    p.drawLine(QPointF(15, 15.5), QPointF(21, 15.5))


_CUSTOM_PAINTERS: dict[str, function] = {
    "new_console": _paint_new_console,
    "add_service": _paint_add_service,
    "play": _paint_play,
    "stop": _paint_stop,
    "reboot": _paint_reboot,
    "refresh": _paint_refresh,
    "delete": _paint_delete,
    "remove": _paint_remove,
}


@lru_cache(maxsize=32)
def _custom_icon(name: str, painter: function) -> QIcon:
    """按名称缓存自绘图标（含 1x/2x 双分辨率）。"""
    icon_obj = QIcon()
    for dpr in (1, 2):
        size = int(_CANVAS * dpr)
        pm, p = _pm_canvas(size)
        p.scale(size / _CANVAS, size / _CANVAS)
        painter(p, _CANVAS)
        p.end()
        icon_obj.addPixmap(pm)
    return icon_obj


def status_icon(status: str) -> QIcon:
    """按运行状态获取圆点图标（running 绿 / stopped 灰 / error 红）。"""
    return _dot_icon(status_color(status))


# ---------------------------------------------------------------------------
# 状态形状图标（绿色播放三角 / 红色方块），服务列表首列使用
# ---------------------------------------------------------------------------

# 渲染尺寸（16px 与表格行高匹配）
_SHAPE_SIZE = 16


def _shape_pixmap(kind: str, color: str, size: int = _SHAPE_SIZE) -> QPixmap:
    """绘制状态形状：play=实心三角 / stop=实心方块 / unknown=空心圆环。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    m = 2  # 边距
    if kind == "play":
        tri = QRectF(m, m, size - 2 * m, size - 2 * m)
        p.drawPolygon(
            QPolygonF([
                QPointF(tri.left(), tri.top()),
                QPointF(tri.right(), tri.center().y()),
                QPointF(tri.left(), tri.bottom()),
            ])
        )
    elif kind == "stop":
        s = size - 2 * m
        p.drawRect(QRectF(m + 1, m + 1, s - 2, s - 2))
    else:  # unknown：灰色空心圆环
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QColor(color))
        p.drawEllipse(QRectF(m, m, size - 2 * m - 1, size - 2 * m - 1))
    p.end()
    return pm


@lru_cache(maxsize=32)
def _shape_icon(kind: str, color: str) -> QIcon:
    return QIcon(_shape_pixmap(kind, color))


def status_shape_icon(status: str) -> QIcon:
    """运行状态 → 形状图标（服务列表首列）。

    running → 绿色播放三角；stopped/error → 红色方块；其他 → 灰色圆环。
    """
    from .theme import status_color as _status_color

    if status == "running":
        return _shape_icon("play", _status_color("running"))
    if status in ("stopped", "error"):
        return _shape_icon("stop", _status_color("stopped"))
    return _shape_icon("unknown", "#767676")


# ---------------------------------------------------------------------------
# 重启图标（双箭头循环，与"刷新"的单向环形箭头明显区分）
# ---------------------------------------------------------------------------

def reboot_icon(size: int = 16) -> QIcon:
    """重启图标：与工具栏"重启"按钮同一画法（双箭头循环）。"""
    return _custom_icon("reboot", _paint_reboot)


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
    _shape_icon.cache_clear()
    _custom_icon.cache_clear()
