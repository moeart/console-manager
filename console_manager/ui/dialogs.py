from __future__ import annotations

"""
对话框模块（标准原生控件版）。

所有对话框统一使用 QDialog，外观走 Qt 原生样式。
"""

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# 1. 控制台编辑 / 新建对话框
# ===========================================================================
class ConsoleEditDialog(QDialog):
    """控制台新建 / 编辑对话框。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        name: str = "",
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        :param parent: 父窗口
        :param name:   控制台名称（编辑时传原名称）
        :param config: 控制台配置 dict，``None`` 表示新建
        """
        super().__init__(parent)
        self.setWindowTitle("编辑控制台" if config is not None else "新建控制台")
        self.setMinimumWidth(520)
        self.setFixedWidth(520)

        self._is_edit = config is not None
        cfg = config or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        # ---- 表单 ----
        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 6, 0, 6)

        # 表单标签右对齐，输入控件左端对齐（标准 Win32 对话框习惯）
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # 名称
        self.name_edit = QLineEdit(self)
        self.name_edit.setText(name)
        self.name_edit.setPlaceholderText("必填，控制台显示名称")
        form.addRow("名称：", self.name_edit)

        # 程序路径（输入框 + 浏览按钮）
        program_row = QHBoxLayout()
        program_row.setContentsMargins(0, 0, 0, 0)
        self.program_edit = QLineEdit(self)
        self.program_edit.setText(cfg.get("program", ""))
        self.program_edit.setPlaceholderText("必填，可执行文件路径")
        btn_browse_program = QPushButton("浏览…", self)
        btn_browse_program.clicked.connect(self._browse_program)
        program_row.addWidget(self.program_edit, 1)
        program_row.addWidget(btn_browse_program)
        program_container = QWidget(self)
        program_container.setLayout(program_row)
        form.addRow("程序路径：", program_container)

        # 参数
        self.args_edit = QLineEdit(self)
        self.args_edit.setText(str(cfg.get("args", "")))
        self.args_edit.setPlaceholderText("可选，空格分隔的命令行参数")
        form.addRow("参数：", self.args_edit)

        # 工作目录（输入框 + 浏览按钮）
        workdir_row = QHBoxLayout()
        workdir_row.setContentsMargins(0, 0, 0, 0)
        self.workdir_edit = QLineEdit(self)
        self.workdir_edit.setText(cfg.get("work_dir", ""))
        self.workdir_edit.setPlaceholderText("可选，留空则使用程序所在目录")
        btn_browse_dir = QPushButton("浏览…", self)
        btn_browse_dir.clicked.connect(self._browse_workdir)
        workdir_row.addWidget(self.workdir_edit, 1)
        workdir_row.addWidget(btn_browse_dir)
        workdir_container = QWidget(self)
        workdir_container.setLayout(workdir_row)
        form.addRow("工作目录：", workdir_container)

        # 对齐：两行浏览按钮宽度一致，保证输入框左端对齐
        size_hint = max(
            btn_browse_program.sizeHint().width(),
            btn_browse_dir.sizeHint().width(),
        )
        btn_browse_program.setMinimumWidth(size_hint)
        btn_browse_dir.setMinimumWidth(size_hint)

        # 描述（高度 4 行）
        self.desc_edit = QPlainTextEdit(self)
        self.desc_edit.setPlainText(cfg.get("description", ""))
        self.desc_edit.setFixedHeight(80)
        form.addRow("描述：", self.desc_edit)

        # 自动启动
        self.auto_start_check = QCheckBox("自动启动", self)
        self.auto_start_check.setChecked(bool(cfg.get("auto_start", False)))
        form.addRow("", self.auto_start_check)

        layout.addLayout(form)

        # ---- 按钮区 ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = btn_box.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText("保存")
        cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText("取消")
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ---- 浏览按钮槽 ----

    def _browse_program(self) -> None:
        """打开文件选择对话框选择可执行文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择程序文件",
            "",
            "可执行文件 (*.exe *.bat *.cmd *.py);;所有文件 (*.*)",
        )
        if path:
            self.program_edit.setText(path)

    def _browse_workdir(self) -> None:
        """打开目录选择对话框选择工作目录。"""
        path = QFileDialog.getExistingDirectory(self, "选择工作目录")
        if path:
            self.workdir_edit.setText(path)

    # ---- 确定按钮校验 ----

    def _on_accept(self) -> None:
        """点击保存时的校验逻辑。"""
        name = self.name_edit.text().strip()
        program = self.program_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "名称不能为空。")
            self.name_edit.setFocus()
            return
        if not program:
            QMessageBox.warning(self, "提示", "程序路径不能为空。")
            self.program_edit.setFocus()
            return
        self.accept()

    # ---- 公开 API ----

    def get_result(self) -> tuple[str, dict[str, Any]]:
        """
        返回表单数据。

        :return: ``(name, config_dict)``，config_dict 键：program / args / work_dir /
                 description / auto_start
        """
        config: dict[str, Any] = {
            "program":     self.program_edit.text().strip(),
            "args":        self.args_edit.text().strip(),
            "work_dir":    self.workdir_edit.text().strip() or ".",
            "description": self.desc_edit.toPlainText().strip(),
            "auto_start":  self.auto_start_check.isChecked(),
        }
        return self.name_edit.text().strip(), config


# ===========================================================================
# 2. 添加服务对话框
# ===========================================================================
class AddServiceDialog(QDialog):
    """添加 Windows 服务对话框。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加服务")
        self.setFixedWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        # ---- 表单 ----
        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 6, 0, 6)

        self.service_name_edit = QLineEdit(self)
        self.service_name_edit.setPlaceholderText("必填，系统服务名称")
        form.addRow("服务名称：", self.service_name_edit)

        self.display_name_edit = QLineEdit(self)
        self.display_name_edit.setPlaceholderText("可选，留空则使用服务名称")
        form.addRow("显示名称：", self.display_name_edit)

        layout.addLayout(form)

        # ---- 按钮区 ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("确定")
        cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText("取消")
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self) -> None:
        """点击确定时的校验逻辑。"""
        if not self.service_name_edit.text().strip():
            QMessageBox.warning(self, "提示", "服务名称不能为空。")
            self.service_name_edit.setFocus()
            return
        self.accept()

    def get_result(self) -> tuple[str, str]:
        """
        返回表单数据。

        :return: ``(service_name, display_name)``
        """
        name = self.service_name_edit.text().strip()
        display = self.display_name_edit.text().strip() or name
        return name, display


# ===========================================================================
# 3. 全局设置对话框
# ===========================================================================
class SettingsDialog(QDialog):
    """全局设置对话框（仅收集数据，不负责持久化）。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        """
        :param parent:   父窗口
        :param settings: 当前设置 dict，``None`` 则使用默认值
        """
        super().__init__(parent)
        self.setWindowTitle("全局设置")
        self.setFixedWidth(480)

        s = settings or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        # ---- 表单 ----
        form = QFormLayout()
        form.setSpacing(12)
        form.setContentsMargins(0, 6, 0, 6)

        self.auto_start_check = QCheckBox("开机自动启动程序", self)
        self.auto_start_check.setChecked(bool(s.get("auto_start_app", False)))
        form.addRow("", self.auto_start_check)

        self.start_hidden_check = QCheckBox("启动时隐藏主窗口", self)
        self.start_hidden_check.setChecked(bool(s.get("start_hidden", False)))
        form.addRow("", self.start_hidden_check)

        self.always_on_top_check = QCheckBox("窗口总是置顶", self)
        self.always_on_top_check.setChecked(bool(s.get("always_on_top", False)))
        form.addRow("", self.always_on_top_check)

        self.log_level_combo = QComboBox(self)
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            self.log_level_combo.addItem(level)
        current_level = str(s.get("log_level", "INFO"))
        idx = self.log_level_combo.findText(current_level)
        if idx >= 0:
            self.log_level_combo.setCurrentIndex(idx)
        form.addRow("日志级别：", self.log_level_combo)

        layout.addLayout(form)

        # ---- 按钮区 ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = btn_box.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText("保存")
        cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText("取消")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_result(self) -> dict[str, Any]:
        """
        返回设置数据 dict。

        :return: 键 auto_start_app / start_hidden / always_on_top / log_level
        """
        return {
            "auto_start_app": self.auto_start_check.isChecked(),
            "start_hidden":   self.start_hidden_check.isChecked(),
            "always_on_top":  self.always_on_top_check.isChecked(),
            "log_level":      self.log_level_combo.currentText(),
        }
