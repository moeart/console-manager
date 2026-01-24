import tkinter as tk
from tkinter import ttk

class ScrolledNotebook(ttk.Frame):
    """可滚动的Notebook控件"""
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent)
        
        # 创建一个Frame来容纳按钮和Notebook
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # 创建Notebook
        self.notebook = ttk.Notebook(self.container)
        self.notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 移除默认的左右按钮，将在工具栏中添加
        
        # 绑定事件
        self.notebook.bind('<Button-4>', lambda e: self.scroll_left())
        self.notebook.bind('<Button-5>', lambda e: self.scroll_right())
        self.notebook.bind('<MouseWheel>', self.on_mousewheel)
        
        # 绑定标签页变化和窗口大小变化事件
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        self.notebook.bind('<Configure>', self.on_configure)
        
        # 初始状态
        self.current_position = 0
        self.tab_count = 0
        self.max_visible_tabs = 0
        
    def scroll_left(self):
        """向左滚动标签页"""
        if self.current_position > 0:
            self.current_position -= 1
            self.update_tab_position()
    
    def scroll_right(self):
        """向右滚动标签页"""
        if self.current_position < self.tab_count - self.max_visible_tabs:
            self.current_position += 1
            self.update_tab_position()
    
    def on_mousewheel(self, event):
        """鼠标滚轮滚动"""
        if event.delta > 0:
            self.scroll_left()
        else:
            self.scroll_right()
    
    def update_tab_position(self):
        """更新标签页位置"""
        # 获取所有标签页
        tabs = self.notebook.tabs()
        
        # 隐藏当前不可见的标签页
        for i, tab in enumerate(tabs):
            if i >= self.current_position and i < self.current_position + self.max_visible_tabs:
                self.notebook.tab(tab, state="normal")
            else:
                self.notebook.tab(tab, state="hidden")
        
        # 更新按钮状态
        # 注意：按钮状态将由外部调用更新
        
        # 确保当前选中的标签页可见
        self.ensure_selected_tab_visible()
    
    def update_buttons_state(self, left_button=None, right_button=None):
        """更新按钮状态"""
        # 更新向左按钮状态
        if left_button:
            if self.current_position > 0:
                left_button.config(state="normal")
            else:
                left_button.config(state="disabled")
        
        # 更新向右按钮状态
        if right_button:
            if self.current_position < self.tab_count - self.max_visible_tabs:
                right_button.config(state="normal")
            else:
                right_button.config(state="disabled")
    
    def on_tab_changed(self, event):
        """标签页变化时，确保当前标签可见"""
        self.ensure_selected_tab_visible()
    
    def on_configure(self, event=None):
        """窗口大小变化时，重新计算可见标签页数量"""
        # 重新计算最大可见标签页数量
        self.calculate_max_visible_tabs()
        
        # 更新标签页位置
        self.update_tab_position()
    
    def calculate_max_visible_tabs(self):
        """计算最大可见标签页数量"""
        # 获取Notebook的宽度
        notebook_width = self.notebook.winfo_width()
        
        if notebook_width > 1:  # 确保已经显示
            # 假设每个标签页最小宽度为100像素（可以调整）
            min_tab_width = 100
            
            # 计算最大可见标签页数量
            self.max_visible_tabs = max(1, notebook_width // min_tab_width)
    
    def ensure_selected_tab_visible(self):
        """确保当前选中的标签页可见"""
        current = self.notebook.select()
        if current:
            index = self.notebook.index(current)
            
            # 如果当前标签页在可见区域之外，调整位置
            if index < self.current_position:
                self.current_position = index
                self.update_tab_position()
            elif index >= self.current_position + self.max_visible_tabs:
                self.current_position = index - self.max_visible_tabs + 1
                self.update_tab_position()
    
    def add(self, *args, **kwargs):
        """添加标签页"""
        result = self.notebook.add(*args, **kwargs)
        
        # 更新标签页计数
        self.tab_count = len(self.notebook.tabs())
        
        # 重新计算最大可见标签页数量
        self.calculate_max_visible_tabs()
        
        # 更新标签页位置和按钮状态
        self.update_tab_position()
        
        return result
    
    def forget(self, index):
        """删除标签页"""
        self.notebook.forget(index)
        
        # 更新标签页计数
        self.tab_count = len(self.notebook.tabs())
        
        # 调整当前位置，确保在合理范围内
        if self.current_position >= self.tab_count:
            self.current_position = max(0, self.tab_count - self.max_visible_tabs)
        
        # 重新计算最大可见标签页数量
        self.calculate_max_visible_tabs()
        
        # 更新标签页位置和按钮状态
        self.update_tab_position()
    
    def select(self, tab_id=None):
        """获取或设置当前选中的标签页"""
        if tab_id is None:
            return self.notebook.select()
        else:
            return self.notebook.select(tab_id)
    
    def index(self, tab_id):
        """获取标签页索引"""
        return self.notebook.index(tab_id)
    
    def tab(self, tab_id, option=None):
        """获取或设置标签页属性"""
        return self.notebook.tab(tab_id, option)
    
    def tabs(self):
        """获取所有标签页"""
        return self.notebook.tabs()


# 测试代码
if __name__ == "__main__":
    root = tk.Tk()
    root.title("可滚动标签页示例")
    root.geometry("600x400")
    
    # 创建可滚动的Notebook
    scrolled_notebook = ScrolledNotebook(root)
    scrolled_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 添加一些标签页
    for i in range(15):
        frame = ttk.Frame(scrolled_notebook)
        label = ttk.Label(frame, text=f"这是标签页 {i+1} 的内容", font=("Arial", 14))
        label.pack(expand=True, padx=20, pady=20)
        scrolled_notebook.add(frame, text=f"标签页 {i+1}")
    
    # 添加控制按钮
    control_frame = ttk.Frame(root)
    control_frame.pack(fill=tk.X, padx=10, pady=5)
    
    def add_tab():
        frame = ttk.Frame(scrolled_notebook)
        label = ttk.Label(frame, text="新增的标签页", font=("Arial", 14))
        label.pack(expand=True, padx=20, pady=20)
        scrolled_notebook.add(frame, text=f"新增 {len(scrolled_notebook.tabs())+1}")
    
    def remove_tab():
        tabs = scrolled_notebook.tabs()
        if tabs:
            scrolled_notebook.forget(tabs[-1])
    
    add_button = ttk.Button(control_frame, text="添加标签页", command=add_tab)
    add_button.pack(side=tk.LEFT, padx=5)
    
    remove_button = ttk.Button(control_frame, text="删除标签页", command=remove_tab)
    remove_button.pack(side=tk.LEFT, padx=5)
    
    # 显示当前标签页信息
    def show_info():
        current = scrolled_notebook.select()
        if current:
            index = scrolled_notebook.index(current)
            info_label.config(text=f"当前标签页: {index+1} / {len(scrolled_notebook.tabs())}")
    
    info_button = ttk.Button(control_frame, text="显示信息", command=show_info)
    info_button.pack(side=tk.LEFT, padx=5)
    
    info_label = ttk.Label(control_frame, text="")
    info_label.pack(side=tk.LEFT, padx=20)
    
    root.mainloop()