import os
import sys
from pathlib import Path

# 获取程序所在目录
def get_app_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent

APP_DIR = get_app_dir()

# 配置文件路径（使用程序所在目录）
CONFIG_FILE = APP_DIR / 'config.yaml'
SETTINGS_FILE = APP_DIR / 'settings.json'

# 现代扁平化配色方案
FLAT_THEME = {
    # 主色调 - 更现代的蓝色
    'primary': '#3B82F6',
    'primary_dark': '#2563EB',
    'primary_light': '#60A5FA',
    
    # 状态色 - 更鲜明的色彩
    'success': '#10B981',
    'warning': '#F59E0B',
    'error': '#EF4444',
    'info': '#3B82F6',
    
    # 背景色 - 更现代的深色主题
    'bg_light': '#F3F4F6',
    'bg_dark': '#1E293B',
    'bg_darker': '#0F172A',
    
    # 文本色
    'text_light': '#F8FAFC',
    'text_dark': '#1E293B',
    
    # UI元素
    'border': '#475569',
    'disabled': '#64748B',
    
    # 控制台状态色
    'running': '#10B981',
    'stopped': '#64748B',
    'error_tab': '#EF4444'
}
