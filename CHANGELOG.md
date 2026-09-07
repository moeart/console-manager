---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '2602b80c-ea85-40c0-bf71-2e5669dc9351'
  PropagateID: '2602b80c-ea85-40c0-bf71-2e5669dc9351'
  ReservedCode1: 'a86c7dcb-a762-405e-87ef-6be11137dda1'
  ReservedCode2: 'a86c7dcb-a762-405e-87ef-6be11137dda1'
---

# Changelog

本文件记录 ConsoleManager 的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [3.2.0] - 2026-09-07

### 新增

- 工具栏重做：按钮带图标+文字，功能随标签页切换（服务页=服务操作，控制台页=控制台操作）
- 服务列表每行首列新增状态图标：运行中=绿色播放三角、已停止=红色方块
- 控制台页顶部操作按钮收归工具栏，仅保留输出与命令发送
- 控制台页工具栏新增「删除控制台」按钮（带确认）
- 自绘矢量图标集：启动=绿三角、停止=红方块、重启=双箭头循环、刷新=单向环形箭头、新建控制台=终端符号、添加服务=文件夹加号，统一尺寸与颜色语义
- 服务表格选中行整行高亮为 Windows 蓝（原样式浅灰不可辨 + 单元格竖线误导）

### 变更

- 移除服务页/控制台页顶部重复操作按钮，统一由工具栏承担
- 移除旧版死信号（add_requested/refresh_requested 与 ConsoleView 的启停信号）
- 版本号 3.0.0 → 3.2.0

### 修复

- 修复服务列表 running 状态图标绘制崩溃（drawPolygon 浮点参数 PyQt6 不兼容）
- 修复「删除控制台」按钮无效（triggered 的 bool 参数被误作控制台名传入）

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