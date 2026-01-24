import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import os
from datetime import datetime
from .constants import FLAT_THEME

class ConsoleTab:
    def __init__(self, parent, name, config, app):
        self.name = name
        self.config = config
        self.app = app
        self.process = None
        self.is_running = False
        self.auto_start = config.get('auto_start', False)
        self.exit_code = None
        
        # 创建标签页框架
        self.tab_frame = ttk.Frame(parent)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建文本显示区域
        self.text_widget = scrolledtext.ScrolledText(
            self.tab_frame,
            wrap=tk.WORD,
            bg=FLAT_THEME['bg_dark'],
            fg=FLAT_THEME['text_light'],
            insertbackground=FLAT_THEME['text_light'],
            selectbackground=FLAT_THEME['primary'],
            selectforeground=FLAT_THEME['text_light'],
            font=('Consolas', 10),
            relief='flat',
            borderwidth=1
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # 创建输入框和按钮
        input_frame = ttk.Frame(self.tab_frame, style='Flat.TFrame')
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.cmd_entry = ttk.Entry(
            input_frame,
            style='Flat.TEntry',
            font=('Segoe UI', 10)
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.cmd_entry.bind('<Return>', self.send_command)
        
        # 创建按钮组
        btn_frame = ttk.Frame(input_frame, style='Flat.TFrame')
        btn_frame.pack(side=tk.RIGHT)
        
        self.create_button(btn_frame, "发送", self.send_command, FLAT_THEME['primary'])
        self.create_button(btn_frame, "停止", self.stop, FLAT_THEME['error'])
        self.create_button(btn_frame, "清除", self.clear_output, FLAT_THEME['warning'])
        
        # 应用文本标签样式
        self.setup_text_tags()
        

    
    def create_toolbar(self):
        """创建标签页工具栏"""
        toolbar = ttk.Frame(self.tab_frame, style='Flat.TFrame')
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # 状态指示灯
        self.status_indicator = tk.Canvas(
            toolbar,
            width=12,
            height=12,
            bg=FLAT_THEME['bg_dark'],
            highlightthickness=0
        )
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 10))
        self.update_status_indicator()
        
        # 标签页标题
        title_label = ttk.Label(
            toolbar,
            text=self.name,
            style='Title.TLabel',
            font=('Segoe UI', 11, 'bold')
        )
        title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 移除自动启动复选框
    
    def create_button(self, parent, text, command, color):
        """创建扁平化按钮"""
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg=FLAT_THEME['text_light'],
            font=('Segoe UI', 9),
            relief='flat',
            padx=12,
            pady=4,
            cursor='hand2',
            activebackground=self.adjust_color(color, -20),
            activeforeground=FLAT_THEME['text_light']
        )
        btn.pack(side=tk.LEFT, padx=2)
        return btn
    
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
    
    def setup_text_tags(self):
        """设置文本标签样式"""
        tags_config = {
            'error': {'foreground': FLAT_THEME['error']},
            'success': {'foreground': FLAT_THEME['success']},
            'warning': {'foreground': FLAT_THEME['warning']},
            'info': {'foreground': FLAT_THEME['info']},
            'command': {'foreground': FLAT_THEME['primary_light'], 'font': ('Consolas', 10, 'bold')},
            'output': {'foreground': FLAT_THEME['text_light']},
            'timestamp': {'foreground': FLAT_THEME['disabled'], 'font': ('Consolas', 9)}
        }
        
        for tag_name, tag_config in tags_config.items():
            self.text_widget.tag_configure(tag_name, **tag_config)
    
    def update_status_indicator(self):
        """更新状态指示灯"""
        self.status_indicator.delete("all")
        
        if self.is_running:
            color = FLAT_THEME['running']
        elif self.exit_code is not None and self.exit_code != 0:
            color = FLAT_THEME['error_tab']
        else:
            color = FLAT_THEME['stopped']
        
        # 绘制圆形指示灯
        self.status_indicator.create_oval(
            2, 2, 10, 10,
            fill=color,
            outline=color,
            width=2
        )
    
    def update_tab_title(self):
        """更新标签页标题"""
        if self.is_running:
            status_text = "[运行中]"
        elif self.exit_code is not None and self.exit_code != 0:
            status_text = "[异常退出]"
        else:
            status_text = "[停止]"
        
        full_title = f"{self.name} {status_text}"
        
        # 更新标签页标题
        tab_id = self.app.get_tab_id(self.name)
        if tab_id is not None:
            self.app.notebook.notebook.tab(tab_id, text=full_title)
            
            # 如果异常退出，设置标签页颜色
            if self.exit_code is not None and self.exit_code != 0:
                # 尝试设置标签页颜色，但避免使用不支持的foreground选项
                try:
                    self.app.notebook.notebook.tab(tab_id, text=full_title)
                except:
                    pass
            else:
                # 正常状态，直接更新标签页标题
                self.app.notebook.notebook.tab(tab_id, text=full_title)
    
    # 移除 toggle_auto_start 方法，因为自动启动复选框已被移除
    
    def clear_output(self):
        """清除输出"""
        self.text_widget.delete(1.0, tk.END)
    
    def send_command(self, event=None):
        """发送命令"""
        if self.process and self.is_running:
            command = self.cmd_entry.get()
            if command:
                try:
                    # 添加时间戳
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    self.append_output(f"\n[{timestamp}] > {command}\n", 'timestamp')
                    
                    # 发送命令
                    self.process.stdin.write(command + '\n')
                    self.process.stdin.flush()
                    self.cmd_entry.delete(0, tk.END)
                except Exception as e:
                    self.append_output(f"无法发送命令: {str(e)}\n", 'error')
    
    def stop(self):
        """停止控制台"""
        if self.process and self.is_running:
            try:
                self.process.terminate()
                self.is_running = False
                self.exit_code = None
                self.update_status_indicator()
                self.update_tab_title()
                self.append_output("进程已停止\n", 'warning')
            except Exception as e:
                self.append_output(f"无法停止进程: {str(e)}\n", 'error')
    
    def append_output(self, text, tag=None):
        """添加输出到文本区域"""
        self.text_widget.insert(tk.END, text)
        if tag:
            start = self.text_widget.index(f"end-{len(text)}c")
            end = self.text_widget.index("end")
            self.text_widget.tag_add(tag, start, end)
        self.text_widget.see(tk.END)
    
    def run(self):
        """运行控制台"""
        try:
            # 创建工作目录
            work_dir = self.config.get('work_dir', '.')
            if not os.path.exists(work_dir):
                os.makedirs(work_dir, exist_ok=True)
            
            # 构建命令
            program = self.config['program']
            args = self.config.get('args', [])
            if isinstance(args, str):
                args = args.split()
            
            # 过滤掉无效的"-foreground"选项
            filtered_args = [arg for arg in args if arg != "-foreground"]
            
            cmd = [program] + filtered_args
            
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.is_running = True
            self.exit_code = None
            
            # 更新状态
            self.update_status_indicator()
            self.update_tab_title()
            
            # 启动输出读取线程
            threading.Thread(target=self.read_output, daemon=True).start()
            threading.Thread(target=self.read_error, daemon=True).start()
            
            # 启动进程监控线程
            threading.Thread(target=self.monitor_process, daemon=True).start()
            
            # 添加启动信息
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.append_output(f"[{timestamp}] 启动命令: {' '.join(cmd)}\n", 'timestamp')
            self.append_output(f"[{timestamp}] 工作目录: {work_dir}\n\n", 'timestamp')
            
        except Exception as e:
            self.append_output(f"[{datetime.now().strftime('%H:%M:%S')}] 启动失败: {str(e)}\n", 'error')
            self.is_running = False
            self.exit_code = -1
            self.update_status_indicator()
            self.update_tab_title()
    
    def read_output(self):
        """读取标准输出"""
        while self.process and self.is_running:
            try:
                line = self.process.stdout.readline()
                if line:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    formatted_line = f"[{timestamp}] {line}"
                    self.text_widget.after(0, self.append_output, formatted_line, 'output')
                elif self.process.poll() is not None:
                    break
            except:
                break
    
    def read_error(self):
        """读取错误输出"""
        while self.process and self.is_running:
            try:
                line = self.process.stderr.readline()
                if line:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    formatted_line = f"[{timestamp}] {line}"
                    self.text_widget.after(0, self.append_output, formatted_line, 'error')
                elif self.process.poll() is not None:
                    break
            except:
                break
    
    def monitor_process(self):
        """监控进程状态"""
        self.process.wait()
        self.exit_code = self.process.returncode
        self.is_running = False
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if self.process.returncode == 0:
            message = f"[{timestamp}] 进程正常退出，退出码: {self.process.returncode}\n"
            tag = 'success'
        else:
            message = f"[{timestamp}] 进程异常退出，退出码: {self.process.returncode}\n"
            tag = 'error'
        
        self.text_widget.after(0, self.append_output, message, tag)
        self.text_widget.after(0, self.update_status_indicator)
        self.text_widget.after(0, self.update_tab_title)
