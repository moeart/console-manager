"""主窗口（标准 Win32 风格布局）。

布局（原生标题栏 + 菜单栏 + 工具栏 + 标签页 + 状态栏）：

    +--------------------------------------------------+
    | [原生标题栏]                                       |
    |--------------------------------------------------|
    | 文件   编辑   视图   设置                          |  ← QMenuBar
    |--------------------------------------------------|
    | [新建▾] [启动] [停止] [重启] [删除] [刷新]  [搜索框…]  |  ← QToolBar
    |--------------------------------------------------|
    | QTabWidget                                       |
    |  ├─ 服务管理                                      |
    |  └─ 控制台 × N                                    |
    |--------------------------------------------------|
    | 状态栏：就绪信息 | 控制台计数 | 运行计数           |
    +--------------------------------------------------+

职责：
- 加载/保存配置，创建 ProcessManager / ServiceManager / TrayManager
- QTabWidget 承载服务页与各控制台页，标签右侧显示运行状态
- 接线所有信号（进程状态/输出、服务状态、托盘回调）
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QWidget,
)

from .. import config as config_store
from ..process_manager import ProcessManager
from ..service_manager import ServiceManager
from ..tray import TrayManager
from . import icons
from .console_view import ConsoleView
from .dialogs import AddServiceDialog, ConsoleEditDialog, SettingsDialog
from .service_view import ServiceView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("控制台管理器")
        self.resize(1100, 640)
        self._set_window_icon()

        # ---- 数据 ----
        self._config = config_store.load_config()
        self._settings = config_store.load_settings()
        self._consoles: dict[str, dict] = dict(self._config.get("consoles", {}))

        # ---- 管理器 ----
        self.process_manager = ProcessManager(self)
        self.process_manager.state_changed_any.connect(self._on_any_console_state)
        self.process_manager.load_consoles(self._consoles)

        self.service_manager = ServiceManager(self._config.get("services", []), self)
        self.service_manager.services_updated.connect(self._on_services_updated)
        self.service_manager.action_finished.connect(self._on_service_action)

        # ---- UI ----
        self._console_views: dict[str, ConsoleView] = {}
        self._tab_index_console: dict[str, int] = {}
        self._build_ui()

        # ---- 托盘 ----
        self.tray = TrayManager(
            self.process_manager,
            self.service_manager,
            self.toggle_window,
            self.quit_app,
            self,
        )
        self.tray.show()

        # ---- 状态栏 ----
        self._refresh_counts()
        self.statusBar().showMessage("就绪")

        # ---- 服务周期刷新（托盘/表格状态同步的根基）----
        self.service_manager.start_periodic_refresh(30_000, parent_widget=self)
        self.service_manager.refresh_async()

        # ---- 信号槽：控制台 ----
        for name in self._consoles:
            self._wire_console(name)

        # ---- 窗口行为 ----
        if self._settings.get("always_on_top", False):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if self._settings.get("window_size"):
            try:
                w, h = self._settings["window_size"]
                self.resize(int(w), int(h))
            except Exception:
                pass
        if self._settings.get("start_hidden", False):
            self.hide()
        else:
            self.show()

        # 自动启动控制台（错开 300ms 避免同时起进程）
        QTimer.singleShot(300, self._auto_start_consoles)

    # ------------------------------------------------------------------ #
    #  UI 构建
    # ------------------------------------------------------------------ #

    def _set_window_icon(self) -> None:
        """设置窗口图标。"""
        from ..constants import APP_DIR

        for filename in ("icon.ico", "icon.png"):
            p = APP_DIR / filename
            if p.exists():
                self.setWindowIcon(QIcon(str(p)))
                return

    def _build_ui(self) -> None:
        """构建整体界面：菜单栏 + 工具栏 + 标签页 + 状态栏。"""

        # ---- 菜单栏 ----
        self._build_menubar()

        # ---- 标签页 ----
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)  # 贴合主窗口的标签页外观
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.setCentralWidget(self.tabs)

        # 服务页（index 0）
        self.service_view = ServiceView()
        self.tabs.addTab(self.service_view, "服务管理")
        self._tab_index_service = 0

        # ---- 服务视图信号 ----
        self.service_view.start_requested.connect(self.service_manager.start)
        self.service_view.stop_requested.connect(self.service_manager.stop)
        self.service_view.restart_requested.connect(self.service_manager.restart)
        self.service_view.remove_requested.connect(self.remove_service)

        # ---- 工具栏（依赖 service_view 存在，放在标签页构建后）----
        self._build_toolbar()

        # ---- 快捷键（Ctrl+N 由菜单动作承载）----
        QShortcut(QKeySequence("Ctrl+K"), self, self.search_edit.setFocus)
        QShortcut(QKeySequence("F5"), self, self.refresh_all)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_all)

    def _build_menubar(self) -> None:
        """构建标准菜单栏（文件 / 编辑 / 视图 / 设置）。"""
        menubar = self.menuBar()

        # ---- 文件 ----
        menu_file = menubar.addMenu("文件(&F)")
        act_new = menu_file.addAction(icons.icon("add"), "新建控制台(&N)")
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.new_console)
        menu_file.addSeparator()
        act_quit = menu_file.addAction("退出(&X)")
        act_quit.triggered.connect(self.quit_app)

        # ---- 编辑 ----
        menu_edit = menubar.addMenu("编辑(&E)")
        act_edit_console = menu_edit.addAction("编辑控制台…")
        act_edit_console.triggered.connect(lambda: self.edit_console())
        act_del_console = menu_edit.addAction(icons.icon("delete"), "删除控制台…")
        act_del_console.triggered.connect(lambda: self.delete_console())

        # ---- 视图 ----
        menu_view = menubar.addMenu("视图(&V)")
        act_services = menu_view.addAction("服务管理")
        act_services.triggered.connect(self.show_service_page)
        menu_view.addSeparator()
        self._act_toolbar = menu_view.addAction("工具栏")
        self._act_toolbar.setCheckable(True)
        self._act_toolbar.setChecked(True)
        self._act_toolbar.triggered.connect(
            lambda checked: self.toolbar.setVisible(checked)
        )
        self._act_statusbar = menu_view.addAction("状态栏")
        self._act_statusbar.setCheckable(True)
        self._act_statusbar.setChecked(True)
        self._act_statusbar.triggered.connect(
            lambda checked: self.statusBar().setVisible(checked)
        )

        # ---- 设置 ----
        menu_settings = menubar.addMenu("设置(&S)")
        act_settings = menu_settings.addAction(icons.icon("settings"), "全局设置…")
        act_settings.triggered.connect(self.open_settings)

    def _build_toolbar(self) -> None:
        """构建工具栏：按钮带图标+文本，按标签页切换功能集。"""
        from PyQt6.QtWidgets import QSizePolicy

        self.toolbar = QToolBar("工具栏")
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(self.toolbar)

        # ---- 通用：新建控制台 ----
        self.act_tb_new = self.toolbar.addAction(icons.icon("new_console"), "新建控制台")
        self.act_tb_new.triggered.connect(self.new_console)

        self.toolbar.addSeparator()

        # ---- 控制台页专属 ----
        self.act_tb_start = self.toolbar.addAction(icons.icon("play"), "启动")
        self.act_tb_start.triggered.connect(self._toolbar_start)

        self.act_tb_stop = self.toolbar.addAction(icons.icon("stop"), "停止")
        self.act_tb_stop.triggered.connect(self._toolbar_stop)

        self.act_tb_restart = self.toolbar.addAction(icons.reboot_icon(), "重启")
        self.act_tb_restart.triggered.connect(self._toolbar_restart)

        self.act_tb_del = self.toolbar.addAction(icons.icon("delete"), "删除控制台")
        # 用显式封装避免 PyQt6 triggered 的 bool 参数被当作 name 传入 delete_console
        self.act_tb_del.triggered.connect(self._toolbar_delete_console)

        self.toolbar.addSeparator()

        # ---- 服务页专属 ----
        self.act_tb_add_service = self.toolbar.addAction(icons.icon("add_service"), "添加服务")
        self.act_tb_add_service.triggered.connect(self.add_service)

        self.act_tb_svc_start = self.toolbar.addAction(icons.icon("play"), "启动服务")
        self.act_tb_svc_start.triggered.connect(self.service_view._on_start)

        self.act_tb_svc_stop = self.toolbar.addAction(icons.icon("stop"), "停止服务")
        self.act_tb_svc_stop.triggered.connect(self.service_view._on_stop)

        self.act_tb_svc_restart = self.toolbar.addAction(icons.reboot_icon(), "重启服务")
        self.act_tb_svc_restart.triggered.connect(self.service_view._on_restart)

        self.act_tb_svc_remove = self.toolbar.addAction(icons.icon("remove"), "移除服务")
        self.act_tb_svc_remove.triggered.connect(self.service_view._on_remove)

        # ---- 通用：刷新 ----
        self.act_tb_refresh = self.toolbar.addAction(icons.icon("refresh"), "刷新")
        self.act_tb_refresh.setShortcut("F5")
        self.act_tb_refresh.triggered.connect(self.refresh_all)

        # 搜索框放工具栏右侧
        spacer_widget = QWidget()
        lay = QHBoxLayout(spacer_widget)
        lay.setContentsMargins(8, 0, 0, 0)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(spacer)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("过滤控制台…（Ctrl+K）")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(220)
        self.search_edit.textChanged.connect(self._filter_tabs)
        lay.addWidget(self.search_edit)
        self.toolbar.addWidget(spacer_widget)

        # 标签页切换时刷新工具栏按钮可见性
        self.tabs.currentChanged.connect(self._update_toolbar_for_tab)
        self._update_toolbar_for_tab(self.tabs.currentIndex())

    def _update_toolbar_for_tab(self, _index: int) -> None:
        """按当前标签页切换工具栏按钮：服务页显示服务操作，控制台页显示控制台操作。"""
        is_service_tab = self._current_console_name() is None

        for act in (
            self.act_tb_start,
            self.act_tb_stop,
            self.act_tb_restart,
            self.act_tb_del,
        ):
            act.setVisible(not is_service_tab)

        for act in (
            self.act_tb_add_service,
            self.act_tb_svc_start,
            self.act_tb_svc_stop,
            self.act_tb_svc_restart,
            self.act_tb_svc_remove,
        ):
            act.setVisible(is_service_tab)

    # ------------------------------------------------------------------ #
    #  控制台视图管理
    # ------------------------------------------------------------------ #

    def _ensure_console_view(self, name: str) -> ConsoleView:
        """确保指定控制台的视图存在并接线。"""
        view = self._console_views.get(name)
        if view is not None:
            return view

        view = ConsoleView(name, self._consoles.get(name, {}), self)
        # 输入行直连 runner.send_command
        runner = self.process_manager.get(name)
        if runner is not None:
            view.cmd_edit.returnPressed.disconnect()
            view.cmd_edit.returnPressed.connect(
                lambda n=name, v=view: self._send_command(n, v)
            )
            view.btn_send.clicked.connect(
                lambda n=name, v=view: self._send_command(n, v)
            )
            runner.output_ready.connect(view.append_output)
            runner.state_changed.connect(view.apply_state)

        self._console_views[name] = view
        self._tab_index_console[name] = self.tabs.addTab(view, name)
        return view

    def _send_command(self, name: str, view: ConsoleView) -> None:
        """把输入框内容发给 runner stdin。"""
        text = view.cmd_edit.text()
        if not text:
            return
        runner = self.process_manager.get(name)
        if runner is None:
            return
        view.append_output(f"[{self._now()}] > {text}")
        runner.send_command(text)
        view.cmd_edit.clear()

    @staticmethod
    def _now() -> str:
        from datetime import datetime

        return datetime.now().strftime("%H:%M:%S")

    def _wire_console(self, name: str) -> None:
        """创建视图（不激活）。"""
        self._ensure_console_view(name)

    def _auto_start_consoles(self) -> None:
        """启动标记了 auto_start 的控制台。"""
        for name, cfg in self._consoles.items():
            if cfg.get("auto_start", False):
                self.process_manager.start_console(name)

    # ------------------------------------------------------------------ #
    #  工具栏动作
    # ------------------------------------------------------------------ #

    def _current_console_name(self) -> str | None:
        """当前标签页对应的控制台名（服务页返回 None）。"""
        widget = self.tabs.currentWidget()
        for name, view in self._console_views.items():
            if view is widget:
                return name
        return None

    def _toolbar_start(self) -> None:
        name = self._current_console_name()
        if name:
            self.process_manager.start_console(name)
        else:
            self.statusBar().showMessage("请先选择一个控制台标签页", 3000)

    def _toolbar_stop(self) -> None:
        name = self._current_console_name()
        if name:
            self.process_manager.stop_console(name)
        else:
            self.statusBar().showMessage("请先选择一个控制台标签页", 3000)

    def _toolbar_restart(self) -> None:
        name = self._current_console_name()
        if name:
            self.process_manager.restart_console(name)
        else:
            self.statusBar().showMessage("请先选择一个控制台标签页", 3000)

    def _toolbar_delete_console(self) -> None:
        """工具栏"删除控制台"：确认后删除当前控制台标签页。"""
        name = self._current_console_name()
        if not name:
            self.statusBar().showMessage("请先选择一个控制台标签页", 3000)
            return
        self.delete_console(name)

    def _filter_tabs(self, text: str) -> None:
        """按名称过滤控制台标签页。"""
        text = (text or "").strip().lower()
        for name, index in self._tab_index_console.items():
            self.tabs.setTabVisible(index, not bool(text) or text in name.lower())

    # ------------------------------------------------------------------ #
    #  控制台增删改
    # ------------------------------------------------------------------ #

    def new_console(self) -> None:
        """新建控制台。"""
        dlg = ConsoleEditDialog(self)
        if dlg.exec() == ConsoleEditDialog.DialogCode.Accepted:
            name, cfg = dlg.get_result()
            if not name or not cfg:
                return
            if name in self._consoles:
                QMessageBox.warning(self, "提示", f"控制台 '{name}' 已存在。")
                return
            self._consoles[name] = cfg
            self.process_manager.add_or_update_console(name, cfg)
            self._wire_console(name)
            self._save_all()
            self.statusBar().showMessage(f"已创建控制台: {name}", 3000)

    def edit_console(self, name: str | None = None) -> None:
        """编辑控制台。"""
        if name is None:
            name = self._current_console_name()
        if name not in self._consoles:
            return

        dlg = ConsoleEditDialog(self, name, self._consoles[name])
        if dlg.exec() == ConsoleEditDialog.DialogCode.Accepted:
            new_name, cfg = dlg.get_result()
            if not new_name or not cfg:
                return

            if new_name != name:
                # 名称改变：删除旧条目重建
                self._remove_console_internal(name)
            self._consoles[new_name] = cfg
            self.process_manager.add_or_update_console(new_name, cfg)
            self._wire_console(new_name)
            self._save_all()
            self.statusBar().showMessage(f"已更新控制台: {new_name}", 3000)

    def delete_console(self, name: str | None = None) -> None:
        """删除控制台（带确认）。"""
        if name is None:
            name = self._current_console_name()
        if name not in self._consoles:
            return

        if QMessageBox.question(
            self, "确认", f"确定要删除控制台 '{name}' 吗？"
        ) != QMessageBox.StandardButton.Yes:
            return

        self._remove_console_internal(name)
        self._save_all()
        self.statusBar().showMessage(f"已删除控制台: {name}", 3000)

    def _remove_console_internal(self, name: str) -> None:
        """内部移除控制台的视图、runner、数据。"""
        view = self._console_views.pop(name, None)
        if view is not None:
            index = self._tab_index_console.pop(name, -1)
            if index >= 0:
                self.tabs.removeTab(index)
            view.deleteLater()
        self.process_manager.remove_console(name)
        self._consoles.pop(name, None)
        # 移除后重建其余标签索引
        self._reindex_tabs()
        self._refresh_counts()
        if self._current_console_name() is None:
            self.show_service_page()

    def _reindex_tabs(self) -> None:
        """移除标签后重建名称→索引映射。"""
        self._tab_index_console.clear()
        for name, view in self._console_views.items():
            self._tab_index_console[name] = self.tabs.indexOf(view)

    # ------------------------------------------------------------------ #
    #  服务增删
    # ------------------------------------------------------------------ #

    def add_service(self) -> None:
        """添加服务。"""
        dlg = AddServiceDialog(self)
        if dlg.exec() == AddServiceDialog.DialogCode.Accepted:
            name, display = dlg.get_result()
            if not name:
                return
            ok = self.service_manager.add_service(name, display)
            if ok:
                self._save_all()
                self.statusBar().showMessage(f"已添加服务: {name}", 3000)
            else:
                QMessageBox.warning(self, "提示", f"服务 '{name}' 不存在或已在列表中。")

    def remove_service(self, name: str) -> None:
        """移除服务。"""
        if QMessageBox.question(
            self, "确认", f"确定要移除服务 '{name}' 吗？"
        ) != QMessageBox.StandardButton.Yes:
            return
        if self.service_manager.remove_service(name):
            self._save_all()
            self.statusBar().showMessage(f"已移除服务: {name}", 3000)

    # ------------------------------------------------------------------ #
    #  信号槽
    # ------------------------------------------------------------------ #

    def _on_any_console_state(self, name: str) -> None:
        """任一控制台状态变化：刷新标签页状态后缀、计数、托盘。"""
        self._refresh_tab_states()
        self._refresh_counts()
        if self.tray is not None:
            self.tray.on_console_state_changed(name)

    def _refresh_tab_states(self) -> None:
        """刷新控制台标签页标题（名称 + 状态后缀）。"""
        for name, index in self._tab_index_console.items():
            runner = self.process_manager.get(name)
            running = bool(runner and runner.is_running)
            suffix = "  ▶" if running else ""
            self.tabs.setTabText(index, f"{name}{suffix}")

    def _refresh_counts(self) -> None:
        """刷新状态栏计数与托盘图标状态。"""
        total = len(self._consoles)
        running = self.process_manager.running_count
        if not hasattr(self, "count_label"):
            # 状态栏永久控件在首次调用时创建（QStatusBar 懒加载）
            self.count_label = QLabel("控制台: 0")
            self.running_label = QLabel("运行: 0")
            self.statusBar().addPermanentWidget(self.count_label)
            self.statusBar().addPermanentWidget(self.running_label)
        self.count_label.setText(f"控制台: {total}")
        self.running_label.setText(f"运行: {running}")
        if self.tray is not None:
            self.tray.update_icon_state(running, total)

    def _on_services_updated(self, services: list) -> None:
        """服务状态刷新完成：更新表格。"""
        self.service_view.refresh(services)

    def _on_service_action(self, name: str, action: str, success: bool, message: str) -> None:
        """服务启停操作完成。"""
        self.statusBar().showMessage(f"{message}", 5000 if success else 8000)
        logger.info("服务操作完成: %s %s success=%s", name, action, success)

    # ------------------------------------------------------------------ #
    #  设置 / 刷新 / 保存
    # ------------------------------------------------------------------ #

    def open_settings(self) -> None:
        """打开全局设置。"""
        dlg = SettingsDialog(self, self._settings)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            new_settings = dlg.get_result()
            self._settings.update(new_settings)
            self._apply_settings()
            self._save_all()
            self.statusBar().showMessage("设置已保存", 3000)

    def _apply_settings(self) -> None:
        """应用设置到当前窗口。"""
        top = bool(self._settings.get("always_on_top", False))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, top)
        self.show()  # setWindowFlag 后需要重新显示

        # 日志级别
        import logging as _logging

        level_name = self._settings.get("log_level", "INFO")
        level = getattr(_logging, level_name, _logging.INFO)
        _logging.getLogger().setLevel(level)

    def refresh_all(self) -> None:
        """F5：刷新服务状态。"""
        self.service_manager.refresh_async()
        self.statusBar().showMessage("正在刷新服务状态…", 2000)

    def _save_all(self) -> None:
        """保存全部配置与设置。"""
        try:
            services = self.service_manager.statuses()
            config_store.save_config(self._consoles, services)
            config_store.save_settings(self._settings)
        except Exception:
            logger.exception("保存配置失败")

    # ------------------------------------------------------------------ #
    #  窗口 / 托盘 / 退出
    # ------------------------------------------------------------------ #

    def show_service_page(self) -> None:
        """切换到服务管理页。"""
        self.tabs.setCurrentIndex(self._tab_index_service)

    def toggle_window(self) -> None:
        """托盘切换窗口可见性。"""
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        """点关闭按钮 → 隐藏到托盘而不是退出。"""
        if getattr(self, "_really_quit", False):
            event.accept()
            return
        event.ignore()
        self.hide()
        if self.tray is not None:
            try:
                from PyQt6.QtWidgets import QSystemTrayIcon

                if QSystemTrayIcon.isSystemTrayAvailable():
                    self.tray._tray.showMessage(
                        "控制台管理器",
                        "程序已最小化到托盘，继续在后台运行",
                        QSystemTrayIcon.MessageIcon.Information,
                        3000,
                    )
            except Exception:
                logger.debug("托盘提示失败", exc_info=True)

    def quit_app(self) -> None:
        """安全退出：停进程、存配置、停托盘。"""
        logger.info("正在退出应用…")
        self._really_quit = True

        try:
            self.service_manager.stop_periodic_refresh()
        except Exception:
            pass

        try:
            self.process_manager.stop_all()
            for runner in self.process_manager.runners.values():
                runner.cleanup()
        except Exception:
            logger.exception("停止控制台进程失败")

        self._save_all()

        try:
            self.tray.shutdown()
        except Exception:
            logger.exception("托盘清理失败")

        self.close()
        QApplication.instance().quit()
