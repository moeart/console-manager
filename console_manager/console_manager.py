import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import subprocess
import threading
import os
import sys
import yaml
import json
from pathlib import Path
import logging
from datetime import datetime
import winshell
import winreg
from .constants import FLAT_THEME, CONFIG_FILE, SETTINGS_FILE
from .tray_manager import TrayManager
from .scrolled_notebook import ScrolledNotebook
from .console_tab import ConsoleTab

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConsoleManager:
    def __init__(self, root):
        self.root = root
        self.root.title("控制台管理器")
        
        # 应用扁平化主题
        self.setup_flat_theme()
        
        # 控制台配置
        self.consoles = {}
        self.services = []
        self.current_tabs = {}
        self.settings = {}
        
        # 加载配置
        self.load_config()
        self.load_settings()
        
        # 设置窗口大小
        if 'window_size' in self.settings:
            width, height = self.settings['window_size']
            self.root.geometry(f"{width}x{height}")
        else:
            # 默认大小
            self.root.geometry("800x580")
        
        # 绑定窗口大小改变事件
        self.root.bind('<Configure>', self.on_window_configure)
        
        # 设置窗口图标
        self.setup_icon()
        
        # 创建GUI
        self.create_menu()
        self.create_toolbar()
        self.create_notebook()
        
        # 创建服务管理标签页
        self.create_service_tab()
        
        self.create_statusbar()
        
        # 启动时自动运行保存的控制台
        self.start_saved_consoles()
        
        # 系统托盘
        self.tray_manager = TrayManager(self)
        # 启动托盘图标
        self.tray_manager.run()
        
        # 根据设置决定是否隐藏主窗口
        if self.settings.get('start_hidden', False):
            self.root.withdraw()
        
        # 窗口事件绑定
        self.setup_window_events()
        
        # 检查开机启动设置
        if self.settings.get('auto_start_app', False):
            self.set_auto_start(True)
    
    def setup_flat_theme(self):
        """设置扁平化主题"""
        style = ttk.Style()
        
        # 创建扁平化主题
        style.theme_create('flat', parent='clam', settings={
            'TFrame': {
                'configure': {
                    'background': FLAT_THEME['bg_dark'],
                    'relief': 'flat'
                }
            },
            'TLabel': {
                'configure': {
                    'background': FLAT_THEME['bg_dark'],
                    'foreground': FLAT_THEME['text_light'],
                    'font': ('微软雅黑', 10)
                }
            },
            'Title.TLabel': {
                'configure': {
                    'font': ('微软雅黑', 11, 'bold'),
                    'foreground': FLAT_THEME['primary_light']
                }
            },
            'TButton': {
                'configure': {
                    'background': FLAT_THEME['primary'],
                    'foreground': FLAT_THEME['text_light'],
                    'borderwidth': 0,
                    'relief': 'flat',
                    'padding': (10, 5),
                    'font': ('微软雅黑', 9)
                },
                'map': {
                    'background': [
                        ('pressed', FLAT_THEME['primary_dark']),
                        ('active', FLAT_THEME['primary_light'])
                    ],
                    'foreground': [
                        ('pressed', FLAT_THEME['text_light']),
                        ('active', FLAT_THEME['text_light'])
                    ]
                }
            },
            'TEntry': {
                'configure': {
                    'fieldbackground': FLAT_THEME['bg_darker'],
                    'foreground': FLAT_THEME['text_light'],
                    'insertcolor': FLAT_THEME['text_light'],
                    'borderwidth': 1,
                    'relief': 'flat',
                    'padding': (5, 5)
                }
            },
            'Flat.TEntry': {
                'configure': {
                    'fieldbackground': FLAT_THEME['bg_darker'],
                    'foreground': FLAT_THEME['text_light'],
                    'borderwidth': 0,
                    'relief': 'flat'
                }
            },
            'TCombobox': {
                'configure': {
                    'fieldbackground': FLAT_THEME['bg_darker'],
                    'foreground': FLAT_THEME['text_light'],
                    'background': FLAT_THEME['bg_darker'],
                    'borderwidth': 0,
                    'relief': 'flat'
                }
            },
            'TCheckbutton': {
                'configure': {
                    'background': FLAT_THEME['bg_dark'],
                    'foreground': FLAT_THEME['text_light'],
                    'indicatorbackground': FLAT_THEME['bg_darker'],
                    'indicatormargin': (2, 2, 2, 2)
                }
            },
            'Flat.TCheckbutton': {
                'configure': {
                    'background': FLAT_THEME['bg_dark'],
                    'foreground': FLAT_THEME['text_light'],
                    'indicatorbackground': FLAT_THEME['bg_darker'],
                    'indicatormargin': (2, 2, 2, 2)
                }
            },
            'Horizontal.TScrollbar': {
                'configure': {
                    'background': FLAT_THEME['bg_darker'],
                    'troughcolor': FLAT_THEME['bg_dark'],
                    'borderwidth': 0,
                    'relief': 'flat'
                }
            },
            'TNotebook': {
                'configure': {
                    'background': FLAT_THEME['bg_dark'],
                    'borderwidth': 0,
                    'tabmargins': (2, 0, 2, 0)
                }
            },
            'TNotebook.Tab': {
                'configure': {
                    'background': FLAT_THEME['bg_darker'],
                    'foreground': FLAT_THEME['text_light'],
                    'padding': (18, 7),
                    'borderwidth': 0,
                    'focuscolor': 'none',
                    'font': ('微软雅黑', 10)
                },
                'map': {
                    'background': [('selected', FLAT_THEME['primary']), ('active', FLAT_THEME['bg_dark'])],
                    'foreground': [('selected', FLAT_THEME['text_light']), ('active', FLAT_THEME['text_light'])]
                }
            }
        })
        
        style.theme_use('flat')
        
        # 设置根窗口背景
        self.root.configure(bg=FLAT_THEME['bg_dark'])
    
    def setup_icon(self):
        """设置窗口图标"""
        icon_paths = [
            'icon.png',
            'icon.ico',
            str(Path(sys.executable).parent / 'icon.png'),
            str(Path(sys.executable).parent / 'icon.ico')
        ]
        
        for path in icon_paths:
            if os.path.exists(path):
                try:
                    if path.endswith('.png'):
                        img = tk.PhotoImage(file=path)
                        self.root.iconphoto(True, img)
                    else:
                        self.root.iconbitmap(path)
                    logger.info(f"已加载图标: {path}")
                    break
                except Exception as e:
                    logger.warning(f"加载图标失败 {path}: {e}")
    
    def setup_window_events(self):
        """设置窗口事件"""
        # 窗口关闭事件
        self.root.protocol('WM_DELETE_WINDOW', self.exit_app)
        
        # 窗口状态变化事件
        self.root.bind('<Unmap>', self.on_window_unmap)
        self.root.bind('<Map>', self.on_window_map)
    
    def minimize_to_tray(self):
        """最小化到系统托盘"""
        self.root.withdraw()
        
        # 显示通知
        if self.tray_manager and self.tray_manager.tray_icon:
            self.tray_manager.tray_icon.notify(
                "控制台管理器已最小化到托盘",
                "程序仍在后台运行"
            )
    
    def on_window_unmap(self, event):
        """窗口最小化时"""
        pass
    
    def on_window_map(self, event):
        """窗口恢复时"""
        pass
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root, bg=FLAT_THEME['bg_dark'], fg=FLAT_THEME['text_light'])
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0, bg=FLAT_THEME['bg_dark'], fg=FLAT_THEME['text_light'])
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="新建控制台", command=self.new_console_dialog, accelerator="Ctrl+N")
        file_menu.add_command(label="导入配置", command=self.import_config)
        file_menu.add_command(label="导出配置", command=self.export_config)
        file_menu.add_separator()
        file_menu.add_command(label="保存配置", command=self.save_config, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="最小化到托盘", command=self.minimize_to_tray)
        file_menu.add_command(label="退出", command=self.exit_app, accelerator="Alt+F4")
        
        # 编辑菜单
        edit_menu = tk.Menu(menubar, tearoff=0, bg=FLAT_THEME['bg_dark'], fg=FLAT_THEME['text_light'])
        menubar.add_cascade(label="编辑", menu=edit_menu)
        edit_menu.add_command(label="编辑控制台", command=self.edit_console_dialog, accelerator="Ctrl+E")
        edit_menu.add_command(label="复制配置", command=self.copy_console_config)
        edit_menu.add_command(label="删除控制台", command=self.delete_console, accelerator="Delete")
        edit_menu.add_separator()
        edit_menu.add_command(label="全局设置", command=self.global_settings_dialog)
        
        # 控制菜单
        control_menu = tk.Menu(menubar, tearoff=0, bg=FLAT_THEME['bg_dark'], fg=FLAT_THEME['text_light'])
        menubar.add_cascade(label="控制", menu=control_menu)
        control_menu.add_command(label="运行所有", command=self.run_all_consoles)
        control_menu.add_command(label="停止所有", command=self.stop_all_consoles)
        control_menu.add_separator()
        control_menu.add_command(label="重启当前", command=self.restart_current_console)
        
        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0, bg=FLAT_THEME['bg_dark'], fg=FLAT_THEME['text_light'])
        menubar.add_cascade(label="视图", menu=view_menu)
        view_menu.add_command(label="刷新", command=self.refresh_consoles, accelerator="F5")
        view_menu.add_separator()
        view_menu.add_command(label="显示所有输出", command=self.show_all_outputs)
        view_menu.add_command(label="清除所有输出", command=self.clear_all_outputs)
        view_menu.add_separator()
        view_menu.add_command(label="总是置顶", command=self.toggle_always_on_top)
        always_on_top_var = tk.BooleanVar(value=self.settings.get('always_on_top', False))
        view_menu.add_checkbutton(label="置顶", variable=always_on_top_var, 
                                 command=lambda: self.set_always_on_top(always_on_top_var.get()))
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0, bg=FLAT_THEME['bg_dark'], fg=FLAT_THEME['text_light'])
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="检查更新", command=self.check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(label="关于", command=self.show_about)
        
        # 绑定快捷键
        self.root.bind('<Control-n>', lambda e: self.new_console_dialog())
        self.root.bind('<Control-s>', lambda e: self.save_config())
        self.root.bind('<Control-e>', lambda e: self.edit_console_dialog())
        self.root.bind('<Delete>', lambda e: self.delete_console())
        self.root.bind('<F5>', lambda e: self.refresh_consoles())
        self.root.bind('<Alt-F4>', lambda e: self.exit_app())
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = tk.Frame(self.root, bg=FLAT_THEME['bg_darker'], height=40)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=0, pady=0)
        
        # 创建按钮组
        button_data = [
            ("新建", self.new_console_dialog, FLAT_THEME['primary'], "新建控制台"),
            ("运行", self.run_console, FLAT_THEME['success'], "运行当前控制台"),
            ("停止", self.stop_console, FLAT_THEME['error'], "停止当前控制台"),
            ("重启", self.restart_current_console, FLAT_THEME['warning'], "重启当前控制台"),
            ("编辑", self.edit_console_dialog, FLAT_THEME['info'], "编辑配置"),
            ("保存", self.save_config, FLAT_THEME['primary'], "保存配置")
        ]
        
        for text, command, color, tooltip in button_data:
            btn = tk.Button(
                toolbar,
                text=text,
                command=command,
                bg=color,
                fg=FLAT_THEME['text_light'],
                font=('微软雅黑', 10, 'bold'),
                relief='flat',
                padx=16,
                pady=7,
                cursor='hand2',
                activebackground=self.adjust_color(color, -20),
                borderwidth=0,
                highlightthickness=0
            )
            btn.pack(side=tk.LEFT, padx=4, pady=6)
            
            # 工具提示
            self.create_tooltip(btn, tooltip)

        # 添加标签页翻页按钮
        self.right_tab_btn = tk.Button(
            toolbar,
            text="▶",
            command=self.scroll_tabs_right,
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9),
            relief='flat',
            width=2,
            cursor='hand2',
            state="disabled"
        )
        self.right_tab_btn.pack(side=tk.RIGHT, padx=(2, 15))
        
        self.left_tab_btn = tk.Button(
            toolbar,
            text="◀",
            command=self.scroll_tabs_left,
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9),
            relief='flat',
            width=2,
            cursor='hand2',
            state="disabled"
        )
        self.left_tab_btn.pack(side=tk.RIGHT, padx=(2, 2))
        
        # 搜索框
        search_frame = tk.Frame(toolbar, bg=FLAT_THEME['bg_darker'])
        search_frame.pack(side=tk.RIGHT, padx=10, pady=5)
        
        tk.Label(
            search_frame,
            text="搜索:",
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9)
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            relief='flat',
            insertbackground=FLAT_THEME['text_light'],
            width=25,
            font=('微软雅黑', 9)
        )
        search_entry.pack(side=tk.LEFT, padx=(0, 5))
        search_entry.bind('<KeyRelease>', self.filter_consoles)
        
        # 搜索按钮
        search_btn = tk.Button(
            search_frame,
            text="×",
            command=self.clear_search,
            bg=FLAT_THEME['disabled'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9),
            relief='flat',
            width=2,
            cursor='hand2'
        )
        search_btn.pack(side=tk.LEFT, padx=(0, 10))
    
    def create_tooltip(self, widget, text):
        """创建工具提示"""
        def show_tooltip(event):
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(
                tooltip,
                text=text,
                bg=FLAT_THEME['bg_darker'],
                fg=FLAT_THEME['text_light'],
                relief='solid',
                borderwidth=1,
                font=('微软雅黑', 8)
            )
            label.pack()
            
            widget.tooltip = tooltip
        
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                delattr(widget, 'tooltip')
        
        widget.bind('<Enter>', show_tooltip)
        widget.bind('<Leave>', hide_tooltip)
    
    def adjust_color(self, color, amount):
        """调整颜色亮度"""
        if color.startswith('#'):
            color = color[1:]
        
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        
        r = max(0, min(255, r + amount))
        g = max(0, min(255, g + amount))
        b = max(0, min(255, b + amount))
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def create_notebook(self):
        """创建可滚动的标签页控件"""
        self.notebook = ScrolledNotebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 0))
        
        # 绑定标签页切换事件
        self.notebook.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # 服务管理相关
        self.service_tab_frame = None
    
    def create_service_tab(self):
        """创建服务管理标签页"""
        # 创建服务管理标签页框架
        self.service_tab_frame = ttk.Frame(self.notebook.notebook)
        
        # 添加到标签页控件的第一个位置
        self.notebook.add(self.service_tab_frame, text="服务管理", sticky=tk.N+tk.S+tk.E+tk.W)
        
        # 切换到服务管理标签页
        self.notebook.notebook.select(0)
        
        # 创建服务管理界面
        self.setup_service_management_ui()
    
    def setup_service_management_ui(self):
        """设置服务管理界面"""
        # 主框架
        main_frame = ttk.Frame(self.service_tab_frame, style='Flat.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        

        
        # 按钮框架
        button_frame = ttk.Frame(main_frame, style='Flat.TFrame')
        button_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 添加服务按钮
        add_service_btn = tk.Button(
            button_frame,
            text="添加服务",
            command=self.add_service_dialog,
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=16,
            pady=7,
            cursor='hand2'
        )
        add_service_btn.pack(side=tk.LEFT, padx=5)
        
        # 刷新服务按钮
        refresh_service_btn = tk.Button(
            button_frame,
            text="刷新",
            command=self.refresh_services,
            bg=FLAT_THEME['info'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=16,
            pady=7,
            cursor='hand2'
        )
        refresh_service_btn.pack(side=tk.LEFT, padx=5)
        
        # 服务列表框架
        list_frame = ttk.Frame(main_frame, style='Flat.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设置monokai风格的颜色
        monokai_colors = {
            'bg': '#272822',
            'fg': '#f8f8f2',
            'header_bg': '#3e3d32',
            'header_fg': '#f8f8f2',
            'grid_color': '#49483e',
            'even_row': '#272822',
            'odd_row': '#2d2e27',
            'running': '#a6e22e',
            'stopped': '#f92672',
            'other': '#f4bf75'
        }
        
        # 配置Treeview样式
        style = ttk.Style()
        style.configure('Monokai.Treeview',
                       background=monokai_colors['bg'],
                       foreground=monokai_colors['fg'],
                       fieldbackground=monokai_colors['bg'])
        style.configure('Monokai.Treeview.Heading',
                       background=monokai_colors['header_bg'],
                       foreground=monokai_colors['header_fg'])
        style.map('Monokai.Treeview',
                 background=[('selected', '#49483e')])
        
        # 服务列表
        self.service_tree = ttk.Treeview(
            list_frame,
            columns=('name', 'status', 'display_name'),
            show='headings',
            style='Monokai.Treeview'
        )
        
        # 设置列
        self.service_tree.heading('name', text='  服务名称')
        self.service_tree.heading('status', text='  状态')
        self.service_tree.heading('display_name', text='  显示名称')
        
        # 设置列宽和对齐方式
        self.service_tree.column('name', width=150, anchor='w')
        self.service_tree.column('status', width=120, anchor='w')
        self.service_tree.column('display_name', width=400, anchor='w')
        
        # 添加网格线效果
        style.configure('Monokai.Treeview',
                       background=monokai_colors['bg'],
                       foreground=monokai_colors['fg'],
                       fieldbackground=monokai_colors['bg'],
                       borderwidth=1,
                       relief='solid')
        style.configure('Monokai.Treeview.Heading',
                       background=monokai_colors['header_bg'],
                       foreground=monokai_colors['header_fg'],
                       borderwidth=1,
                       relief='solid')
        
        # 设置表头对齐方式
        self.service_tree.heading('name', text='  服务名称', anchor='w')
        self.service_tree.heading('status', text='  状态', anchor='w')
        self.service_tree.heading('display_name', text='  显示名称', anchor='w')
        
        # 添加网格线效果
        self.service_tree.tag_configure('even', background=monokai_colors['even_row'])
        self.service_tree.tag_configure('odd', background=monokai_colors['odd_row'])
        
        # 状态颜色标签
        self.service_tree.tag_configure('running', foreground=monokai_colors['running'])
        self.service_tree.tag_configure('stopped', foreground=monokai_colors['stopped'])
        self.service_tree.tag_configure('other', foreground=monokai_colors['other'])
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.service_tree.yview)
        self.service_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.service_tree.pack(fill=tk.BOTH, expand=True)
        
        # 服务操作按钮框架
        action_frame = ttk.Frame(main_frame, style='Flat.TFrame')
        action_frame.pack(fill=tk.X, pady=15)
        
        # 启动服务按钮
        start_service_btn = tk.Button(
            action_frame,
            text="启动服务",
            command=self.start_service,
            bg=FLAT_THEME['success'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=16,
            pady=7,
            cursor='hand2'
        )
        start_service_btn.pack(side=tk.LEFT, padx=5)
        
        # 停止服务按钮
        stop_service_btn = tk.Button(
            action_frame,
            text="停止服务",
            command=self.stop_service,
            bg=FLAT_THEME['error'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=16,
            pady=7,
            cursor='hand2'
        )
        stop_service_btn.pack(side=tk.LEFT, padx=5)
        
        # 删除服务按钮
        remove_service_btn = tk.Button(
            action_frame,
            text="删除服务",
            command=self.remove_service,
            bg=FLAT_THEME['warning'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=16,
            pady=7,
            cursor='hand2'
        )
        remove_service_btn.pack(side=tk.LEFT, padx=5)
        
        # 初始刷新服务列表
        self.refresh_services()
    
    def scroll_tabs_left(self):
        """向左滚动标签页"""
        self.notebook.scroll_left()
        self.update_tab_buttons_state()
    
    def scroll_tabs_right(self):
        """向右滚动标签页"""
        self.notebook.scroll_right()
        self.update_tab_buttons_state()
    
    def update_tab_buttons_state(self):
        """更新标签页按钮状态"""
        self.notebook.update_buttons_state(self.left_tab_btn, self.right_tab_btn)
    
    def create_statusbar(self):
        """创建状态栏"""
        statusbar = tk.Frame(self.root, bg=FLAT_THEME['bg_darker'], height=25)
        statusbar.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)
        
        # 左侧状态信息
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_label = tk.Label(
            statusbar,
            textvariable=self.status_var,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9)
        )
        status_label.pack(side=tk.LEFT, padx=10, pady=2)
        
        # 中间分隔符
        tk.Frame(statusbar, bg=FLAT_THEME['border'], width=1, height=15).pack(side=tk.LEFT, padx=5, pady=2)
        
        # 右侧信息
        info_frame = tk.Frame(statusbar, bg=FLAT_THEME['bg_darker'])
        info_frame.pack(side=tk.RIGHT, padx=10, pady=2)
        
        # 控制台计数
        self.console_count_var = tk.StringVar()
        self.console_count_var.set("控制台: 0")
        count_label = tk.Label(
            info_frame,
            textvariable=self.console_count_var,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9)
        )
        count_label.pack(side=tk.LEFT, padx=5)
        
        # 分隔符
        tk.Frame(info_frame, bg=FLAT_THEME['border'], width=1, height=15).pack(side=tk.LEFT, padx=5, pady=2)
        
        # 运行状态
        self.running_count_var = tk.StringVar()
        self.running_count_var.set("运行: 0")
        running_label = tk.Label(
            info_frame,
            textvariable=self.running_count_var,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['success'],
            font=('微软雅黑', 9)
        )
        running_label.pack(side=tk.LEFT, padx=5)
    
    def new_console_dialog(self):
        """新建控制台对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("新建控制台")
        dialog.geometry("620x520")
        dialog.configure(bg=FLAT_THEME['bg_dark'])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # 居中显示
        self.center_window(dialog)
        
        # 标题
        title_label = tk.Label(
            dialog,
            text="新建控制台",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['primary_light'],
            font=('微软雅黑', 15, 'bold')
        )
        title_label.pack(pady=(25, 15))
        
        # 表单框架
        form_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        form_frame.pack(fill=tk.BOTH, expand=True, padx=35, pady=10)
        
        row = 0
        
        # 名称
        tk.Label(
            form_frame,
            text="名称:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        name_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        name_entry.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E, pady=8, padx=(10, 0))
        row += 1
        
        # 程序路径
        tk.Label(
            form_frame,
            text="程序路径:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        program_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        program_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=8, padx=(10, 5))
        
        browse_btn = tk.Button(
            form_frame,
            text="浏览",
            command=lambda: self.browse_file(program_entry),
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9),
            relief='flat',
            padx=15
        )
        browse_btn.grid(row=row, column=2, sticky=tk.W, pady=8)
        row += 1
        
        # 参数
        tk.Label(
            form_frame,
            text="参数:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        args_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        args_entry.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E, pady=8, padx=(10, 0))
        row += 1
        
        # 工作目录
        tk.Label(
            form_frame,
            text="工作目录:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        workdir_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        workdir_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=8, padx=(10, 5))
        
        browse_dir_btn = tk.Button(
            form_frame,
            text="浏览",
            command=lambda: self.browse_directory(workdir_entry),
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9),
            relief='flat',
            padx=15
        )
        browse_dir_btn.grid(row=row, column=2, sticky=tk.W, pady=8)
        row += 1
        
        # 自动启动
        auto_start_var = tk.BooleanVar()
        auto_start_check = tk.Checkbutton(
            form_frame,
            text="自动启动",
            variable=auto_start_var,
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            selectcolor=FLAT_THEME['bg_darker'],
            activebackground=FLAT_THEME['bg_dark'],
            activeforeground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        )
        auto_start_check.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=8, padx=(10, 0))
        row += 1
        
        # 描述
        tk.Label(
            form_frame,
            text="描述:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.NW, pady=8)
        desc_text = scrolledtext.ScrolledText(
            form_frame,
            height=6,
            width=40,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            relief='flat'
        )
        desc_text.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=8, padx=(10, 0))
        row += 1
        
        # 按钮框架
        button_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        button_frame.pack(pady=20)
        
        def save_and_close():
            name = name_entry.get().strip()
            program = program_entry.get().strip()
            work_dir = workdir_entry.get().strip()
            args = args_entry.get().strip()
            description = desc_text.get(1.0, tk.END).strip()
            
            if not name or not program:
                messagebox.showwarning("警告", "名称和程序路径是必填项")
                return
            
            self.consoles[name] = {
                'program': program,
                'args': args,
                'work_dir': work_dir or '.',
                'description': description,
                'auto_start': auto_start_var.get()
            }
            
            self.add_console_tab(name, self.consoles[name])
            self.save_config()
            dialog.destroy()
            self.status_var.set(f"已创建控制台: {name}")
        
        # 保存按钮
        save_btn = tk.Button(
            button_frame,
            text="保存",
            command=save_and_close,
            bg=FLAT_THEME['success'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=32,
            pady=9,
            cursor='hand2',
            activebackground=self.adjust_color(FLAT_THEME['success'], -20),
            borderwidth=0
        )
        save_btn.pack(side=tk.LEFT, padx=12)
        
        # 取消按钮
        cancel_btn = tk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy,
            bg=FLAT_THEME['disabled'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=32,
            pady=9,
            cursor='hand2',
            activebackground=self.adjust_color(FLAT_THEME['disabled'], -20),
            borderwidth=0
        )
        cancel_btn.pack(side=tk.LEFT, padx=12)
        
        # 设置焦点
        name_entry.focus_set()
    
    def center_window(self, window):
        """居中窗口"""
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f'{width}x{height}+{x}+{y}')
    
    def browse_file(self, entry_widget):
        """浏览文件"""
        filename = filedialog.askopenfilename(
            title="选择程序",
            filetypes=[("可执行文件", "*.exe;*.bat;*.cmd;*.py"), ("所有文件", "*.*")]
        )
        if filename:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, filename)
    
    def browse_directory(self, entry_widget):
        """浏览目录"""
        directory = filedialog.askdirectory(title="选择工作目录")
        if directory:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, directory)
    
    def add_console_tab(self, name, config):
        """添加控制台标签页"""
        if name in self.current_tabs:
            return
        
        tab = ConsoleTab(self.notebook.notebook, name, config, self)
        self.current_tabs[name] = tab
        
        self.notebook.add(tab.tab_frame, text=name)
        self.update_status()
        self.update_tab_buttons_state()
        
        # 自动启动
        if config.get('auto_start', False):
            tab.run()
        
        # 刷新系统托盘
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.update_menu()
    
    def get_tab_id(self, name):
        """获取标签页ID"""
        if name in self.current_tabs:
            for i in range(self.notebook.notebook.index('end')):
                if self.notebook.notebook.tab(i, 'text').startswith(name):
                    return i
        return None
    
    def edit_console_dialog(self):
        """编辑控制台对话框"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("提示", "请先选择一个控制台")
            return
        
        tab_index = self.notebook.index(current_tab)
        tab_text = self.notebook.tab(tab_index, 'text')
        
        # 从标签文本中提取原始名称（移除状态文本）
        for name in self.consoles:
            if tab_text.startswith(name):
                original_name = name
                break
        else:
            return
        
        config = self.consoles[original_name]
        
        # 打开编辑对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑控制台 - {original_name}")
        dialog.geometry("620x520")
        dialog.configure(bg=FLAT_THEME['bg_dark'])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # 居中显示
        self.center_window(dialog)
        
        # 标题
        title_label = tk.Label(
            dialog,
            text=f"编辑控制台 - {original_name}",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['primary_light'],
            font=('微软雅黑', 15, 'bold')
        )
        title_label.pack(pady=(25, 15))
        
        # 表单框架
        form_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        form_frame.pack(fill=tk.BOTH, expand=True, padx=35, pady=10)
        
        row = 0
        
        # 名称
        tk.Label(
            form_frame,
            text="名称:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        name_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        name_entry.insert(0, original_name)
        name_entry.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E, pady=8, padx=(10, 0))
        row += 1
        
        # 程序路径
        tk.Label(
            form_frame,
            text="程序路径:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        program_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        program_entry.insert(0, config.get('program', ''))
        program_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=8, padx=(10, 5))
        
        browse_btn = tk.Button(
            form_frame,
            text="浏览",
            command=lambda: self.browse_file(program_entry),
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9),
            relief='flat',
            padx=15
        )
        browse_btn.grid(row=row, column=2, sticky=tk.W, pady=8)
        row += 1
        
        # 参数
        tk.Label(
            form_frame,
            text="参数:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        args_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        args_entry.insert(0, config.get('args', ''))
        args_entry.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E, pady=8, padx=(10, 0))
        row += 1
        
        # 工作目录
        tk.Label(
            form_frame,
            text="工作目录:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=8)
        workdir_entry = tk.Entry(
            form_frame,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        workdir_entry.insert(0, config.get('work_dir', '.'))
        workdir_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=8, padx=(10, 5))
        
        browse_dir_btn = tk.Button(
            form_frame,
            text="浏览",
            command=lambda: self.browse_directory(workdir_entry),
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 9),
            relief='flat',
            padx=15
        )
        browse_dir_btn.grid(row=row, column=2, sticky=tk.W, pady=8)
        row += 1
        
        # 自动启动
        auto_start_var = tk.BooleanVar(value=config.get('auto_start', False))
        auto_start_check = tk.Checkbutton(
            form_frame,
            text="自动启动",
            variable=auto_start_var,
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            selectcolor=FLAT_THEME['bg_darker'],
            activebackground=FLAT_THEME['bg_dark'],
            activeforeground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        )
        auto_start_check.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=8, padx=(10, 0))
        row += 1
        
        # 描述
        tk.Label(
            form_frame,
            text="描述:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.NW, pady=8)
        desc_text = scrolledtext.ScrolledText(
            form_frame,
            height=6,
            width=40,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            relief='flat'
        )
        desc_text.insert(1.0, config.get('description', ''))
        desc_text.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=8, padx=(10, 0))
        row += 1
        
        # 按钮框架
        button_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        button_frame.pack(pady=20)
        
        def update_and_close():
            new_name = name_entry.get().strip()
            program = program_entry.get().strip()
            work_dir = workdir_entry.get().strip()
            args = args_entry.get().strip()
            description = desc_text.get(1.0, tk.END).strip()
            
            if not new_name or not program:
                messagebox.showwarning("警告", "名称和程序路径是必填项")
                return
            
            # 如果名称改变，删除旧的并创建新的
            if new_name != original_name:
                del self.consoles[original_name]
                if original_name in self.current_tabs:
                    # 关闭标签页
                    tab_index = self.get_tab_id(original_name)
                    if tab_index is not None:
                        self.notebook.forget(tab_index)
                        if self.current_tabs[original_name].process:
                            self.current_tabs[original_name].process.terminate()
                        del self.current_tabs[original_name]
            
            # 更新配置
            self.consoles[new_name] = {
                'program': program,
                'args': args,
                'work_dir': work_dir or '.',
                'description': description,
                'auto_start': auto_start_var.get()
            }
            
            # 如果名称改变，需要创建新的标签页
            if new_name != original_name or new_name not in self.current_tabs:
                self.add_console_tab(new_name, self.consoles[new_name])
            
            self.save_config()
            dialog.destroy()
            self.status_var.set(f"已更新控制台: {new_name}")
            
            # 刷新系统托盘
            if hasattr(self, 'tray_manager') and self.tray_manager:
                self.tray_manager.update_menu()
        
        def delete_and_close():
            if messagebox.askyesno("确认", f"确定要删除控制台 '{original_name}' 吗？"):
                if original_name in self.consoles:
                    del self.consoles[original_name]
                
                if original_name in self.current_tabs:
                    # 关闭标签页
                    tab_index = self.get_tab_id(original_name)
                    if tab_index is not None:
                        self.notebook.forget(tab_index)
                        if self.current_tabs[original_name].process:
                            self.current_tabs[original_name].process.terminate()
                        del self.current_tabs[original_name]
                
                self.save_config()
                dialog.destroy()
                self.status_var.set(f"已删除控制台: {original_name}")
                self.update_status()
                
                # 刷新系统托盘
                if hasattr(self, 'tray_manager') and self.tray_manager:
                    self.tray_manager.update_menu()
        
        # 更新按钮
        update_btn = tk.Button(
            button_frame,
            text="更新",
            command=update_and_close,
            bg=FLAT_THEME['success'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=32,
            pady=9,
            cursor='hand2',
            activebackground=self.adjust_color(FLAT_THEME['success'], -20),
            borderwidth=0
        )
        update_btn.pack(side=tk.LEFT, padx=12)
        
        # 删除按钮
        delete_btn = tk.Button(
            button_frame,
            text="删除",
            command=delete_and_close,
            bg=FLAT_THEME['error'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=32,
            pady=9,
            cursor='hand2',
            activebackground=self.adjust_color(FLAT_THEME['error'], -20),
            borderwidth=0
        )
        delete_btn.pack(side=tk.LEFT, padx=12)
        
        # 取消按钮
        cancel_btn = tk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy,
            bg=FLAT_THEME['disabled'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=32,
            pady=9,
            cursor='hand2',
            activebackground=self.adjust_color(FLAT_THEME['disabled'], -20),
            borderwidth=0
        )
        cancel_btn.pack(side=tk.LEFT, padx=12)
        
        name_entry.focus_set()
    
    def delete_console(self):
        """删除当前控制台"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("提示", "请先选择一个控制台")
            return
        
        tab_index = self.notebook.index(current_tab)
        tab_text = self.notebook.tab(tab_index, 'text')
        
        # 从标签文本中提取名称
        for name in self.consoles:
            if tab_text.startswith(name):
                original_name = name
                break
        else:
            return
        
        if messagebox.askyesno("确认", f"确定要删除控制台 '{original_name}' 吗？"):
            if original_name in self.consoles:
                del self.consoles[original_name]
            
            if original_name in self.current_tabs:
                # 关闭标签页
                tab_index = self.get_tab_id(original_name)
                if tab_index is not None:
                    self.notebook.forget(tab_index)
                    if self.current_tabs[original_name].process:
                        self.current_tabs[original_name].process.terminate()
                    del self.current_tabs[original_name]
            
            # 刷新系统托盘
            if hasattr(self, 'tray_manager') and self.tray_manager:
                self.tray_manager.update_menu()
            
            self.save_config()
            self.update_status()
            self.update_tab_buttons_state()
            self.status_var.set(f"已删除控制台: {original_name}")
    
    def run_console(self):
        """运行当前控制台"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("提示", "请先选择一个控制台")
            return
        
        tab_index = self.notebook.index(current_tab)
        tab_text = self.notebook.tab(tab_index, 'text')
        
        # 从标签文本中提取名称
        for name in self.current_tabs:
            if tab_text.startswith(name):
                tab = self.current_tabs[name]
                if not tab.is_running:
                    # 在新线程中运行
                    threading.Thread(target=tab.run, daemon=True).start()
                    self.status_var.set(f"正在启动: {name}")
                else:
                    self.status_var.set(f"{name} 已在运行中")
                break
    
    def stop_console(self):
        """停止当前控制台"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("提示", "请先选择一个控制台")
            return
        
        tab_index = self.notebook.index(current_tab)
        tab_text = self.notebook.tab(tab_index, 'text')
        
        # 从标签文本中提取名称
        for name in self.current_tabs:
            if tab_text.startswith(name):
                tab = self.current_tabs[name]
                if tab.is_running:
                    tab.stop()
                    self.status_var.set(f"正在停止: {name}")
                else:
                    self.status_var.set(f"{name} 未在运行")
                break
    
    def restart_current_console(self):
        """重启当前控制台"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("提示", "请先选择一个控制台")
            return
        
        tab_index = self.notebook.index(current_tab)
        tab_text = self.notebook.tab(tab_index, 'text')
        
        # 从标签文本中提取名称
        for name in self.current_tabs:
            if tab_text.startswith(name):
                tab = self.current_tabs[name]
                if tab.is_running:
                    tab.stop()
                    self.root.after(500, tab.run)  # 0.5秒后重启
                    self.status_var.set(f"正在重启: {name}")
                else:
                    tab.run()
                    self.status_var.set(f"正在启动: {name}")
                break
    
    def run_all_consoles(self):
        """运行所有控制台"""
        for name, tab in self.current_tabs.items():
            if not tab.is_running:
                threading.Thread(target=tab.run, daemon=True).start()
        
        self.status_var.set("正在启动所有控制台...")
    
    def stop_all_consoles(self):
        """停止所有控制台"""
        for name, tab in self.current_tabs.items():
            if tab.is_running:
                tab.stop()
        
        self.status_var.set("正在停止所有控制台...")
    
    def refresh_consoles(self):
        """刷新所有控制台"""
        # 保存自动启动状态
        auto_start_consoles = []
        for name, tab in self.current_tabs.items():
            if tab.auto_start:
                auto_start_consoles.append(name)
            if tab.process:
                tab.process.terminate()
        
        self.current_tabs.clear()
        
        # 重新添加所有控制台
        for name, config in self.consoles.items():
            self.add_console_tab(name, config)
        
        self.status_var.set("已刷新所有控制台")
        self.update_status()
    
    def filter_consoles(self, event=None):
        """过滤控制台"""
        search_text = self.search_var.get().lower()
        for name in self.consoles.keys():
            tab_id = self.get_tab_id(name)
            if tab_id is not None:
                if search_text and search_text != "搜索控制台...":
                    if search_text in name.lower():
                        self.notebook.notebook.tab(tab_id, state='normal')
                    else:
                        self.notebook.notebook.tab(tab_id, state='hidden')
                else:
                    self.notebook.notebook.tab(tab_id, state='normal')
    
    def clear_search(self):
        """清除搜索"""
        self.search_var.set("")
        self.filter_consoles()
    
    def start_saved_consoles(self):
        """启动保存的控制台"""
        for name, config in self.consoles.items():
            self.add_console_tab(name, config)
        
        self.update_status()
        self.status_var.set("就绪")
        
        # 默认切换到服务管理标签页
        self.notebook.notebook.select(0)
    
    def on_tab_changed(self, event):
        """标签页切换事件"""
        self.update_tab_buttons_state()
        current_tab = self.notebook.select()
        if current_tab:
            tab_index = self.notebook.index(current_tab)
            tab_text = self.notebook.tab(tab_index, 'text')
            
            # 从标签文本中提取名称
            for name in self.current_tabs:
                if tab_text.startswith(name):
                    tab = self.current_tabs[name]
                    status = "运行中" if tab.is_running else "已停止"
                    if tab.exit_code is not None and tab.exit_code != 0:
                        status = "异常退出"
                    self.status_var.set(f"{name} - {status}")
                    break
    
    def update_status(self):
        """更新状态栏"""
        count = len(self.current_tabs)
        self.console_count_var.set(f"控制台: {count}")
        
        # 更新运行状态计数
        running_count = sum(1 for tab in self.current_tabs.values() if tab.is_running)
        self.running_count_var.set(f"运行: {running_count}")
    
    def clear_all_outputs(self):
        """清除所有输出"""
        for tab in self.current_tabs.values():
            tab.clear_output()
        self.status_var.set("已清除所有输出")
    
    def show_all_outputs(self):
        """显示所有输出"""
        for name in self.consoles.keys():
            tab_id = self.get_tab_id(name)
            if tab_id is not None:
                self.notebook.notebook.tab(tab_id, state='normal')
        self.clear_search()
    
    def toggle_always_on_top(self):
        """切换总是置顶"""
        current_state = self.root.attributes('-topmost')
        self.root.attributes('-topmost', not current_state)
        
        # 保存设置
        self.settings['always_on_top'] = not current_state
        self.save_settings()
        
        status = "开启" if not current_state else "关闭"
        self.status_var.set(f"窗口置顶已{status}")
    
    def set_always_on_top(self, state):
        """设置总是置顶"""
        self.root.attributes('-topmost', state)
        self.settings['always_on_top'] = state
        self.save_settings()
    
    def global_settings_dialog(self):
        """全局设置对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("全局设置")
        dialog.geometry("500x400")
        dialog.configure(bg=FLAT_THEME['bg_dark'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        self.center_window(dialog)
        
        # 标题
        title_label = tk.Label(
            dialog,
            text="全局设置",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['primary_light'],
            font=('微软雅黑', 14, 'bold')
        )
        title_label.pack(pady=(20, 10))
        
        # 设置框架
        settings_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        row = 0
        
        # 开机启动
        auto_start_var = tk.BooleanVar(value=self.settings.get('auto_start_app', False))
        
        auto_start_check = tk.Checkbutton(
            settings_frame,
            text="开机自动启动程序",
            variable=auto_start_var,
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            selectcolor=FLAT_THEME['bg_darker'],
            activebackground=FLAT_THEME['bg_dark'],
            activeforeground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        )
        auto_start_check.grid(row=row, column=0, sticky=tk.W, pady=10)
        row += 1
        
        # 启动时隐藏主窗口
        start_hidden_var = tk.BooleanVar(value=self.settings.get('start_hidden', False))
        
        start_hidden_check = tk.Checkbutton(
            settings_frame,
            text="启动时隐藏主窗口",
            variable=start_hidden_var,
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            selectcolor=FLAT_THEME['bg_darker'],
            activebackground=FLAT_THEME['bg_dark'],
            activeforeground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        )
        start_hidden_check.grid(row=row, column=0, sticky=tk.W, pady=10)
        row += 1
        
        # 窗口置顶
        always_on_top_var = tk.BooleanVar(value=self.settings.get('always_on_top', False))
        
        always_on_top_check = tk.Checkbutton(
            settings_frame,
            text="窗口总是置顶",
            variable=always_on_top_var,
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            selectcolor=FLAT_THEME['bg_darker'],
            activebackground=FLAT_THEME['bg_dark'],
            activeforeground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        )
        always_on_top_check.grid(row=row, column=0, sticky=tk.W, pady=10)
        row += 1
        
        # 自动保存间隔
        tk.Label(
            settings_frame,
            text="自动保存间隔(秒):",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=10)
        
        auto_save_var = tk.StringVar(value=str(self.settings.get('auto_save_interval', 60)))
        auto_save_spinbox = tk.Spinbox(
            settings_frame,
            from_=10,
            to=3600,
            textvariable=auto_save_var,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=10,
            relief='flat'
        )
        auto_save_spinbox.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        row += 1
        
        # 日志级别
        tk.Label(
            settings_frame,
            text="日志级别:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=row, column=0, sticky=tk.W, pady=10)
        
        log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        log_level_var = tk.StringVar(value=self.settings.get('log_level', 'INFO'))
        log_level_combo = ttk.Combobox(
            settings_frame,
            textvariable=log_level_var,
            values=log_levels,
            state='readonly',
            width=10
        )
        log_level_combo.grid(row=row, column=1, sticky=tk.W, pady=10, padx=(10, 0))
        row += 1
        
        # 按钮框架
        button_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        button_frame.pack(pady=20)
        
        def save_settings():
            self.settings['auto_start_app'] = auto_start_var.get()
            self.settings['start_hidden'] = start_hidden_var.get()
            self.settings['always_on_top'] = always_on_top_var.get()
            self.settings['auto_save_interval'] = int(auto_save_var.get())
            self.settings['log_level'] = log_level_var.get()
            
            # 应用设置
            self.set_auto_start(auto_start_var.get())
            self.set_always_on_top(always_on_top_var.get())
            
            # 设置日志级别
            log_level = getattr(logging, log_level_var.get())
            logger.setLevel(log_level)
            for handler in logging.getLogger().handlers:
                handler.setLevel(log_level)
            
            self.save_settings()
            dialog.destroy()
            self.status_var.set("全局设置已保存")
        
        def reset_settings():
            if messagebox.askyesno("确认", "确定要重置所有设置吗？"):
                self.settings = {}
                self.save_settings()
                dialog.destroy()
                self.status_var.set("设置已重置，请重启程序")
        
        # 保存按钮
        save_btn = tk.Button(
            button_frame,
            text="保存",
            command=save_settings,
            bg=FLAT_THEME['success'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=30,
            pady=8
        )
        save_btn.pack(side=tk.LEFT, padx=10)
        
        # 重置按钮
        reset_btn = tk.Button(
            button_frame,
            text="重置",
            command=reset_settings,
            bg=FLAT_THEME['warning'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            relief='flat',
            padx=30,
            pady=8
        )
        reset_btn.pack(side=tk.LEFT, padx=10)
        
        # 取消按钮
        cancel_btn = tk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy,
            bg=FLAT_THEME['disabled'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            relief='flat',
            padx=30,
            pady=8
        )
        cancel_btn.pack(side=tk.LEFT, padx=10)
    
    def set_auto_start(self, enable):
        """设置开机启动"""
        if sys.platform == 'win32':
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_SET_VALUE
                )
                
                app_name = "ConsoleManager"
                app_path = sys.executable
                
                if enable:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
                    logger.info(f"已设置开机启动: {app_path}")
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                        logger.info("已取消开机启动")
                    except FileNotFoundError:
                        pass
                
                winreg.CloseKey(key)
                
            except Exception as e:
                logger.error(f"设置开机启动失败: {e}")
                messagebox.showerror("错误", f"设置开机启动失败: {e}")
        else:
            logger.warning("开机启动功能仅支持Windows系统")
            if enable:
                messagebox.showinfo("提示", "开机启动功能仅支持Windows系统")
    
    def show_help(self):
        """显示帮助"""
        help_text = """控制台管理器 v2.0 使用说明

主要功能：
1. 新建控制台：
   - 点击工具栏的"新建"按钮
   - 填写控制台配置信息
   - 可选择"自动启动"选项

2. 控制台操作：
   - 运行：点击"运行"按钮或双击控制台
   - 停止：点击"停止"按钮
   - 重启：点击"重启"按钮
   - 编辑：点击"编辑"按钮修改配置
   - 删除：点击"删除"按钮或按Delete键

3. 系统托盘：
   - 点击关闭按钮会最小化到托盘
   - 托盘图标右键菜单可控制所有控制台

4. 全局设置：
   - 开机启动：程序随系统启动
   - 窗口置顶：窗口始终在最前面
   - 自动保存：定期自动保存配置

5. 标签页管理：
   - 支持横向滚动，标签页过多时可滚动查看
   - 标签页显示运行状态：[运行中]、[停止]、[异常退出]
   - 异常退出时标签页标题显示为红色

6. 搜索功能：
   - 在工具栏搜索框中输入关键词
   - 实时过滤显示相关控制台

快捷键：
   Ctrl+N: 新建控制台
   Ctrl+S: 保存配置
   Ctrl+E: 编辑控制台
   Delete: 删除控制台
   F5: 刷新
   Alt+F4: 退出程序

注意事项：
   - 配置自动保存到应用程序运行目录中的 config.yaml
   - 日志文件保存在应用程序运行目录中的 app.log

关于项目：
   - 项目使用 MIT 许可证
   - 更多信息请查看 README.md 文件"""

        dialog = tk.Toplevel(self.root)
        dialog.title("使用说明")
        dialog.geometry("600x500")
        dialog.configure(bg=FLAT_THEME['bg_dark'])
        
        text_widget = scrolledtext.ScrolledText(
            dialog,
            wrap=tk.WORD,
            width=70,
            height=25,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            font=('Segoe UI', 10),
            relief='flat'
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget.insert(1.0, help_text)
        text_widget.configure(state='disabled')
        
        close_btn = tk.Button(
            dialog,
            text="关闭",
            command=dialog.destroy,
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('Segoe UI', 10),
            relief='flat',
            padx=30,
            pady=8
        )
        close_btn.pack(pady=10)
    
    def check_for_updates(self):
        """检查更新"""
        messagebox.showinfo("检查更新", "当前已是最新版本 v2.0")
    
    def add_service_dialog(self):
        """添加服务对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加服务")
        dialog.geometry("500x300")
        dialog.configure(bg=FLAT_THEME['bg_dark'])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # 居中显示
        self.center_window(dialog)
        
        # 标题
        title_label = tk.Label(
            dialog,
            text="添加服务",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['primary_light'],
            font=('微软雅黑', 14, 'bold')
        )
        title_label.pack(pady=(20, 15))
        
        # 表单框架
        form_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # 服务名称
        tk.Label(
            form_frame,
            text="服务名称:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=0, column=0, sticky=tk.W, pady=10)
        
        service_name_var = tk.StringVar()
        service_name_entry = tk.Entry(
            form_frame,
            textvariable=service_name_var,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        service_name_entry.grid(row=0, column=1, sticky=tk.W, pady=10)
        
        # 显示名称
        tk.Label(
            form_frame,
            text="显示名称:",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10)
        ).grid(row=1, column=0, sticky=tk.W, pady=10)
        
        display_name_var = tk.StringVar()
        display_name_entry = tk.Entry(
            form_frame,
            textvariable=display_name_var,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            width=40
        )
        display_name_entry.grid(row=1, column=1, sticky=tk.W, pady=10)
        
        # 按钮框架
        button_frame = tk.Frame(dialog, bg=FLAT_THEME['bg_dark'])
        button_frame.pack(pady=20)
        
        def save_service():
            service_name = service_name_var.get().strip()
            display_name = display_name_var.get().strip()
            
            if not service_name:
                messagebox.showwarning("警告", "服务名称不能为空")
                return
            
            # 检查服务是否存在
            if self.get_service_status(service_name) is None:
                messagebox.showerror("错误", f"服务 '{service_name}' 不存在")
                return
            
            # 添加到服务列表
            if service_name not in [s['name'] for s in self.services]:
                self.services.append({
                    'name': service_name,
                    'display_name': display_name or service_name
                })
                self.refresh_services()
                self.save_config()  # 保存配置到文件
                dialog.destroy()
                self.status_var.set(f"已添加服务: {service_name}")
                
                # 刷新系统托盘
                if hasattr(self, 'tray_manager') and self.tray_manager:
                    self.tray_manager.update_menu()
            else:
                messagebox.showinfo("提示", "服务已存在")
        
        # 保存按钮
        save_btn = tk.Button(
            button_frame,
            text="保存",
            command=save_service,
            bg=FLAT_THEME['success'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10, 'bold'),
            relief='flat',
            padx=30,
            pady=8
        )
        save_btn.pack(side=tk.LEFT, padx=10)
        
        # 取消按钮
        cancel_btn = tk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy,
            bg=FLAT_THEME['disabled'],
            fg=FLAT_THEME['text_light'],
            font=('微软雅黑', 10),
            relief='flat',
            padx=30,
            pady=8
        )
        cancel_btn.pack(side=tk.LEFT, padx=10)
        
        service_name_entry.focus_set()
    
    def refresh_services(self):
        """刷新服务列表"""
        # 清空树状视图
        for item in self.service_tree.get_children():
            self.service_tree.delete(item)
        
        # 更新服务状态
        for index, service in enumerate(self.services):
            status = self.get_service_status(service['name'])
            # 更新服务字典中的状态，确保托盘管理器能获取到正确状态
            if status == '运行中':
                service['status'] = 'running'
            elif status == '已停止':
                service['status'] = 'stopped'
            else:
                service['status'] = 'unknown'
            
            # 根据状态选择图标
            if status == '运行中':
                icon = '▶'
            elif status == '已停止':
                icon = '■'
            else:
                icon = '⏸'
            
            # 合并图标和状态文本
            status_with_icon = f'  {icon} {status}'
            
            # 应用奇偶行样式和状态颜色标签
            row_tag = 'even' if index % 2 == 0 else 'odd'
            
            # 根据状态选择颜色标签
            if status == '运行中':
                status_tag = 'running'
            elif status == '已停止':
                status_tag = 'stopped'
            else:
                status_tag = 'other'
            
            self.service_tree.insert('', tk.END, values=(
                f'  {service["name"]}',
                status_with_icon,
                f'  {service["display_name"]}'
            ), tags=(row_tag, status_tag))
    
    def get_service_status(self, service_name):
        """获取服务状态"""
        try:
            result = subprocess.run(
                ['sc', 'query', service_name],
                capture_output=True,
                text=True,
                check=True,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            for line in result.stdout.split('\n'):
                if 'STATE' in line:
                    state_part = line.split(':')[1].strip()
                    if 'RUNNING' in state_part:
                        return '运行中'
                    elif 'STOPPED' in state_part:
                        return '已停止'
                    else:
                        return state_part
            return '未知'
        except subprocess.CalledProcessError:
            return None
        except Exception as e:
            logger.error(f"获取服务状态失败: {e}")
            return '错误'
    
    def start_service(self):
        """启动服务"""
        selected_item = self.service_tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "请选择一个服务")
            return
        
        item = selected_item[0]
        service_name_with_spaces = self.service_tree.item(item, 'values')[0]
        service_name = service_name_with_spaces.strip()
        # 移除固定的成功提示，因为 start_service_by_name 已经会根据执行结果显示相应的提示
        self.start_service_by_name(service_name)

    def stop_service(self):
        """停止服务"""
        selected_item = self.service_tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "请选择一个服务")
            return
        
        item = selected_item[0]
        service_name_with_spaces = self.service_tree.item(item, 'values')[0]
        service_name = service_name_with_spaces.strip()
        # 移除固定的成功提示，因为 stop_service_by_name 已经会根据执行结果显示相应的提示
        self.stop_service_by_name(service_name)
    
    def start_service_by_name(self, service_name):
        """通过服务名启动服务"""
        try:
            result = subprocess.run(
                ['net', 'start', service_name],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                self.refresh_services()
                self.status_var.set(f"服务启动成功: {service_name}")
            else:
                error_msg = f"服务启动失败: {result.stderr}"
                logger.error(error_msg)
                messagebox.showerror("错误", error_msg)
                self.status_var.set(f"服务启动失败: {service_name}")
        except Exception as e:
            error_msg = f"启动服务失败: {str(e)}"
            logger.error(error_msg)
            messagebox.showerror("错误", error_msg)
            self.status_var.set(f"服务启动失败: {service_name}")

    def stop_service_by_name(self, service_name):
        """通过服务名停止服务"""
        try:
            result = subprocess.run(
                ['net', 'stop', service_name],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                self.refresh_services()
                self.status_var.set(f"服务停止成功: {service_name}")
            else:
                error_msg = f"服务停止失败: {result.stderr}"
                logger.error(error_msg)
                messagebox.showerror("错误", error_msg)
                self.status_var.set(f"服务停止失败: {service_name}")
        except Exception as e:
            error_msg = f"停止服务失败: {str(e)}"
            logger.error(error_msg)
            messagebox.showerror("错误", error_msg)
            self.status_var.set(f"服务停止失败: {service_name}")

    def restart_service_by_name(self, service_name):
        """通过服务名重启服务"""
        try:
            # 先停止服务
            stop_result = subprocess.run(
                ['net', 'stop', service_name],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 等待服务停止
            import time
            time.sleep(2)
            
            # 再启动服务
            start_result = subprocess.run(
                ['net', 'start', service_name],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if start_result.returncode == 0:
                # 等待服务完全启动
                time.sleep(1)
                self.refresh_services()
                self.status_var.set(f"服务重启成功: {service_name}")
            else:
                error_msg = f"服务重启失败: {start_result.stderr}"
                logger.error(error_msg)
                messagebox.showerror("错误", error_msg)
                self.status_var.set(f"服务重启失败: {service_name}")
        except Exception as e:
            error_msg = f"重启服务失败: {str(e)}"
            logger.error(error_msg)
            messagebox.showerror("错误", error_msg)
            self.status_var.set(f"服务重启失败: {service_name}")
    
    def remove_service(self):
        """删除服务"""
        selected_item = self.service_tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "请选择一个服务")
            return
        
        item = selected_item[0]
        service_name_with_spaces = self.service_tree.item(item, 'values')[0]
        service_name = service_name_with_spaces.strip()
        
        if messagebox.askyesno("确认", f"确定要删除服务 '{service_name}' 吗？"):
            # 从服务列表中删除
            self.services = [s for s in self.services if s['name'] != service_name]
            self.refresh_services()
            self.status_var.set(f"已删除服务: {service_name}")
            
            # 刷新系统托盘
            if hasattr(self, 'tray_manager') and self.tray_manager:
                self.tray_manager.update_menu()
    
    def show_about(self):
        """显示关于信息"""
        about_text = f"""控制台管理器 v2.0

一个功能强大的控制台程序集中管理工具
开发者：萌艺科技（原萌绘开发组）

主要特性：
- 扁平化现代UI设计
- 系统托盘支持
- 开机启动功能
- 标签页状态显示
- 横向滚动支持
- 自动启动控制台
- 实时日志输出
- Windows服务管理

萌艺科技 MoeArt Inc.
- www.acgdraw.com -
版权所有 © 2026

使用技术：
- Python tkinter GUI
- subprocess.Popen 进程管理
- YAML 配置文件
- 系统托盘集成

系统要求：
- Windows 7 或更高版本"""
        
        dialog = tk.Toplevel(self.root)
        dialog.title("关于")
        dialog.geometry("520x450")
        dialog.configure(bg=FLAT_THEME['bg_dark'])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # 居中显示
        self.center_window(dialog)
        
        # 标题
        title_label = tk.Label(
            dialog,
            text="控制台管理器 v2.0",
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['primary_light'],
            font=('Segoe UI', 17, 'bold')
        )
        title_label.pack(pady=(25, 20))
        
        # 图标（如果存在）
        try:
            icon_img = tk.PhotoImage(file='icon.png')
            icon_label = tk.Label(dialog, image=icon_img, bg=FLAT_THEME['bg_dark'])
            icon_label.image = icon_img
            icon_label.pack(pady=15)
        except:
            pass
        
        # 文本内容
        text_widget = scrolledtext.ScrolledText(
            dialog,
            wrap=tk.WORD,
            width=55,
            height=15,
            bg=FLAT_THEME['bg_darker'],
            fg=FLAT_THEME['text_light'],
            font=('Segoe UI', 10),
            relief='flat',
            borderwidth=0
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=25, pady=15)
        
        text_widget.insert(1.0, about_text)
        text_widget.configure(state='disabled')
        
        close_btn = tk.Button(
            dialog,
            text="关闭",
            command=dialog.destroy,
            bg=FLAT_THEME['primary'],
            fg=FLAT_THEME['text_light'],
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=32,
            pady=9,
            cursor='hand2',
            activebackground=self.adjust_color(FLAT_THEME['primary'], -20),
            borderwidth=0
        )
        close_btn.pack(pady=15)
    
    def import_config(self):
        """导入配置"""
        filename = filedialog.askopenfilename(
            title="选择配置文件",
            filetypes=[("YAML文件", "*.yaml;*.yml"), ("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    if filename.endswith('.json'):
                        imported_consoles = json.load(f)
                    else:
                        imported_consoles = yaml.safe_load(f) or {}
                
                # 合并配置
                for name, config in imported_consoles.items():
                    if name not in self.consoles:
                        self.consoles[name] = config
                
                self.refresh_consoles()
                self.save_config()
                self.status_var.set(f"已导入配置: {filename}")
                
            except Exception as e:
                messagebox.showerror("错误", f"导入配置失败: {str(e)}")
    
    def export_config(self):
        """导出配置"""
        filename = filedialog.asksaveasfilename(
            title="保存配置文件",
            defaultextension=".yaml",
            filetypes=[("YAML文件", "*.yaml"), ("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(self.consoles, f, indent=2, ensure_ascii=False)
                else:
                    with open(filename, 'w', encoding='utf-8') as f:
                        yaml.dump(self.consoles, f, default_flow_style=False, allow_unicode=True)
                
                self.status_var.set(f"已导出配置: {filename}")
                
            except Exception as e:
                messagebox.showerror("错误", f"导出配置失败: {str(e)}")
    
    def copy_console_config(self):
        """复制控制台配置"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("提示", "请先选择一个控制台")
            return
        
        tab_index = self.notebook.index(current_tab)
        tab_text = self.notebook.tab(tab_index, 'text')
        
        # 从标签文本中提取名称
        for name in self.consoles:
            if tab_text.startswith(name):
                # 复制配置到剪贴板
                import json
                config_json = json.dumps(self.consoles[name], indent=2)
                self.root.clipboard_clear()
                self.root.clipboard_append(config_json)
                self.status_var.set(f"已复制配置: {name}")
                break
    
    def exit_app(self):
        """退出应用程序"""
        # 停止所有控制台
        for name, tab in self.current_tabs.items():
            if tab.process and tab.is_running:
                try:
                    tab.process.terminate()
                    # 等待进程退出
                    tab.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # 强制终止
                    tab.process.kill()
                except Exception as e:
                    logger.error(f"终止进程 {name} 失败: {e}")
        
        # 保存配置
        self.save_config()
        self.save_settings()
        
        # 停止托盘图标
        if self.tray_manager:
            self.tray_manager.exit_app()
        else:
            self.root.quit()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            # 保存控制台和服务配置
            config_data = {
                'consoles': self.consoles,
                'services': self.services
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            logger.info("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
    
    def load_config(self):
        """从文件加载配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
                self.consoles = config_data.get('consoles', {})
                self.services = config_data.get('services', [])
                logger.info(f"已加载配置: {CONFIG_FILE}")
                logger.info(f"已加载 {len(self.services)} 个服务")
            else:
                self.consoles = {}
                self.services = []
                logger.info("未找到配置文件，使用默认配置")
        except Exception as e:
            # 加载失败时，使用默认配置但不保存，避免清空现有配置
            self.consoles = {}
            self.services = []
            logger.error(f"加载配置失败: {e}")
            logger.warning("使用默认配置，但不会覆盖现有配置文件")
    
    def on_window_configure(self, event):
        """窗口大小改变事件处理"""
        # 只在窗口实际存在时保存大小
        if event.widget == self.root and self.root.state() == 'normal':
            # 保存窗口大小
            self.settings['window_size'] = [event.width, event.height]
            # 保存设置
            self.save_settings()
    
    def save_settings(self):
        """保存设置到文件"""
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            logger.info("设置已保存")
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
    
    def load_settings(self):
        """从文件加载设置"""
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                logger.info(f"已加载设置: {SETTINGS_FILE}")
            else:
                self.settings = {}
                logger.info("未找到设置文件，使用默认设置")
        except Exception as e:
            self.settings = {}
            logger.error(f"加载设置失败: {e}")
