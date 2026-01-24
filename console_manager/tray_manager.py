import os
import sys
from pathlib import Path
import pystray
from PIL import Image, ImageDraw
from .constants import FLAT_THEME

class TrayManager:
    """系统托盘管理器"""
    def __init__(self, app):
        self.app = app
        self.tray_icon = None
        
        # 创建托盘图标
        self.create_tray_icon()
    
    def create_tray_icon(self):
        """创建托盘图标"""
        # 尝试加载图标文件
        icon_paths = [
            'icon.png',
            'icon.ico',
            str(Path(sys.executable).parent / 'icon.png'),
            str(Path(sys.executable).parent / 'icon.ico'),
            'default_icon.png'
        ]
        
        icon_image = None
        
        for path in icon_paths:
            if os.path.exists(path):
                try:
                    icon_image = Image.open(path)
                    break
                except:
                    continue
        
        # 如果没有找到图标，创建一个默认图标
        if icon_image is None:
            icon_image = self.create_default_icon()
        
        # 创建托盘菜单
        menu_items = []
        
        # 添加显示/隐藏界面选项
        menu_items.append(pystray.MenuItem('显示/隐藏界面', self.toggle_window))
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # 添加服务管理选项（一级菜单）
        services = getattr(self.app, 'services', [])
        if services:
            for service in services:
                # 获取服务状态
                status = service.get('status', 'stopped')
                
                # 根据状态添加标志
                if status == 'running':
                    status_icon = '▶ '
                elif status == 'stopped':
                    status_icon = '◼ '
                else:
                    status_icon = '◾ '
                
                # 创建服务子菜单
                def create_service_start_callback(svc):
                    def callback(icon=None):
                        self.start_service(svc)
                    return callback
                
                def create_service_stop_callback(svc):
                    def callback(icon=None):
                        self.stop_service(svc)
                    return callback
                
                def create_service_restart_callback(svc):
                    def callback(icon=None):
                        self.restart_service(svc)
                    return callback
                
                service_submenu = pystray.Menu(
                    pystray.MenuItem('启动', create_service_start_callback(service), enabled=status != 'running'),
                    pystray.MenuItem('停止', create_service_stop_callback(service), enabled=status == 'running'),
                    pystray.MenuItem('重启', create_service_restart_callback(service), enabled=status == 'running')
                )
                
                menu_items.append(
                    pystray.MenuItem(f"{status_icon}{service.get('name', '未知服务')}", service_submenu)
                )
            menu_items.append(pystray.Menu.SEPARATOR)
        else:
            menu_items.append(pystray.MenuItem('无服务', None, enabled=False))
            menu_items.append(pystray.Menu.SEPARATOR)
        
        # 添加控制台管理选项（一级菜单）
        consoles = self.app.current_tabs
        if consoles:
            for name, tab in consoles.items():
                # 根据状态添加标志
                if tab.is_running:
                    status_icon = '▶ '
                else:
                    status_icon = '◼ '
                
                # 创建控制台子菜单
                def create_console_start_callback(t):
                    def callback(icon=None):
                        self.start_console(t)
                    return callback
                
                def create_console_stop_callback(t):
                    def callback(icon=None):
                        self.stop_console(t)
                    return callback
                
                def create_console_restart_callback(t):
                    def callback(icon=None):
                        self.restart_console(t)
                    return callback
                
                console_submenu = pystray.Menu(
                    pystray.MenuItem('启动', create_console_start_callback(tab), enabled=not tab.is_running),
                    pystray.MenuItem('停止', create_console_stop_callback(tab), enabled=tab.is_running),
                    pystray.MenuItem('重启', create_console_restart_callback(tab), enabled=tab.is_running)
                )
                
                menu_items.append(
                    pystray.MenuItem(f"{status_icon}{name}", console_submenu)
                )
            menu_items.append(pystray.Menu.SEPARATOR)
        else:
            menu_items.append(pystray.MenuItem('无控制台', None, enabled=False))
            menu_items.append(pystray.Menu.SEPARATOR)
        
        # 添加全局操作选项
        menu_items.append(pystray.MenuItem('运行所有控制台', self.run_all_consoles))
        menu_items.append(pystray.MenuItem('停止所有控制台', self.stop_all_consoles))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem('退出', self.exit_app))
        
        # 创建菜单
        menu = pystray.Menu(*menu_items)
        
        # 创建托盘图标
        self.tray_icon = pystray.Icon(
            "console_manager",
            icon_image,
            "控制台管理器",
            menu
        )
        
        # 绑定点击事件
        self.tray_icon.on_click = self.on_tray_click
    
    def create_default_icon(self):
        """创建默认托盘图标"""
        # 创建一个简单的蓝色图标
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        # 绘制控制台形状
        dc.rectangle([12, 12, 52, 52], fill=FLAT_THEME['primary'])
        dc.rectangle([16, 16, 48, 32], fill=FLAT_THEME['bg_light'])
        dc.rectangle([20, 36, 44, 44], fill=FLAT_THEME['success'])
        
        return image
    
    def on_tray_click(self, icon, item):
        """托盘图标点击事件"""
        # 点击托盘图标时显示/隐藏主窗口
        self.toggle_window()
    
    def toggle_window(self):
        """显示/隐藏主窗口"""
        if self.app.root.state() == 'withdrawn':
            # 显示窗口
            self.app.root.deiconify()
            self.app.root.state('normal')
            self.app.root.attributes('-topmost', 1)
            self.app.root.attributes('-topmost', 0)
        else:
            # 隐藏窗口
            self.app.root.withdraw()
    
    def create_service_submenu(self):
        """创建服务管理子菜单"""
        service_items = []
        
        # 获取服务列表
        services = getattr(self.app, 'services', [])
        
        if not services:
            return pystray.Menu(pystray.MenuItem('无服务', None, enabled=False))
        
        for service in services:
            # 获取服务状态
            status = service.get('status', 'stopped')
            
            # 根据状态添加标志
            if status == 'running':
                status_icon = '▶ '
            elif status == 'stopped':
                status_icon = '◼ '
            else:
                status_icon = '◾ '
            
            # 创建服务子菜单
            service_submenu = pystray.Menu(
                pystray.MenuItem('启动', lambda s=service: self.start_service(s), enabled=status != 'running'),
                pystray.MenuItem('停止', lambda s=service: self.stop_service(s), enabled=status == 'running'),
                pystray.MenuItem('重启', lambda s=service: self.restart_service(s), enabled=status == 'running')
            )
            
            service_items.append(
                pystray.MenuItem(f"{status_icon}{service.get('name', '未知服务')}", service_submenu)
            )
        
        return pystray.Menu(*service_items)
    
    def create_console_submenu(self):
        """创建控制台管理子菜单"""
        console_items = []
        
        # 获取控制台列表
        for name, tab in self.app.current_tabs.items():
            # 根据状态添加标志
            if tab.is_running:
                status_icon = '▶ '
            else:
                status_icon = '◼ '
            
            # 创建控制台子菜单
            console_submenu = pystray.Menu(
                pystray.MenuItem('启动', lambda t=tab: self.start_console(t), enabled=not tab.is_running),
                pystray.MenuItem('停止', lambda t=tab: self.stop_console(t), enabled=tab.is_running),
                pystray.MenuItem('重启', lambda t=tab: self.restart_console(t), enabled=tab.is_running)
            )
            
            console_items.append(
                pystray.MenuItem(f"{status_icon}{name}", console_submenu)
            )
        
        if not console_items:
            return pystray.Menu(pystray.MenuItem('无控制台', None, enabled=False))
        
        return pystray.Menu(*console_items)
    
    def start_service(self, service):
        """启动服务"""
        if hasattr(self.app, 'start_service_by_name'):
            service_name = service.get('name')
            if service_name:
                self.app.start_service_by_name(service_name)
                # 更新托盘菜单
                self.update_menu()

    def stop_service(self, service):
        """停止服务"""
        if hasattr(self.app, 'stop_service_by_name'):
            service_name = service.get('name')
            if service_name:
                self.app.stop_service_by_name(service_name)
                # 更新托盘菜单
                self.update_menu()

    def restart_service(self, service):
        """重启服务"""
        if hasattr(self.app, 'restart_service_by_name'):
            service_name = service.get('name')
            if service_name:
                self.app.restart_service_by_name(service_name)
                # 等待服务状态完全更新
                import time
                time.sleep(1)
                # 更新托盘菜单
                self.update_menu()
    
    def start_console(self, tab):
        """启动控制台"""
        if not tab.is_running:
            tab.run()
            # 更新托盘菜单
            self.update_menu()

    def stop_console(self, tab):
        """停止控制台"""
        if tab.is_running:
            tab.stop()
            # 更新托盘菜单
            self.update_menu()

    def restart_console(self, tab):
        """重启控制台"""
        tab.stop()
        import threading
        threading.Thread(target=tab.run, daemon=True).start()
        # 等待控制台状态完全更新
        import time
        time.sleep(0.5)
        # 更新托盘菜单
        self.update_menu()
    
    def update_menu(self):
        """更新托盘图标菜单"""
        if not self.tray_icon:
            return
        
        # 创建新的菜单
        menu_items = []
        
        # 添加显示/隐藏界面选项
        menu_items.append(pystray.MenuItem('显示/隐藏界面', self.toggle_window))
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # 添加服务管理选项（一级菜单）
        services = getattr(self.app, 'services', [])
        if services:
            for service in services:
                # 获取服务状态
                status = service.get('status', 'stopped')
                
                # 根据状态添加标志
                if status == 'running':
                    status_icon = '▶ '
                elif status == 'stopped':
                    status_icon = '◼ '
                else:
                    status_icon = '◾ '
                
                # 创建服务子菜单
                def create_service_start_callback(svc):
                    def callback(icon=None):
                        self.start_service(svc)
                        self.update_menu()
                    return callback
                
                def create_service_stop_callback(svc):
                    def callback(icon=None):
                        self.stop_service(svc)
                        self.update_menu()
                    return callback
                
                def create_service_restart_callback(svc):
                    def callback(icon=None):
                        self.restart_service(svc)
                        self.update_menu()
                    return callback
                
                service_submenu = pystray.Menu(
                    pystray.MenuItem('启动', create_service_start_callback(service), enabled=status != 'running'),
                    pystray.MenuItem('停止', create_service_stop_callback(service), enabled=status == 'running'),
                    pystray.MenuItem('重启', create_service_restart_callback(service), enabled=status == 'running')
                )
                
                menu_items.append(
                    pystray.MenuItem(f"{status_icon}{service.get('name', '未知服务')}", service_submenu)
                )
            menu_items.append(pystray.Menu.SEPARATOR)
        else:
            menu_items.append(pystray.MenuItem('无服务', None, enabled=False))
            menu_items.append(pystray.Menu.SEPARATOR)
        
        # 添加控制台管理选项（一级菜单）
        consoles = self.app.current_tabs
        if consoles:
            for name, tab in consoles.items():
                # 根据状态添加标志
                if tab.is_running:
                    status_icon = '▶ '
                else:
                    status_icon = '◼ '
                
                # 创建控制台子菜单
                def create_console_start_callback(t):
                    def callback(icon=None):
                        self.start_console(t)
                        self.update_menu()
                    return callback
                
                def create_console_stop_callback(t):
                    def callback(icon=None):
                        self.stop_console(t)
                        self.update_menu()
                    return callback
                
                def create_console_restart_callback(t):
                    def callback(icon=None):
                        self.restart_console(t)
                        self.update_menu()
                    return callback
                
                console_submenu = pystray.Menu(
                    pystray.MenuItem('启动', create_console_start_callback(tab), enabled=not tab.is_running),
                    pystray.MenuItem('停止', create_console_stop_callback(tab), enabled=tab.is_running),
                    pystray.MenuItem('重启', create_console_restart_callback(tab), enabled=tab.is_running)
                )
                
                menu_items.append(
                    pystray.MenuItem(f"{status_icon}{name}", console_submenu)
                )
            menu_items.append(pystray.Menu.SEPARATOR)
        else:
            menu_items.append(pystray.MenuItem('无控制台', None, enabled=False))
            menu_items.append(pystray.Menu.SEPARATOR)
        
        # 添加全局操作选项
        menu_items.append(pystray.MenuItem('运行所有控制台', self.run_all_consoles))
        menu_items.append(pystray.MenuItem('停止所有控制台', self.stop_all_consoles))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem('退出', self.exit_app))
        
        # 创建新菜单
        new_menu = pystray.Menu(*menu_items)
        
        # 更新托盘图标菜单
        self.tray_icon.menu = new_menu
    
    def run_all_consoles(self):
        """运行所有控制台"""
        for name, tab in self.app.current_tabs.items():
            if not tab.is_running:
                import threading
                threading.Thread(target=tab.run, daemon=True).start()
    
    def stop_all_consoles(self):
        """停止所有控制台"""
        for name, tab in self.app.current_tabs.items():
            if tab.is_running:
                tab.stop()
    
    def exit_app(self):
        """退出应用程序"""
        # 先停止所有控制台
        self.stop_all_consoles()
        
        # 停止托盘图标
        if self.tray_icon:
            self.tray_icon.stop()
        
        # 退出应用
        self.app.root.quit()
        self.app.root.destroy()
    
    def run(self):
        """运行托盘图标"""
        if self.tray_icon:
            import threading
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
