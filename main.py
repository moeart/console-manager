import tkinter as tk
from console_manager.console_manager import ConsoleManager

if __name__ == "__main__":
    # 创建根窗口
    root = tk.Tk()
    
    # 初始化控制台管理器
    app = ConsoleManager(root)
    
    # 启动主事件循环
    root.mainloop()
