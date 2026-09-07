---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '29298306-5887-418a-848c-0e62431251f0'
  PropagateID: '29298306-5887-418a-848c-0e62431251f0'
  ReservedCode1: '94cf3ce0-df03-4117-89b3-e7c922fa94f5'
  ReservedCode2: '94cf3ce0-df03-4117-89b3-e7c922fa94f5'
---

# Changelog

本文件记录 ConsoleManager 的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [3.0.0] - 2026-09-07

### 新增

- 整体迁移至 PyQt6：原生标题栏 + 菜单栏（文件/操作/视图/设置），顶栏精简为仅搜索框（Ctrl+K）
- 暗色/亮色/跟随系统三态主题，语义色柔和化（启动=柔和绿、停止=柔和红、重启=柔和橙、添加/发送=蓝）
- 图标改用 QStyle 系统图标：彩色图标保留原生配色，单色图标按主题自动染文字色，按钮采用浅色底+同色系深色图标
- 侧边栏增加「控制台 / 服务」分区标题
- 服务管理：pywin32 服务核心 + 后台定时刷新，列表列宽固定
- 进程管理：QThread 模型 + 队列缓冲读取输出，统一日志格式（时间戳+等级+模块前缀）
- 配置读写原子化（临时文件替换），应用日志 RotatingFileHandler + 全局异常钩子写入 app.log

### 变更

- 配置文件与工作目录统一以程序所在目录为基准
- 系统托盘改为 QSystemTrayIcon 同线程模型，动态菜单随进程状态刷新，最小化行为优化

### 移除

- 移除全部 tkinter 旧实现（console_manager / console_tab / scrolled_notebook / tray_manager 四个模块）
- 移除 qtawesome 图标依赖