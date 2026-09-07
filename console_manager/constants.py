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
LOG_FILE = APP_DIR / 'app.log'

# 现代扁平化配色方案（供托盘图标等非 QSS 场景使用，界面配色见 ui/theme.py）
FLAT_THEME = {
    'primary': '#3B82F6',
    'primary_dark': '#2563EB',
    'primary_light': '#60A5FA',
    'success': '#10B981',
    'warning': '#F59E0B',
    'error': '#EF4444',
    'info': '#3B82F6',
    'bg_light': '#F3F4F6',
    'bg_dark': '#1E293B',
    'bg_darker': '#0F172A',
    'text_light': '#F8FAFC',
    'text_dark': '#1E293B',
    'border': '#334155',
    'disabled': '#64748B',
    'running': '#10B981',
    'stopped': '#64748B',
    'error_tab': '#EF4444'
}
