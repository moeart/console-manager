"""服务管理视图（标准原生控件版）。

固定列宽表格（服务名 / 状态 / 显示名称），顶部操作按钮。
数据由 ServiceManager 的 services_updated 信号驱动整表重建。
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .theme import status_color, status_text_zh

logger = logging.getLogger(__name__)

_COLUMNS = ("服务名称", "状态", "显示名称")
_COL_WIDTHS = (200, 110, 420)


class ServiceView(QWidget):
    """服务管理页面。"""

    start_requested = pyqtSignal(str)
    stop_requested = pyqtSignal(str)
    restart_requested = pyqtSignal(str)
    add_requested = pyqtSignal()
    remove_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # ---- 顶部按钮行 ----
        top = QHBoxLayout()
        top.setSpacing(8)

        btn_add = QPushButton("添加服务")
        icons.set_button_icon(btn_add, "add")
        btn_add.clicked.connect(lambda: self.add_requested.emit())
        top.addWidget(btn_add)

        btn_start = QPushButton("启动")
        icons.set_button_icon(btn_start, "play")
        btn_start.clicked.connect(self._on_start)
        top.addWidget(btn_start)

        btn_stop = QPushButton("停止")
        icons.set_button_icon(btn_stop, "stop")
        btn_stop.clicked.connect(self._on_stop)
        top.addWidget(btn_stop)

        btn_restart = QPushButton("重启")
        icons.set_button_icon(btn_restart, "restart")
        btn_restart.clicked.connect(self._on_restart)
        top.addWidget(btn_restart)

        btn_remove = QPushButton("移除")
        btn_remove.clicked.connect(self._on_remove)
        top.addWidget(btn_remove)

        top.addStretch(1)

        btn_refresh = QPushButton("刷新")
        icons.set_button_icon(btn_refresh, "refresh")
        btn_refresh.clicked.connect(lambda: self.refresh_requested.emit())
        top.addWidget(btn_refresh)

        layout.addLayout(top)

        # ---- 服务表格 ----
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for i, w in enumerate(_COL_WIDTHS):
            self.table.setColumnWidth(i, w)
        # 最后一列铺满剩余空间
        header.setSectionResizeMode(len(_COL_WIDTHS) - 1, QHeaderView.ResizeMode.Stretch)

        self.table.doubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.table, 1)

        # 内部缓存：行号 -> 服务名 / 状态快照（供双击判断用）
        self._row_names: list[str] = []
        self._row_status: list[str] = []

    # ------------------------------------------------------------------ #
    #  公开槽
    # ------------------------------------------------------------------ #

    def refresh(self, services: list) -> None:
        """用服务快照整表重建。"""
        self.table.setRowCount(0)
        self._row_names.clear()
        self._row_status.clear()

        for svc in services:
            name = str(svc.get("name", ""))
            display = str(svc.get("display_name", name))
            status = str(svc.get("status", "unknown"))
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(name))
            item_status = QTableWidgetItem(status_text_zh(status))
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # 状态列着色：运行=绿 / 停止=红 / 未知=灰
            item_status.setForeground(QBrush(QColor(status_color(status))))
            self.table.setItem(row, 1, item_status)
            self.table.setItem(row, 2, QTableWidgetItem(display))

            self._row_names.append(name)
            self._row_status.append(status)

    def refresh_styling(self) -> None:
        """重刷状态列颜色（保留接口，颜色不随主题变化时也可调用）。"""
        for row, status in enumerate(self._row_status):
            item = self.table.item(row, 1)
            if item is not None:
                item.setForeground(QBrush(QColor(status_color(status))))

    def refresh_styling(self) -> None:
        """兼容接口：颜色不随主题变化（保留给既有调用点）。"""

    # ------------------------------------------------------------------ #
    #  内部
    # ------------------------------------------------------------------ #

    def _selected_service(self) -> str | None:
        """当前选中行的服务名。"""
        row = self.table.currentRow()
        if 0 <= row < len(self._row_names):
            return self._row_names[row]
        return None

    def _on_start(self) -> None:
        name = self._selected_service()
        if name:
            self.start_requested.emit(name)

    def _on_stop(self) -> None:
        name = self._selected_service()
        if name:
            self.stop_requested.emit(name)

    def _on_restart(self) -> None:
        name = self._selected_service()
        if name:
            self.restart_requested.emit(name)

    def _on_remove(self) -> None:
        name = self._selected_service()
        if name:
            self.remove_requested.emit(name)

    def _on_double_clicked(self, _index) -> None:
        """双击行 = 启停切换。"""
        name = self._selected_service()
        if not name:
            return
        row = self.table.currentRow()
        if 0 <= row < len(self._row_status):
            if self._row_status[row] == "running":
                self.stop_requested.emit(name)
            else:
                self.start_requested.emit(name)
