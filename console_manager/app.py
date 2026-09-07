"""应用入口：日志初始化、全局异常钩子、QApplication 启动。

稳定性设计：
- 日志用 RotatingFileHandler（app.log 最大 2MB，保留 2 个备份）
- sys.excepthook / threading.excepthook 兜底，未捕获异常记日志而不是闪退
- 退出时统一走 MainWindow.quit_app()
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
import threading

from PyQt6.QtWidgets import QApplication

from .constants import APP_DIR


def _setup_logging(level: str = "INFO") -> None:
    """初始化日志（轮转文件 + 控制台）。"""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        APP_DIR / "app.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # 仅在控制台运行（开发调试）时输出到 stderr
    if sys.stderr is not None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(fmt)
        root.addHandler(console_handler)


def _install_excepthooks() -> None:
    """安装全局异常钩子，未捕获异常记日志而不是崩掉进程。"""

    def _sys_hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.critical(
            "未捕获的异常", exc_info=(exc_type, exc_value, exc_tb)
        )

    def _thread_hook(args) -> None:
        logging.critical(
            "线程 %s 未捕获的异常: %s",
            getattr(args.thread, "name", "?"),
            args.exc_value,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook


def main() -> int:
    """程序主入口。"""
    _setup_logging()
    _install_excepthooks()
    logger = logging.getLogger(__name__)
    logger.info("=== 控制台管理器启动 ===")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关主窗口只是隐藏到托盘
    app.setApplicationName("控制台管理器")
    app.setDesktopFileName("ConsoleManager")

    # 界面使用 Qt 原生样式（Windows 上即系统原生外观），无自定义主题

    from .ui.main_window import MainWindow

    window = MainWindow()
    app._main_window = window  # 防止被 GC

    ret = app.exec()
    logger.info("=== 应用已退出 (code=%s) ===", ret)
    return ret


if __name__ == "__main__":
    sys.exit(main())
