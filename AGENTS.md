# ConsoleManager 项目修改指南

## 项目概述
控制台管理器是一个Windows桌面应用程序，用于管理多个控制台进程和服务。

## 项目结构
```
ConsoleManager/
├── console_manager/
│   ├── __init__.py
│   ├── console_manager.py      # 主窗口和应用程序逻辑
│   ├── console_tab.py          # 控制台标签页组件
│   ├── tray_manager.py         # 系统托盘管理
│   ├── scrolled_notebook.py    # 可滚动标签页控件
│   ├── constants.py            # 主题和常量定义
│   └── utils/
├── main.py                      # 程序入口
├── icon.ico / icon.png          # 应用图标
└── _doc/                        # 文档和截图
```

## 关键组件修改指南

### 1. 系统托盘 (tray_manager.py)

#### 托盘菜单动态更新
托盘菜单通过 `get_menu()` 方法动态生成，每次右键点击托盘图标时都会重新获取当前服务状态。

```python
def get_menu(self, icon=None):
    """动态获取托盘菜单（在每次右键显示时调用）"""
    # 每次显示菜单前会刷新服务状态
    self.update_menu()
    # ... 构建菜单项
    return pystray.Menu(*menu_items)
```

#### 托盘点击行为
- **左键点击**: 切换窗口显示/隐藏状态 (`on_tray_click` -> `toggle_window`)
- **右键点击**: 显示动态菜单 (通过 `get_menu` 获取最新状态)

#### 修改托盘菜单项
在 `get_menu()` 方法中修改菜单结构。菜单项包括：
- 显示/隐藏界面
- 服务管理子菜单（带运行/停止/重启控制）
- 控制台管理子菜单（带运行/停止/重启控制）
- 运行所有控制台 / 停止所有控制台
- 退出

### 2. 主窗口行为 (console_manager.py)

#### 窗口关闭行为
点叉叉时窗口会最小化到托盘而不是退出：
```python
def setup_window_events(self):
    # 窗口关闭事件 - 点叉叉最小化到托盘
    self.root.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)
```

#### 最小化到托盘
```python
def minimize_to_tray(self):
    """最小化到系统托盘"""
    self.root.withdraw()
```

#### 完全退出应用
退出应用程序需要调用 `exit_app()` 方法（在 console_manager.py 中），它会：
1. 停止所有控制台进程
2. 保存配置和设置
3. 停止托盘图标
4. 销毁窗口

### 3. 服务状态管理

#### 更新服务状态
服务状态存储在 `self.services` 列表中，状态字段为 `status`，可能的值：
- `'running'` - 运行中
- `'stopped'` - 已停止
- 其他值 - 未知/中间状态

托盘菜单根据状态显示不同图标：
- `▶ ` 运行中
- `◼ ` 已停止
- `◾ ` 未知状态

### 4. 添加新功能建议

#### 添加新的托盘菜单项
在 `get_menu()` 方法中添加新的 `pystray.MenuItem`：
```python
menu_items.append(pystray.MenuItem('新功能', self.new_function_callback))
```

#### 修改窗口行为
- 最小化行为：在 `on_window_unmap()` 中修改
- 恢复行为：在 `on_window_map()` 中修改

### 5. 注意事项

- 托盘图标使用 `pystray` 库，需要 `PIL` 处理图像
- 窗口使用 `tkinter` 构建
- 所有后台操作（如启动/停止服务）应在独立线程中执行，避免阻塞UI
