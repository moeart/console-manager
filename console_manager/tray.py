"""系统托盘管理模块。

使用 QSystemTrayIcon 重写，与主窗口同线程运行，
彻底解决旧版 pystray 跨线程操作 tkinter 控件导致的随机崩溃问题。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QObject, Qt, QRectF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


logger = logging.getLogger(__name__)


class TrayManager(QObject):
    """系统托盘管理器（QSystemTrayIcon 组合封装）。

    与主窗口运行在同一 Qt 事件循环线程中，菜单回调直接调用
    ProcessManager / ServiceManager 方法（内部已保证不阻塞 UI），
    不再创建子线程，彻底根治旧版 pystray 跨线程崩溃问题。

    菜单实时同步链路：
      1. services_updated 信号 → rebuild_menu（后台刷新完成）
      2. on_console_state_changed() → rebuild_menu（控制台启停）
      3. aboutToShow 信号 → rebuild_menu（右键打开前，微秒级）+ refresh_async
    """

    def __init__(
        self,
        process_manager: Any,
        service_manager: Any,
        toggle_window: Callable[[], None],
        quit_app: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._process_manager = process_manager
        self._service_manager = service_manager
        self._toggle_window = toggle_window
        self._quit_app = quit_app

        # --- 图标准备 ---
        base_pixmap = self._load_base_pixmap()
        self._base_pixmap = base_pixmap
        self._refresh_state_icons()

        # --- 托盘实例 ---
        self._tray = QSystemTrayIcon(self._icon_stopped, parent=self)
        self._tray.setToolTip("控制台管理器\n运行中: 0/0")
        self._tray.activated.connect(self._on_activated)

        # --- 菜单（持久化，clear + repopulate 方式重建） ---
        self._menu: QMenu | None = None
        self.rebuild_menu()

        # --- 信号连接：服务状态后台刷新完成时自动重建菜单 ---
        if hasattr(self._service_manager, "services_updated"):
            try:
                self._service_manager.services_updated.connect(
                    self._on_services_updated
                )
            except Exception:
                logger.debug("连接 services_updated 信号失败", exc_info=True)

    # ------------------------------------------------------------------
    #  图标
    # ------------------------------------------------------------------

    @staticmethod
    def _get_app_dir() -> Path:
        """获取应用根目录。"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).resolve().parent.parent

    def _load_base_pixmap(self) -> QPixmap:
        """加载基础图标 pixmap；文件不存在时用 QPainter 绘制默认图标。"""
        app_dir = self._get_app_dir()
        for filename in ("icon.png", "icon.ico"):
            path = app_dir / filename
            if path.exists():
                pm = QPixmap(str(path))
                if not pm.isNull():
                    return pm
                logger.debug("图标文件 %s 解析失败", path)

        # 绘制默认图标：64×64 深色圆角方块 + 蓝色 ">_" 终端符号
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 深色圆角方块 #1E293B
        path = QPainterPath()
        path.addRoundedRect(QRectF(4, 4, 56, 56), 12, 12)
        painter.setBrush(QColor("#1E293B"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # 蓝色 ">_" 终端符号 #3B82F6
        painter.setPen(QColor("#3B82F6"))
        font = QFont("Consolas", 22, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(4, 4, 56, 56), Qt.AlignmentFlag.AlignCenter, ">_"
        )
        painter.end()
        return pm

    @staticmethod
    def _make_state_icon(base: QPixmap, dot_color: str) -> QIcon:
        """在基础 pixmap 右下角叠加 12px 状态圆点生成 QIcon。"""
        pm = base.copy()
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(dot_color))
        # 半透明白色描边，保证在任意任务栏底色上可见
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
        painter.drawEllipse(QRectF(46, 46, 12, 12))
        painter.end()
        return QIcon(pm)

    def _refresh_state_icons(self) -> None:
        """重建托盘状态色图标（运行绿 / 停止灰）。"""
        from .ui.theme import status_color

        self._icon_running = self._make_state_icon(
            self._base_pixmap, status_color("running")
        )
        self._icon_stopped = self._make_state_icon(
            self._base_pixmap, status_color("stopped")
        )

    def on_theme_changed(self) -> None:
        """兼容接口：原生外观下无需处理主题切换。"""

    # ------------------------------------------------------------------
    #  公开 API
    # ------------------------------------------------------------------

    def update_icon_state(self, running: int, total: int) -> None:
        """根据运行控制台数量切换托盘图标状态并更新 tooltip。

        Args:
            running: 当前运行中的控制台数量。
            total: 控制台总数。
        """
        if running > 0:
            self._tray.setIcon(self._icon_running)
        else:
            self._tray.setIcon(self._icon_stopped)
        self.update_tooltip(running, total)

    def update_tooltip(self, running_count: int, total: int) -> None:
        """更新托盘 tooltip。"""
        self._tray.setToolTip(
            f"控制台管理器\n运行中: {running_count}/{total}"
        )

    def on_console_state_changed(self, name: str) -> None:
        """控制台状态变化回调（由主窗口调用），重建菜单。

        Args:
            name: 发生状态变化的控制台名称。
        """
        self.rebuild_menu()

    def rebuild_menu(self) -> None:
        """重建托盘菜单（从缓存快照立即构建，微秒级，不阻塞）。

        采用 clear + repopulate 策略：持久 QMenu 不反复创建销毁，
        旧 QAction 由 Qt 父子机制自动释放，无内存泄漏。
        """
        if self._menu is None:
            self._menu = QMenu()
            self._menu.aboutToShow.connect(self._on_menu_about_to_show)
            self._tray.setContextMenu(self._menu)

        self._menu.clear()

        # --- 显示/隐藏主窗口 ---
        act = self._menu.addAction("显示 / 隐藏主窗口")
        act.triggered.connect(lambda _: self._toggle_window())

        self._menu.addSeparator()

        # --- 服务菜单 ---
        self._build_service_menu()

        self._menu.addSeparator()

        # --- 控制台菜单 ---
        self._build_console_menu()

        self._menu.addSeparator()

        # --- 全局操作 ---
        act = self._menu.addAction("启动所有控制台")
        act.triggered.connect(lambda _: self._on_start_all())

        act = self._menu.addAction("停止所有控制台")
        act.triggered.connect(lambda _: self._on_stop_all())

        self._menu.addSeparator()

        # --- 退出 ---
        act = self._menu.addAction("退出")
        act.triggered.connect(lambda _: self._quit_app())

    def show(self) -> None:
        """显示托盘图标。系统托盘不可用时仅打日志警告。"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统托盘不可用，托盘图标可能无法显示")
        self._tray.show()

    def hide(self) -> None:
        """隐藏托盘图标。"""
        self._tray.hide()

    def shutdown(self) -> None:
        """退出前清理：隐藏图标并释放菜单资源。"""
        self._tray.hide()
        if self._menu is not None:
            self._menu.deleteLater()
            self._menu = None
        self._tray.deleteLater()

    # ------------------------------------------------------------------
    #  菜单构建
    # ------------------------------------------------------------------

    def _build_service_menu(self) -> None:
        """构建服务子菜单（从 service_manager.statuses() 缓存快照）。"""
        service_menu = self._menu.addMenu("服务")

        try:
            statuses = self._service_manager.statuses()
        except Exception:
            logger.debug("获取服务状态快照失败", exc_info=True)
            statuses = []

        if not statuses:
            act = service_menu.addAction("暂无服务")
            act.setEnabled(False)
            return

        for svc in statuses:
            name: str = svc.get("name", "未知")
            display: str = svc.get("display_name", name)
            status: str = svc.get("status", "unknown")

            if status == "running":
                prefix = "▶ "
            elif status == "stopped":
                prefix = "■ "
            else:
                prefix = "◾ "

            is_running = status == "running"
            svc_submenu = service_menu.addMenu(f"{prefix}{display}")

            act_start = svc_submenu.addAction("启动")
            act_start.setEnabled(not is_running)
            act_start.triggered.connect(
                lambda _, n=name: self._on_service_start(n)
            )

            act_stop = svc_submenu.addAction("停止")
            act_stop.setEnabled(is_running)
            act_stop.triggered.connect(
                lambda _, n=name: self._on_service_stop(n)
            )

            act_restart = svc_submenu.addAction("重启")
            act_restart.setEnabled(is_running)
            act_restart.triggered.connect(
                lambda _, n=name: self._on_service_restart(n)
            )

    def _build_console_menu(self) -> None:
        """构建控制台子菜单（从 process_manager.runners 缓存快照）。"""
        console_menu = self._menu.addMenu("控制台")

        try:
            runners = self._process_manager.runners
        except Exception:
            logger.debug("获取控制台列表失败", exc_info=True)
            runners = {}

        if not runners:
            act = console_menu.addAction("暂无控制台")
            act.setEnabled(False)
            return

        for name, runner in runners.items():
            is_running = getattr(runner, "is_running", False)

            if is_running:
                prefix = "▶ "
            else:
                prefix = "■ "

            console_submenu = console_menu.addMenu(f"{prefix}{name}")

            act_start = console_submenu.addAction("启动")
            act_start.setEnabled(not is_running)
            act_start.triggered.connect(
                lambda _, n=name: self._on_console_start(n)
            )

            act_stop = console_submenu.addAction("停止")
            act_stop.setEnabled(is_running)
            act_stop.triggered.connect(
                lambda _, n=name: self._on_console_stop(n)
            )

            act_restart = console_submenu.addAction("重启")
            act_restart.setEnabled(is_running)
            act_restart.triggered.connect(
                lambda _, n=name: self._on_console_restart(n)
            )

    # ------------------------------------------------------------------
    #  信号处理
    # ------------------------------------------------------------------

    def _on_activated(
        self, reason: QSystemTrayIcon.ActivationReason
    ) -> None:
        """托盘图标激活事件。左键单击 → 切换窗口可见性。"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _on_menu_about_to_show(self) -> None:
        """菜单即将显示：用缓存快照重建（微秒级）+ 触发异步刷新。

        绝不做任何耗时操作或子进程调用。
        """
        self.rebuild_menu()
        try:
            self._service_manager.refresh_async()
        except Exception:
            logger.debug("触发服务状态异步刷新失败", exc_info=True)

    def _on_services_updated(self) -> None:
        """服务状态后台刷新完成，重建菜单。"""
        self.rebuild_menu()

    # ------------------------------------------------------------------
    #  操作回调（直接调用管理器方法，不阻塞）
    # ------------------------------------------------------------------

    def _on_service_start(self, name: str) -> None:
        self._service_manager.start(name)

    def _on_service_stop(self, name: str) -> None:
        self._service_manager.stop(name)

    def _on_service_restart(self, name: str) -> None:
        self._service_manager.restart(name)

    def _on_console_start(self, name: str) -> None:
        self._process_manager.start_console(name)

    def _on_console_stop(self, name: str) -> None:
        self._process_manager.stop_console(name)

    def _on_console_restart(self, name: str) -> None:
        self._process_manager.restart_console(name)

    def _on_start_all(self) -> None:
        self._process_manager.start_all()

    def _on_stop_all(self) -> None:
        self._process_manager.stop_all()
