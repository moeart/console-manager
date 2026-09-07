"""单个控制台的输出视图（标准原生控件版）。

每个控制台对应一个 ConsoleView：
- QPlainTextEdit 显示输出（maximumBlockCount 环形缓冲，长期运行内存恒定）
- 输出按日志级别着色（ERROR 红 / WARN 橙 / INFO 绿 / DEBUG 灰 / 时间戳淡灰）
- 底部命令输入框 + 发送按钮
- 顶部状态指示（状态圆点 + 名称 + 状态文字 + PID + 操作按钮）

所有更新由 ProcessRunner 的信号驱动。
"""
from __future__ import annotations

import logging
import re
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .theme import status_color, status_text_zh

logger = logging.getLogger(__name__)

# 输出区环形缓冲行数（内存上限的关键）
_MAX_BLOCKS = 4000


class LogHighlighter(QSyntaxHighlighter):
    """按日志级别给输出行着色。

    规则（对每行独立匹配，命中即整行着色）：
    - ERROR / FATAL / CRITICAL / SEVERE / 异常 / 失败 → 红
    - WARN / WARNING / 警告 → 橙
    - INFO / OK / SUCCESS / 成功 → 绿
    - DEBUG / TRACE → 灰
    - 行首 [HH:MM:SS] 时间戳 → 淡灰
    """

    _COLOR_ERROR = QColor("#C50F1F")
    _COLOR_WARN = QColor("#B26A00")
    _COLOR_INFO = QColor("#107C10")
    _COLOR_DEBUG = QColor("#767676")
    _COLOR_TS = QColor("#767676")

    _RE_ERROR = re.compile(
        r"\b(ERROR|FATAL|CRITICAL|SEVERE|Exception|Traceback)\b|异常|失败",
        re.IGNORECASE,
    )
    _RE_WARN = re.compile(r"\b(WARN|WARNING)\b|警告", re.IGNORECASE)
    _RE_INFO = re.compile(r"\b(INFO|OK|SUCCESS)\b|成功", re.IGNORECASE)
    _RE_DEBUG = re.compile(r"\b(DEBUG|TRACE|VERBOSE)\b", re.IGNORECASE)
    _RE_TS = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s?")

    def highlightBlock(self, text: str) -> None:
        # 时间戳部分淡灰
        m = self._RE_TS.match(text)
        # 级别判断（优先级：ERROR > WARN > INFO > DEBUG）
        color = None
        if self._RE_ERROR.search(text):
            color = self._COLOR_ERROR
        elif self._RE_WARN.search(text):
            color = self._COLOR_WARN
        elif self._RE_INFO.search(text):
            color = self._COLOR_INFO
        elif self._RE_DEBUG.search(text):
            color = self._COLOR_DEBUG

        if color is not None:
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            # 级别整行着色
            self.setFormat(0, len(text), fmt)

        # 时间戳部分淡灰（最后设置，覆盖级别色的行首区域）
        if m:
            fmt_ts = QTextCharFormat()
            fmt_ts.setForeground(self._COLOR_TS)
            self.setFormat(m.start(), m.end(), fmt_ts)


class ConsoleView(QWidget):
    """单个控制台的内容视图（输出 + 输入行）。"""

    #: 用户点击"启动"（未运行时）
    start_requested = pyqtSignal(str)
    #: 用户点击"停止"（运行中）
    stop_requested = pyqtSignal(str)
    #: 用户点击"重启"
    restart_requested = pyqtSignal(str)

    def __init__(self, name: str, config: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._config = config
        self._last_state: tuple[str, int, int] = ("stopped", 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # ---- 顶部信息行 ----
        top = QHBoxLayout()
        top.setSpacing(8)

        self.dot_label = QLabel()
        self.dot_label.setPixmap(icons._dot_pixmap("#767676"))
        top.addWidget(self.dot_label)

        self.title_label = QLabel(name)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        top.addWidget(self.title_label)

        self.state_label = QLabel("已停止")
        top.addWidget(self.state_label)

        top.addStretch(1)

        self.pid_label = QLabel("")
        top.addWidget(self.pid_label)

        self.btn_start = QPushButton("启动")
        icons.set_button_icon(self.btn_start, "play")
        self.btn_start.clicked.connect(lambda: self.start_requested.emit(self._name))
        top.addWidget(self.btn_start)

        self.btn_stop = QPushButton("停止")
        icons.set_button_icon(self.btn_stop, "stop")
        self.btn_stop.clicked.connect(lambda: self.stop_requested.emit(self._name))
        top.addWidget(self.btn_stop)

        self.btn_restart = QPushButton("重启")
        icons.set_button_icon(self.btn_restart, "restart")
        self.btn_restart.clicked.connect(lambda: self.restart_requested.emit(self._name))
        top.addWidget(self.btn_restart)

        layout.addLayout(top)

        # ---- 输出区 ----
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setMaximumBlockCount(_MAX_BLOCKS)
        self.output_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # 等宽字体，输出对齐更整齐
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.output_view.setFont(mono)
        layout.addWidget(self.output_view, 1)

        # 日志级别高亮器（挂在 document 上，随文本追加自动重扫）
        self.highlighter = LogHighlighter(self.output_view.document())

        # ---- 命令输入行 ----
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText("输入命令后回车发送到进程 stdin…")
        self.cmd_edit.returnPressed.connect(self._on_send)
        bottom.addWidget(self.cmd_edit, 1)

        self.btn_send = QPushButton("发送")
        icons.set_button_icon(self.btn_send, "check")
        self.btn_send.clicked.connect(self._on_send)
        bottom.addWidget(self.btn_send)

        self.btn_clear = QPushButton("清除")
        icons.set_button_icon(self.btn_clear, "close")
        self.btn_clear.clicked.connect(self.output_view.clear)
        bottom.addWidget(self.btn_clear)

        layout.addLayout(bottom)

        self._apply_state("stopped", 0, 0)

    # ------------------------------------------------------------------ #
    #  公开槽（由主窗口接到 ProcessRunner 信号）
    # ------------------------------------------------------------------ #

    def append_output(self, text: str) -> None:
        """追加输出文本。"""
        self.output_view.appendPlainText(text.rstrip("\n"))
        sb = self.output_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def apply_state(self, state: str, exit_code: int, pid: int) -> None:
        """根据 runner 状态刷新指示灯、按钮可用性等。"""
        self._apply_state(state, exit_code, pid)

    def on_theme_changed(self) -> None:
        """兼容接口：原生外观下无需处理主题切换。"""

    # ------------------------------------------------------------------ #
    #  内部
    # ------------------------------------------------------------------ #

    def _apply_state(self, state: str, exit_code: int, pid: int) -> None:
        running = state == "running"
        self._last_state = (state, exit_code, pid)

        self.dot_label.setPixmap(icons._dot_pixmap(status_color(state)))

        self.state_label.setText(status_text_zh(state) if state != "error" else f"异常退出（{exit_code}）")
        self.pid_label.setText(f"PID {pid}" if running else "")

        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_restart.setEnabled(True)

    def _on_send(self) -> None:
        """发送命令（通过信号交主窗口转发给 runner）。"""
        # 由主窗口连接后生效；此处保底为空操作
        pass

    # 兼容旧属性名
    @property
    def name(self) -> str:
        return self._name
