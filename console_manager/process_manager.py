from __future__ import annotations

import os
import sys
import locale
import shlex
import subprocess
import threading
import time
import queue
import logging
import datetime
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# 单次 emit 文本上限（字节），超过则截断头尾
_MAX_EMIT_BYTES = 64 * 1024
# flusher 每轮最多取出的行数
_MAX_FLUSH_LINES = 500
# flusher 轮询间隔（秒）
_FLUSH_INTERVAL = 0.1
# stop 时 terminate 后等待秒数
_STOP_WAIT = 2.0
# restart 时 stop 后等待秒数
_RESTART_DELAY = 0.3


def _console_encoding() -> str:
    """返回子进程控制台输出的真实编码名。

    Windows 控制台程序本地化输出遵循系统 ANSI 代码页（中文系统为 cp936/GBK）。
    必须直接调 Win32 GetACP：环境变量 PYTHONUTF8=1 时
    locale.getpreferredencoding() 会被 Python 重载为 UTF-8，不代表子进程
    真实输出编码。非 Windows 平台退回 locale 探测。
    """
    if sys.platform == "win32":
        try:
            import ctypes

            acp = ctypes.windll.kernel32.GetACP()
            return f"cp{acp}"
        except Exception:
            logger.debug("GetACP 失败，退回 locale 探测", exc_info=True)
    return locale.getpreferredencoding(False)


class ProcessRunner(QObject):
    """单个控制台进程的运行器，负责启动、停止、重启子进程并读取输出。

    所有 UI 相关的更新通过 PyQt6 信号发出，内部 IO 线程绝不直接操作 QWidget。
    """

    # 批量合并后的输出文本（已含时间戳前缀，按行）
    output_ready = pyqtSignal(str)
    # (state, exit_code, pid)；state: 'starting'/'running'/'stopped'/'error'
    state_changed = pyqtSignal(str, int, int)
    # 成功启动时发一次 pid
    started_ok = pyqtSignal(int)

    def __init__(self, name: str, config: dict) -> None:
        super().__init__()
        self._name: str = name
        self._config: dict = config

        self._process: subprocess.Popen | None = None
        self._pid: int = 0
        self._exit_code: int | None = None

        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._reader_thread: threading.Thread | None = None
        self._flusher_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None

        self._output_queue: queue.Queue[str | None] = queue.Queue()
        self._restarting = False

    # ------------------------------------------------------------------ #
    #  属性
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        """控制台名称。"""
        return self._name

    @property
    def config(self) -> dict:
        """控制台配置字典。"""
        return self._config

    @property
    def pid(self) -> int:
        """当前进程 PID，未启动时为 0。"""
        return self._pid

    @property
    def exit_code(self) -> int | None:
        """进程退出码，未退出时为 None。"""
        return self._exit_code

    @property
    def is_running(self) -> bool:
        """进程是否存在且仍在运行。"""
        with self._lock:
            proc = self._process
        if proc is None:
            return False
        return proc.poll() is None

    # ------------------------------------------------------------------ #
    #  启动
    # ------------------------------------------------------------------ #

    def _build_command(self) -> list[str]:
        """根据 config 组装命令行列表。"""
        program: str = self._config.get("program", "").strip()
        if not program:
            raise ValueError(f"console '{self._name}' 配置缺少 program")

        raw_args: Any = self._config.get("args", "")
        if isinstance(raw_args, str):
            args = shlex.split(raw_args) if raw_args.strip() else []
        elif isinstance(raw_args, (list, tuple)):
            args = list(raw_args)
        else:
            args = []

        # 过滤历史遗留的 -foreground 参数
        args = [a for a in args if a != "-foreground"]

        return [program, *args]

    def run(self) -> None:
        """启动子进程。若已在运行则直接返回。"""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            # 清理上一轮残留
            self._stop_event.clear()
            self._output_queue = queue.Queue()
            self._exit_code = None
            self._pid = 0

        cmd = self._build_command()
        work_dir: str = self._config.get("work_dir", ".") or "."

        logger.info("[%s] 启动进程: %s", self._name, cmd)
        self.state_changed.emit("starting", 0, 0)

        try:
            # Windows 控制台程序本地化输出默认是 ANSI 代码页（中文系统为 GBK/cp936）。
            # 注意：环境变量 PYTHONUTF8=1 时 locale.getpreferredencoding() 会返回
            # UTF-8（Python 层重载，不代表子进程真实输出），必须直接读 Win32 API
            # 的 ANSI 代码页才准确。非 Windows 平台退回 locale 探测。
            proc = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                encoding=_console_encoding(),
                errors="replace",
                bufsize=-1,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as exc:
            logger.exception("[%s] 启动失败", self._name)
            self._exit_code = -1
            self.state_changed.emit("error", -1, 0)
            self.output_ready.emit(f"[错误] 启动失败: {exc}\n")
            return

        with self._lock:
            self._process = proc
            self._pid = proc.pid

        self.state_changed.emit("running", 0, proc.pid)
        self.started_ok.emit(proc.pid)

        # 启动 IO 线程
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name=f"{self._name}-reader", daemon=True
        )
        self._flusher_thread = threading.Thread(
            target=self._flusher_loop, name=f"{self._name}-flusher", daemon=True
        )
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name=f"{self._name}-monitor", daemon=True
        )
        self._reader_thread.start()
        self._flusher_thread.start()
        self._monitor_thread.start()

    # ------------------------------------------------------------------ #
    #  reader 线程
    # ------------------------------------------------------------------ #

    def _reader_loop(self) -> None:
        """逐行读取 stdout（已合并 stderr），加时间戳后放入队列。"""
        proc = self._get_process()
        if proc is None or proc.stdout is None:
            return

        try:
            for line in iter(proc.stdout.readline, ""):
                if self._stop_event.is_set():
                    break
                if line == "":
                    break
                ts = datetime.datetime.now().strftime("[%H:%M:%S] ")
                self._output_queue.put(ts + line if not line.startswith("\n") else line)
        except Exception:
            logger.exception("[%s] reader 线程异常", self._name)
        finally:
            # 通知 flusher 退出
            self._output_queue.put(None)

    # ------------------------------------------------------------------ #
    #  flusher 线程
    # ------------------------------------------------------------------ #

    def _flusher_loop(self) -> None:
        """以固定间隔从队列批量取出行，拼接后 emit output_ready。"""
        while True:
            try:
                item = self._output_queue.get(timeout=_FLUSH_INTERVAL)
            except queue.Empty:
                if self._stop_event.is_set():
                    # 队列可能还有残余，再捞一轮
                    self._drain_queue()
                    break
                continue

            if item is None:
                # reader 结束，把队列剩余全部 flush
                self._drain_queue()
                break

            lines: list[str] = [item]
            count = 1
            while count < _MAX_FLUSH_LINES:
                try:
                    nxt = self._output_queue.get_nowait()
                except queue.Empty:
                    break
                if nxt is None:
                    break
                lines.append(nxt)
                count += 1

            text = "".join(lines)
            text = self._truncate(text)
            if text:
                self.output_ready.emit(text)

    def _drain_queue(self) -> None:
        """把队列中剩余的行全部取出并 emit。"""
        lines: list[str] = []
        while True:
            try:
                item = self._output_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                continue
            lines.append(item)
        if lines:
            text = self._truncate("".join(lines))
            if text:
                self.output_ready.emit(text)

    @staticmethod
    def _truncate(text: str) -> str:
        """超过 ~64KB 时保留头尾，中间插入截断提示。"""
        b = text.encode("utf-8")
        if len(b) <= _MAX_EMIT_BYTES:
            return text
        head_bytes = _MAX_EMIT_BYTES // 2
        tail_bytes = _MAX_EMIT_BYTES // 2
        head = b[:head_bytes].decode("utf-8", errors="ignore")
        tail = b[-tail_bytes:].decode("utf-8", errors="ignore")
        return head + "\n... (输出过多已截断) ...\n" + tail

    # ------------------------------------------------------------------ #
    #  monitor 线程
    # ------------------------------------------------------------------ #

    def _monitor_loop(self) -> None:
        """等待进程退出，发出 stopped/error 状态。"""
        proc = self._get_process()
        if proc is None:
            return
        try:
            code = proc.wait()
        except Exception:
            logger.exception("[%s] monitor 线程异常", self._name)
            code = -1

        self._exit_code = code
        with self._lock:
            self._pid = 0

        state = "stopped" if code == 0 else "error"
        pid = proc.pid
        self.state_changed.emit(state, code if code is not None else -1, pid)
        logger.info("[%s] 进程退出, code=%s", self._name, code)

        # restart 延迟启动（在 monitor 线程里做，避免再开 Timer 线程）
        if self._restarting:
            self._restarting = False
            time.sleep(_RESTART_DELAY)
            self.run()

    # ------------------------------------------------------------------ #
    #  停止 / 重启
    # ------------------------------------------------------------------ #

    def stop(self) -> None:
        """停止进程：terminate → 等 2s → kill()。对已退出的进程调用不抛异常。"""
        with self._lock:
            proc = self._process
        if proc is None:
            return

        self._stop_event.set()

        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                logger.debug("[%s] terminate 异常（忽略）", self._name)
            try:
                proc.wait(timeout=_STOP_WAIT)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    logger.debug("[%s] kill 异常（忽略）", self._name)

        # 关闭 stdin（send_command 后续调用会得到提示）
        for stream_attr in ("stdin", "stdout"):
            stream = getattr(proc, stream_attr, None)
            if stream:
                try:
                    stream.close()
                except Exception:
                    pass

    def restart(self) -> None:
        """重启进程：先 stop，等 300ms 后重新 run。"""
        if self._restarting:
            return
        self._restarting = True
        self.stop()

        # 如果进程已经不在运行（monitor 已退出或从未启动），直接触发重启
        if not self._is_monitor_alive():
            self._restarting = False
            time.sleep(_RESTART_DELAY)
            self.run()

    def _is_monitor_alive(self) -> bool:
        t = self._monitor_thread
        return t is not None and t.is_alive()

    # ------------------------------------------------------------------ #
    #  发送命令
    # ------------------------------------------------------------------ #

    def send_command(self, text: str) -> None:
        """往子进程 stdin 写一行文本。stdin 不可写时 emit 提示而非抛异常。"""
        with self._lock:
            proc = self._process
        if proc is None or proc.poll() is not None:
            self.output_ready.emit("[提示] 进程未运行，无法发送命令\n")
            return
        stdin = proc.stdin
        if stdin is None or stdin.closed:
            self.output_ready.emit("[提示] stdin 不可写，无法发送命令\n")
            return
        try:
            if not text.endswith("\n"):
                text += "\n"
            stdin.write(text)
            stdin.flush()
        except Exception as exc:
            self.output_ready.emit(f"[提示] 发送命令失败: {exc}\n")

    # ------------------------------------------------------------------ #
    #  cleanup
    # ------------------------------------------------------------------ #

    def cleanup(self) -> None:
        """彻底停止进程并通知所有线程退出。"""
        self._restarting = False
        self._stop_event.set()
        self.stop()

        # 往队列塞 None 唤醒 flusher
        try:
            self._output_queue.put(None)
        except Exception:
            pass

        # 等待线程结束（最多各等 3s）
        for thread_attr in ("_reader_thread", "_flusher_thread", "_monitor_thread"):
            t = getattr(self, thread_attr, None)
            if t is not None and t.is_alive():
                t.join(timeout=3.0)

        with self._lock:
            proc = self._process
            if proc is not None:
                for stream_attr in ("stdin", "stdout"):
                    stream = getattr(proc, stream_attr, None)
                    if stream:
                        try:
                            stream.close()
                        except Exception:
                            pass
                self._process = None
            self._pid = 0

    # ------------------------------------------------------------------ #
    #  辅助
    # ------------------------------------------------------------------ #

    def _get_process(self) -> subprocess.Popen | None:
        """线程安全地获取当前 process 引用。"""
        with self._lock:
            return self._process


class ProcessManager(QObject):
    """管理多个 ProcessRunner 的容器，提供批量启停和状态聚合信号。"""

    # 任一 console 状态变化时发 console name
    state_changed_any = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runners: dict[str, ProcessRunner] = {}

    # ------------------------------------------------------------------ #
    #  加载 / 添加 / 删除
    # ------------------------------------------------------------------ #

    def load_consoles(self, configs: dict) -> None:
        """批量创建 runner（不启动）。"""
        for name, cfg in configs.items():
            self.add_or_update_console(name, cfg)

    def add_or_update_console(self, name: str, config: dict) -> None:
        """添加或更新控制台配置。若在运行先 stop，再替换 runner。"""
        existing = self._runners.get(name)
        if existing is not None:
            existing.stop()
            existing.state_changed.disconnect()
            existing.cleanup()
        runner = ProcessRunner(name, config)
        runner.state_changed.connect(lambda s, c, p, n=name: self._on_state(n, s, c, p))
        self._runners[name] = runner

    def remove_console(self, name: str) -> None:
        """移除控制台：先停进程再从管理器删除。"""
        runner = self._runners.get(name)
        if runner is None:
            return
        runner.cleanup()
        try:
            runner.state_changed.disconnect()
        except Exception:
            pass
        del self._runners[name]

    # ------------------------------------------------------------------ #
    #  启停控制
    # ------------------------------------------------------------------ #

    def start_console(self, name: str) -> None:
        """启动指定控制台。"""
        runner = self._runners.get(name)
        if runner is not None:
            runner.run()

    def stop_console(self, name: str) -> None:
        """停止指定控制台。"""
        runner = self._runners.get(name)
        if runner is not None:
            runner.stop()

    def restart_console(self, name: str) -> None:
        """重启指定控制台。"""
        runner = self._runners.get(name)
        if runner is not None:
            runner.restart()

    def start_all(self) -> None:
        """启动所有控制台。"""
        for runner in self._runners.values():
            runner.run()

    def stop_all(self) -> None:
        """停止所有控制台。"""
        for runner in self._runners.values():
            runner.stop()

    # ------------------------------------------------------------------ #
    #  查询
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> ProcessRunner | None:
        """按名称获取 runner，不存在返回 None。"""
        return self._runners.get(name)

    @property
    def runners(self) -> dict[str, ProcessRunner]:
        """所有 runner 的字典副本。"""
        return dict(self._runners)

    @property
    def running_count(self) -> int:
        """当前正在运行的进程数。"""
        return sum(1 for r in self._runners.values() if r.is_running)

    # ------------------------------------------------------------------ #
    #  内部回调
    # ------------------------------------------------------------------ #

    def _on_state(self, name: str, state: str, code: int, pid: int) -> None:
        """单个 runner 状态变化回调，转发为聚合信号。"""
        self.state_changed_any.emit(name)
