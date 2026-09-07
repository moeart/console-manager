"""服务管理核心模块。

负责 Windows 服务的查询、启动、停止、重启，以及后台周期刷新。
所有耗时操作在后台线程执行，通过 Qt 信号通知 UI/托盘层。

优先使用 pywin32 直连 SCM（性能好、信息全），无 pywin32 时自动降级为
subprocess + sc/net 命令行，保证纯源码环境也能运行。
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# pywin32 可选导入
# ---------------------------------------------------------------------------
try:
    import win32service  # noqa: F401 — 用于常量
    import win32serviceutil
    import win32api  # noqa: F401 — 确保可用

    _HAS_PYWIN32 = True
except ImportError:
    _HAS_PYWIN32 = False
    logger.warning("未安装 pywin32，服务管理将降级为 subprocess 命令行模式")

# ---------------------------------------------------------------------------
# 状态常量映射
# ---------------------------------------------------------------------------
# pywin32 SERVICE_STATUS.dwCurrentState 取值
_SERVICE_RUNNING = 0x00000004
_SERVICE_STOPPED = 0x00000001
_SERVICE_START_PENDING = 0x00000002
_SERVICE_STOP_PENDING = 0x00000003
_SERVICE_CONTINUE_PENDING = 0x00000005
_SERVICE_PAUSE_PENDING = 0x00000006
_SERVICE_PAUSED = 0x00000007


def _map_win32_state(state: int) -> str:
    """将 pywin32 dwCurrentState 数值映射为统一状态字符串。"""
    if state == _SERVICE_RUNNING:
        return "running"
    if state == _SERVICE_STOPPED:
        return "stopped"
    if state in (_SERVICE_START_PENDING, _SERVICE_CONTINUE_PENDING):
        return "starting"
    if state in (_SERVICE_STOP_PENDING, _SERVICE_PAUSE_PENDING):
        return "stopping"
    if state == _SERVICE_PAUSED:
        return "paused"
    return "unknown"


def _parse_sc_query_state(text: str) -> str:
    """从 ``sc query`` 输出中解析状态行。

    典型输出行（大小写和空格不定）::

        STATE              : 4  RUNNING
        STATE              : 1  STOPPED

    本函数对大小写和空白做容错处理。
    """
    for line in text.splitlines():
        upper = line.strip().upper()
        if not upper.startswith("STATE"):
            continue
        # 取冒号后的部分
        if ":" in line:
            after_colon = line.split(":", 1)[1].strip()
        else:
            after_colon = upper  # 退化处理
        after_upper = after_colon.upper()
        if "RUNNING" in after_upper:
            return "running"
        if "STOPPED" in after_upper:
            return "stopped"
        if "START_PENDING" in after_upper or "CONTINUE_PENDING" in after_upper:
            return "starting"
        if "STOP_PENDING" in after_upper or "PAUSE_PENDING" in after_upper:
            return "stopping"
        if "PAUSED" in after_upper:
            return "paused"
        # 有 STATE 行但未识别具体值
        return "unknown"
    return "unknown"


# ---------------------------------------------------------------------------
# 命令行降级辅助
# ---------------------------------------------------------------------------
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _run_sc(args: list[str], timeout: float = 15.0) -> subprocess.CompletedProcess:
    """运行 sc.exe，附加窗口抑制标志。"""
    return subprocess.run(
        ["sc"] + args,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
        timeout=timeout,
    )


def _run_net(args: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    """运行 net start/stop，附加窗口抑制标志。"""
    return subprocess.run(
        ["net"] + args,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# ServiceManager
# ---------------------------------------------------------------------------
class ServiceManager(QObject):
    """Windows 服务管理器。

    负责：
    - 维护已配置服务的状态缓存
    - 后台查询服务状态（不阻塞 UI）
    - 后台执行启动/停止/重启操作
    - 通过 Qt 信号通知 UI 和托盘

    线程安全说明：
    - ``self._services`` 的读写均在 ``self._lock`` 保护下进行
    - 每次发出 ``services_updated`` 信号时构造全新列表对象，
      避免跨线程引用被外部修改
    - 后台线程只做数据查询和 emit，绝不触碰 QWidget
    """

    # ---- 信号 ----
    #: 服务列表快照已更新。参数: ``[{name, display_name, status}, ...]``
    services_updated = pyqtSignal(list)

    #: 单次启停操作完成。参数: (service_name, action, success, message)
    action_finished = pyqtSignal(str, str, bool, str)

    # ---- 类属性 ----
    #: restart 中等待服务停止的最大秒数
    RESTART_STOP_TIMEOUT = 15
    #: 轮询间隔（秒）
    RESTART_POLL_INTERVAL = 0.5

    def __init__(self, configs: list, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._refresh_lock = threading.Lock()  # 防刷新重入
        self._action_lock = threading.Lock()   # 防同服务并发启停
        self._refreshing = False               # 轻量标志，配合 _refresh_lock
        self._services: list[dict] = []
        self._timer: Optional[QTimer] = None
        self._set_services_locked(configs)
        logger.info("ServiceManager 已初始化，共 %d 个服务", len(self._services))

    # ------------------------------------------------------------------
    # 内部缓存操作（调用方自行加锁）
    # ------------------------------------------------------------------
    def _set_services_locked(self, configs: list) -> None:
        """根据配置列表重建内部缓存（调用方已持锁）。"""
        new_list: list[dict] = []
        for cfg in configs:
            name = str(cfg.get("name", "")).strip()
            if not name:
                continue
            display_name = str(cfg.get("display_name", name)).strip() or name
            cached_status = str(cfg.get("status", "unknown")).strip() or "unknown"
            new_list.append(
                {
                    "name": name,
                    "display_name": display_name,
                    "status": cached_status,
                }
            )
        self._services = new_list

    def _snapshot_locked(self) -> list[dict]:
        """生成当前缓存的深拷贝快照（调用方已持锁）。"""
        return [
            {"name": s["name"], "display_name": s["display_name"], "status": s["status"]}
            for s in self._services
        ]

    def _find_index_locked(self, name: str) -> int:
        """在缓存中查找指定服务名的索引（调用方已持锁）。"""
        for i, s in enumerate(self._services):
            if s["name"] == name:
                return i
        return -1

    def _emit_snapshot(self) -> None:
        """生成快照并发出 services_updated 信号。"""
        with self._lock:
            snapshot = self._snapshot_locked()
        self.services_updated.emit(snapshot)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def statuses(self) -> list:
        """返回当前缓存快照（非阻塞）。

        供托盘打开菜单时立即使用，不需要等待后台刷新。
        """
        with self._lock:
            return self._snapshot_locked()

    def set_services(self, configs: list) -> None:
        """批量替换服务列表。"""
        with self._lock:
            self._set_services_locked(configs)
        self._emit_snapshot()

    def service_exists(self, name: str) -> bool:
        """检查指定名称的 Windows 服务是否存在。"""
        return self._query_status(name) is not None

    def add_service(self, name: str, display_name: str) -> bool:
        """添加一个服务到管理列表。

        会先验证服务是否存在（查一次状态），不存在返回 False。
        """
        name = name.strip()
        display_name = (display_name or name).strip() or name

        status = self._query_status(name)
        if status is None:
            logger.warning("添加服务失败：服务 '%s' 不存在", name)
            return False

        with self._lock:
            if self._find_index_locked(name) >= 0:
                logger.warning("添加服务失败：服务 '%s' 已在列表中", name)
                return False
            self._services.append(
                {"name": name, "display_name": display_name, "status": status}
            )
        self._emit_snapshot()
        logger.info("已添加服务: %s (%s)", name, display_name)
        return True

    def remove_service(self, name: str) -> bool:
        """从管理列表中移除一个服务。"""
        with self._lock:
            idx = self._find_index_locked(name)
            if idx < 0:
                return False
            del self._services[idx]
        self._emit_snapshot()
        logger.info("已移除服务: %s", name)
        return True

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------
    def _query_status(self, name: str) -> Optional[str]:
        """查询单个服务的实时状态。

        :return: 状态字符串，若服务不存在返回 None。
        """
        if _HAS_PYWIN32:
            try:
                # QueryServiceStatus 返回 7 元组:
                # (dwServiceType, dwCurrentState, dwControlsAccepted,
                #  dwWin32ExitCode, dwServiceSpecificExitCode, dwCheckPoint, dwWaitHint)
                status_tuple = win32serviceutil.QueryServiceStatus(name)
                return _map_win32_state(status_tuple[1])
            except Exception as exc:
                # pywintypes.error 的 winerror 1060 = 服务不存在
                err_low = str(exc).lower()
                if "1060" in err_low or "not exist" in err_low or "找不到" in err_low:
                    return None
                logger.error("pywin32 查询服务 '%s' 状态失败: %s", name, exc)
                return "unknown"

        # 降级路径
        try:
            result = _run_sc(["query", name])
            if result.returncode != 0:
                # sc query 不存在的服务返回码非 0
                stderr_lower = (result.stderr or "").lower()
                if "1060" in stderr_lower or "does not exist" in stderr_lower:
                    return None
                return "unknown"
            return _parse_sc_query_state(result.stdout or "")
        except Exception as exc:
            logger.error("sc query 查询服务 '%s' 状态失败: %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # 后台刷新
    # ------------------------------------------------------------------
    def refresh_async(self) -> None:
        """请求后台刷新服务状态（非阻塞）。

        若已有刷新线程在跑则直接返回，避免堆叠线程。
        """
        if not self._refresh_lock.acquire(blocking=False):
            # 已有刷新在进行
            return
        # 成功获取锁
        t = threading.Thread(target=self._refresh_worker, daemon=True)
        t.start()

    def _refresh_worker(self) -> None:
        """后台刷新工作线程。"""
        try:
            # 获取当前服务名列表的快照（持锁时间极短）
            with self._lock:
                names = [s["name"] for s in self._services]

            # 逐个查询（不持锁，避免长时间占用）
            results: dict[str, str] = {}
            for name in names:
                status = self._query_status(name)
                results[name] = status if status else "unknown"

            # 更新缓存
            with self._lock:
                for s in self._services:
                    new_status = results.get(s["name"])
                    if new_status:
                        s["status"] = new_status
                snapshot = self._snapshot_locked()

            self.services_updated.emit(snapshot)
        except Exception as exc:
            logger.error("后台刷新服务状态失败: %s", exc)
        finally:
            self._refresh_lock.release()

    # ------------------------------------------------------------------
    # 启停操作
    # ------------------------------------------------------------------
    def start(self, name: str) -> None:
        """启动服务（后台执行，不阻塞 UI）。"""
        self._run_action(name, "start")

    def stop(self, name: str) -> None:
        """停止服务（后台执行，不阻塞 UI）。"""
        self._run_action(name, "stop")

    def restart(self, name: str) -> None:
        """重启服务（后台执行，不阻塞 UI）。"""
        self._run_action(name, "restart")

    def _run_action(self, name: str, action: str) -> None:
        """在后台线程中执行启停操作。"""
        # 以服务名+操作类型做粒度的并发控制
        lock_key = (name, action)
        # 使用单个 action_lock 防止同时对同一服务执行多个操作
        # 这里简化处理：直接起线程，内部有 _action_lock 保护
        if not self._action_lock.acquire(blocking=False):
            logger.warning("已有启停操作在进行中，忽略 %s %s", action, name)
            return

        def _worker() -> None:
            try:
                success, message = self._do_action(name, action)
                self.action_finished.emit(name, action, success, message)
            except Exception as exc:
                logger.error("执行 %s %s 时异常: %s", action, name, exc)
                self.action_finished.emit(
                    name, action, False, f"操作异常: {exc}"
                )
            finally:
                self._action_lock.release()
                # 操作完成后触发一次刷新
                self.refresh_async()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _do_action(self, name: str, action: str) -> tuple[bool, str]:
        """实际执行启停操作（在后台线程中调用）。

        :return: (success, message)
        """
        if action == "start":
            return self._do_start(name)
        if action == "stop":
            return self._do_stop(name)
        if action == "restart":
            return self._do_restart(name)
        return False, f"未知操作: {action}"

    def _do_start(self, name: str) -> tuple[bool, str]:
        """启动服务。"""
        if _HAS_PYWIN32:
            try:
                win32serviceutil.StartService(name)
                return True, f"服务 {name} 启动成功"
            except Exception as exc:
                logger.error("pywin32 启动服务 '%s' 失败: %s", name, exc)
                return False, f"启动失败: {exc}"
        # 降级
        try:
            result = _run_net(["start", name])
            if result.returncode == 0:
                return True, f"服务 {name} 启动成功"
            return False, f"启动失败: {(result.stderr or '').strip()}"
        except Exception as exc:
            return False, f"启动异常: {exc}"

    def _do_stop(self, name: str) -> tuple[bool, str]:
        """停止服务。"""
        if _HAS_PYWIN32:
            try:
                win32serviceutil.StopService(name)
                return True, f"服务 {name} 停止成功"
            except Exception as exc:
                logger.error("pywin32 停止服务 '%s' 失败: %s", name, exc)
                return False, f"停止失败: {exc}"
        # 降级
        try:
            result = _run_net(["stop", name])
            if result.returncode == 0:
                return True, f"服务 {name} 停止成功"
            return False, f"停止失败: {(result.stderr or '').strip()}"
        except Exception as exc:
            return False, f"停止异常: {exc}"

    def _do_restart(self, name: str) -> tuple[bool, str]:
        """重启服务：stop → 轮询等待 stopped（超时 15s）→ start。"""
        # 1. 停止
        stop_ok, stop_msg = self._do_stop(name)
        if not stop_ok:
            # 停止失败也要尝试后续，但标记为可能未完全停止
            logger.warning("restart: 停止 %s 时: %s（继续等待）", name, stop_msg)

        # 2. 轮询等待服务变为 stopped
        deadline = time.monotonic() + self.RESTART_STOP_TIMEOUT
        reached_stopped = False
        while time.monotonic() < deadline:
            status = self._query_status(name)
            if status == "stopped":
                reached_stopped = True
                break
            if status is None:
                # 服务可能已不存在
                break
            time.sleep(self.RESTART_POLL_INTERVAL)

        if not reached_stopped:
            # 超时仍未停止，直接尝试启动
            logger.warning(
                "restart: 等待 %s 停止超时（%ds），尝试直接启动",
                name,
                self.RESTART_STOP_TIMEOUT,
            )

        # 3. 启动
        start_ok, start_msg = self._do_start(name)
        if start_ok:
            return True, f"服务 {name} 重启成功"
        return False, f"重启失败（停止阶段: {stop_msg}, 启动阶段: {start_msg}）"

    # ------------------------------------------------------------------
    # 周期刷新
    # ------------------------------------------------------------------
    def start_periodic_refresh(
        self, interval_ms: int = 30000, parent_widget: Optional[QObject] = None
    ) -> None:
        """启动周期性刷新定时器。

        .. note::
            QTimer 必须在有事件循环的线程（主线程）中创建。
            此方法应在 MainWindow / 主线程中调用。

        :param interval_ms: 刷新间隔，毫秒，默认 30000（30 秒）
        :param parent_widget: 父 QObject，定时器将附加到其生命周期。
            传入 None 时定时器归 self 管理，需手动调 :meth:`stop_periodic_refresh`。
        """
        self.stop_periodic_refresh()
        self._timer = QTimer(parent_widget or self)
        self._timer.timeout.connect(self.refresh_async)
        self._timer.start(interval_ms)
        logger.info("周期刷新已启动，间隔 %dms", interval_ms)

    def stop_periodic_refresh(self) -> None:
        """停止周期性刷新定时器。"""
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
            logger.info("周期刷新已停止")
