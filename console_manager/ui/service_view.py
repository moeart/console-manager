"""服务管理视图（标准原生控件版）。

固定列宽表格（状态图标 / 服务名 / 状态 / 显示名称）。
启停等操作统一收归主窗口工具栏，本视图只负责展示与选中。
数据由 ServiceManager 的 services_updated 信号驱动整表重建。
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .theme import status_color, status_text_zh

logger = logging.getLogger(__name__)

_COLUMNS = ("", "服务名称", "状态", "显示名称")
_COL_WIDTHS = (40, 200, 110, 420)


class ServiceView(QWidget):
    """服务管理页面。"""

    start_requested = pyqtSignal(str)
    stop_requested = pyqtSignal(str)
    restart_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

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

        # ---- 选中行样式：整行 Windows 高亮蓝 ----
        # 默认 windows11 样式下选中仅浅灰底+单元格左侧编辑光标竖线，
        # 观感上"不像选中"。改用 QSS 强制整行蓝底白字，效果直观。
        self.table.setStyleSheet(
            """
            QTableWidget::item:selected {
                background-color: #0078D4;
                color: #FFFFFF;
            }
            QTableWidget::item {
                padding: 2px 4px;
            }
            """
        )
        # 交替行底色保持与原生一致
        self.table.setAlternatingRowColors(True)

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

            # 首列：状态图标（运行=绿色播放 / 停止=红色方块 / 未知=灰色问号）
            item_icon = QTableWidgetItem()
            item_icon.setIcon(icons.status_shape_icon(status))
            item_icon.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_icon.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, item_icon)

            self.table.setItem(row, 1, QTableWidgetItem(name))
            item_status = QTableWidgetItem(status_text_zh(status))
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # 状态列着色：运行=绿 / 停止=红 / 未知=灰
            item_status.setForeground(QBrush(QColor(status_color(status))))
            self.table.setItem(row, 2, item_status)
            self.table.setItem(row, 3, QTableWidgetItem(display))

            self._row_names.append(name)
            self._row_status.append(status)

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
