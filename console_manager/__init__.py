"""控制台管理器包。

PyQt6 重写版模块结构：
- app.py            应用入口（日志 + 异常钩子 + QApplication）
- config.py         配置/设置读写（原子写）
- process_manager.py 进程管理核心（QThread 模型 + 队列缓冲）
- service_manager.py 服务管理核心（pywin32 + 后台刷新）
- tray.py           系统托盘（QSystemTrayIcon，同线程模型）
- ui/               界面层（主题 / 对话框 / 视图 / 主窗口）
"""

__version__ = "3.0.0"
