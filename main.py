import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import os
import sys
import json
import threading
import time
from datetime import datetime
import uuid
import shutil
import glob
import webbrowser

# Безопасный импорт psutil
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Предупреждение: psutil не установлен. Мониторинг ресурсов будет отключен.")

# Условные импорты для macOS
if sys.platform == "darwin":
    try:
        import pystray
        from PIL import Image, ImageDraw
        HAS_PYSTRAY = True
    except ImportError:
        HAS_PYSTRAY = False
        print("Предупреждение: pystray/Pillow не установлены. Системный трей недоступен.")
    
    try:
        import plistlib
        HAS_MAC_MODULES = True
    except ImportError:
        HAS_MAC_MODULES = True  # plistlib встроен в Python 3

# Условные импорты для Windows
elif sys.platform == "win32":
    try:
        import pystray
        from PIL import Image, ImageDraw
        HAS_PYSTRAY = True
    except ImportError:
        HAS_PYSTRAY = False
    
    try:
        import winshell
        from win32com.client import Dispatch
        import winreg
        HAS_WIN_MODULES = True
    except ImportError:
        HAS_WIN_MODULES = False
        print("Предупреждение: Windows модули не найдены.")
else:
    # Linux/Unix
    try:
        import pystray
        from PIL import Image, ImageDraw
        HAS_PYSTRAY = True
    except ImportError:
        HAS_PYSTRAY = False


def find_system_python():
    """Находит системный интерпретатор Python"""
    # 1. Поиск в PATH
    python_executable = "python3" if sys.platform != "win32" else "python"
    python_path = shutil.which(python_executable) or shutil.which("python")
    
    if python_path and os.path.exists(python_path):
        return os.path.abspath(python_path)

    # 2. Платформозависимый поиск
    if sys.platform == "win32":
        # Windows
        standard_paths = [
            r"C:\Python*\python.exe",
            r"C:\Program Files\Python*\python.exe",
            r"C:\Program Files (x86)\Python*\python.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Python\Python*\python.exe")
        ]
        
        for path_pattern in standard_paths:
            for found_path in glob.glob(path_pattern):
                if os.path.exists(found_path):
                    return os.path.abspath(found_path)
    
    elif sys.platform == "darwin":
        # macOS
        mac_paths = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/*/bin/python3",
            "/Users/*/.pyenv/shims/python3",
            "/opt/local/bin/python3",
            "/usr/bin/python",
            "/usr/local/bin/python"
        ]
        
        for path_pattern in mac_paths:
            for found_path in glob.glob(path_pattern):
                if os.path.exists(found_path):
                    return os.path.abspath(found_path)
    
    else:
        # Linux/Unix
        unix_paths = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "/bin/python3",
            "/usr/bin/python",
            "/usr/local/bin/python"
        ]
        
        for path_pattern in unix_paths:
            for found_path in glob.glob(path_pattern):
                if os.path.exists(found_path):
                    return os.path.abspath(found_path)

    # 3. Текущий интерпретатор
    return sys.executable


def get_base_path():
    """Определяет базовый путь в зависимости от платформы"""
    if getattr(sys, 'frozen', False):
        # Исполняемый файл
        if sys.platform == "darwin" and ".app/Contents/MacOS/" in sys.executable:
            # macOS .app bundle
            return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(sys.executable))))
        else:
            return os.path.dirname(sys.executable)
    else:
        # Скрипт Python
        return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = get_base_path()

# Настройки тем
THEMES = {
    "light": {
        "bg": "#ffffff", "fg": "#000000",
        "frame_bg": "#f0f0f0", "button_bg": "#e0e0e0",
        "button_fg": "#000000", "listbox_bg": "#ffffff",
        "listbox_fg": "#000000", "progress_bg": "#e0e0e0",
        "progress_fg": "#0078d7", "label_bg": "#f0f0f0",
        "label_fg": "#000000", "console_bg": "#000000",
        "console_fg": "#00ff00", "tree_bg": "#ffffff",
        "tree_fg": "#000000"
    },
    "dark": {
        "bg": "#2d2d30", "fg": "#ffffff",
        "frame_bg": "#3e3e42", "button_bg": "#007acc",
        "button_fg": "#ffffff", "listbox_bg": "#1e1e1e",
        "listbox_fg": "#d4d4d4", "progress_bg": "#3e3e42",
        "progress_fg": "#007acc", "label_bg": "#3e3e42",
        "label_fg": "#ffffff", "console_bg": "#0c0c0c",
        "console_fg": "#00ff00", "tree_bg": "#1e1e1e",
        "tree_fg": "#d4d4d4"
    }
}


class ConsoleDialog(tk.Toplevel):
    def __init__(self, parent, script_name, process, theme="light"):
        super().__init__(parent)
        self.theme = theme
        self.colors = THEMES.get(theme, THEMES["light"])
        self.script_name = script_name
        self.process = process

        self.title(f"Консоль: {script_name}")
        self.geometry("800x600")
        
        # Для macOS убираем topmost
        if sys.platform != "darwin":
            self.attributes('-topmost', True)
        
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        output_frame = ttk.LabelFrame(main_frame, text="Вывод консоли", padding=5)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.output_text = tk.Text(
            output_frame,
            wrap=tk.WORD,
            bg=self.colors["console_bg"],
            fg=self.colors["console_fg"],
            font=("Menlo" if sys.platform == "darwin" else "Consolas", 10),
            insertbackground=self.colors["console_fg"],
            state=tk.DISABLED
        )

        scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scrollbar.set)

        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(input_frame, text="Ввод:").pack(side=tk.LEFT, padx=(0, 5))
        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind('<Return>', self.send_input)
        ttk.Button(input_frame, text="Отправить", command=self.send_input).pack(side=tk.RIGHT)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)
        ttk.Button(buttons_frame, text="Очистить вывод", command=self.clear_output).pack(side=tk.LEFT)
        ttk.Button(buttons_frame, text="Закрыть", command=self.destroy).pack(side=tk.RIGHT)

    def clear_output(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

    def send_input(self, event=None):
        input_text = self.input_entry.get()
        if input_text and self.process and self.process.poll() is None:
            try:
                self.process.stdin.write((input_text + '\n').encode('utf-8'))
                self.process.stdin.flush()
                self.append_text(f"> {input_text}\n")
                self.input_entry.delete(0, tk.END)
            except Exception as e:
                self.append_text(f"Ошибка ввода: {str(e)}\n")

    def append_text(self, text):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def load_historical_output(self, historical_output):
        if historical_output:
            self.append_text(historical_output)


class ErrorDialog(tk.Toplevel):
    def __init__(self, parent, script_name, error_message, theme="light"):
        super().__init__(parent)
        self.theme = theme
        self.colors = THEMES.get(theme, THEMES["light"])

        self.title("Ошибка скрипта")
        self.geometry("700x500")
        self.transient(parent)
        
        if sys.platform != "darwin":
            self.attributes('-topmost', True)

        self.script_name = script_name
        self.error_message = error_message
        self.init_ui()

    def init_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Скрипт: {self.script_name}", 
                 font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(main_frame, text=f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 font=('Arial', 10)).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(main_frame, text="Текст ошибки:", 
                 font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        error_frame = ttk.Frame(main_frame)
        error_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        self.error_text = tk.Text(error_frame, wrap=tk.WORD, width=80, height=15,
                                 font=("Menlo" if sys.platform == "darwin" else "Consolas", 9))
        scrollbar = ttk.Scrollbar(error_frame, orient=tk.VERTICAL, command=self.error_text.yview)
        self.error_text.configure(yscrollcommand=scrollbar.set)

        self.error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.error_text.insert(tk.END, self.error_message)
        self.error_text.config(state=tk.DISABLED)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(buttons_frame, text="Копировать ошибку", command=self.copy_error).pack(side=tk.LEFT)
        ttk.Button(buttons_frame, text="Закрыть", command=self.destroy).pack(side=tk.RIGHT)

    def copy_error(self):
        self.clipboard_clear()
        self.clipboard_append(self.error_message)
        messagebox.showinfo("Успех", "Ошибка скопирована в буфер обмена")


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.parent = parent
        self.title("Настройки Python Script Manager")
        self.geometry("500x450")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        if sys.platform == "win32":
            self.attributes('-topmost', True)

        self.init_ui()

    def init_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        autostart_frame = ttk.LabelFrame(main_frame, text="Настройки приложения", padding=10)
        autostart_frame.pack(fill=tk.X, pady=(0, 10))

        if sys.platform == "darwin":
            self.autostart_var = tk.BooleanVar(value=self.settings.get('autostart', False))
            ttk.Checkbutton(autostart_frame, text="Запускать при входе в систему",
                           variable=self.autostart_var,
                           command=self.toggle_autostart_mac).pack(anchor=tk.W)
        elif sys.platform == "win32":
            self.autostart_var = tk.BooleanVar(value=self.settings.get('autostart', False))
            ttk.Checkbutton(autostart_frame, text="Запускать при старте Windows",
                           variable=self.autostart_var,
                           command=self.toggle_autostart_win).pack(anchor=tk.W)
        else:
            ttk.Label(autostart_frame, text="Автозапуск доступен только на Windows и macOS").pack(anchor=tk.W)

        self.monitoring_var = tk.BooleanVar(value=self.settings.get('performance_monitoring', True))
        ttk.Checkbutton(autostart_frame, text="Включить мониторинг производительности",
                       variable=self.monitoring_var).pack(anchor=tk.W, pady=(5, 0))

        interpreter_frame = ttk.LabelFrame(main_frame, text="Интерпретатор Python", padding=10)
        interpreter_frame.pack(fill=tk.X, pady=(0, 10))

        interpreter_subframe = ttk.Frame(interpreter_frame)
        interpreter_subframe.pack(fill=tk.X)

        self.interpreter_var = tk.StringVar(value=self.settings.get('default_interpreter', find_system_python()))
        interpreter_entry = ttk.Entry(interpreter_subframe, textvariable=self.interpreter_var)
        interpreter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(interpreter_subframe, text="Обзор", command=self.browse_interpreter).pack(side=tk.RIGHT)
        ttk.Button(interpreter_frame, text="Показать установленные пакеты",
                  command=self.show_packages).pack(anchor=tk.W, pady=(5, 0))

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        ttk.Button(buttons_frame, text="Сохранить", command=self.save_settings).pack(side=tk.RIGHT)
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side=tk.RIGHT, padx=(5, 0))

    def toggle_autostart_mac(self):
        """Автозапуск для macOS"""
        try:
            if self.autostart_var.get():
                # Добавить в Login Items
                app_name = "Python Script Manager"
                applescript = f'''
                tell application "System Events"
                    make login item at end with properties {{name:"{app_name}", path:"{sys.executable}", hidden:false}}
                end tell
                '''
                subprocess.run(['osascript', '-e', applescript], check=True)
                messagebox.showinfo("Успех", "Автозапуск включен")
            else:
                # Удалить из Login Items
                app_name = "Python Script Manager"
                applescript = f'''
                tell application "System Events"
                    delete login item "{app_name}"
                end tell
                '''
                subprocess.run(['osascript', '-e', applescript], check=True)
                messagebox.showinfo("Успех", "Автозапуск отключен")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось настроить автозапуск: {str(e)}")
            self.autostart_var.set(not self.autostart_var.get())

    def toggle_autostart_win(self):
        """Автозапуск для Windows"""
        if sys.platform != "win32" or not HAS_WIN_MODULES:
            messagebox.showerror("Ошибка", "Функция доступна только на Windows")
            self.autostart_var.set(not self.autostart_var.get())
            return
        
        try:
            startup_folder = winshell.startup()
            shortcut_path = os.path.join(startup_folder, "Python Script Manager.lnk")
            
            if self.autostart_var.get():
                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.Targetpath = sys.executable
                shortcut.WorkingDirectory = os.path.dirname(sys.executable)
                shortcut.IconLocation = sys.executable
                shortcut.save()
                messagebox.showinfo("Успех", "Автозапуск включен")
            else:
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                messagebox.showinfo("Успех", "Автозапуск отключен")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось настроить автозапуск: {str(e)}")
            self.autostart_var.set(not self.autostart_var.get())

    def browse_interpreter(self):
        filetypes = [("All files", "*")]
        if sys.platform == "win32":
            filetypes = [("Executable files", "*.exe"), ("All files", "*.*")]
        
        path = filedialog.askopenfilename(title="Выберите интерпретатор Python", filetypes=filetypes)
        if path:
            self.interpreter_var.set(path)

    def show_packages(self):
        interpreter = self.interpreter_var.get()
        if not os.path.exists(interpreter):
            messagebox.showerror("Ошибка", "Интерпретатор не найден")
            return
        
        try:
            result = subprocess.run([interpreter, "-m", "pip", "list"], 
                                   capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                packages_window = tk.Toplevel(self)
                packages_window.title("Установленные пакеты")
                packages_window.geometry("600x400")
                packages_window.transient(self)
                packages_window.grab_set()
                
                text_frame = ttk.Frame(packages_window, padding=10)
                text_frame.pack(fill=tk.BOTH, expand=True)
                
                text_widget = tk.Text(text_frame, wrap=tk.WORD)
                scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)
                
                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                text_widget.insert(tk.END, result.stdout)
                text_widget.config(state=tk.DISABLED)
            else:
                messagebox.showerror("Ошибка", f"Ошибка при получении пакетов:\n{result.stderr}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка: {str(e)}")

    def save_settings(self):
        self.settings['default_interpreter'] = self.interpreter_var.get()
        self.settings['performance_monitoring'] = self.monitoring_var.get()
        if hasattr(self, 'autostart_var'):
            self.settings['autostart'] = self.autostart_var.get()
        self.destroy()


class ScriptConfigDialog(tk.Toplevel):
    """Диалог для настройки скрипта"""
    def __init__(self, parent, script_info):
        super().__init__(parent)
        self.script_info = script_info.copy()
        self.parent = parent
        self.result = None
        
        self.title(f"Настройки скрипта: {script_info.get('display_name', script_info['name'])}")
        self.geometry("500x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        if sys.platform == "win32":
            self.attributes('-topmost', True)
            
        self.init_ui()
        
    def init_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Имя скрипта
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(name_frame, text="Отображаемое имя:").pack(anchor=tk.W)
        self.name_var = tk.StringVar(value=self.script_info.get('display_name', self.script_info['name']))
        name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=40)
        name_entry.pack(fill=tk.X, pady=(5, 0))
        
        # Интерпретатор
        interpreter_frame = ttk.Frame(main_frame)
        interpreter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(interpreter_frame, text="Интерпретатор Python:").pack(anchor=tk.W)
        
        interpreter_subframe = ttk.Frame(interpreter_frame)
        interpreter_subframe.pack(fill=tk.X, pady=(5, 0))
        
        self.interpreter_var = tk.StringVar(value=self.script_info.get('interpreter', find_system_python()))
        interpreter_entry = ttk.Entry(interpreter_subframe, textvariable=self.interpreter_var)
        interpreter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(interpreter_subframe, text="Обзор", command=self.browse_interpreter).pack(side=tk.RIGHT)
        
        # Автозапуск
        autostart_frame = ttk.Frame(main_frame)
        autostart_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.autostart_var = tk.BooleanVar(value=self.script_info.get('autostart', False))
        ttk.Checkbutton(autostart_frame, text="Запускать скрипт при старте программы",
                       variable=self.autostart_var).pack(anchor=tk.W)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(buttons_frame, text="Сохранить", command=self.save).pack(side=tk.RIGHT)
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        
    def browse_interpreter(self):
        filetypes = [("All files", "*")]
        if sys.platform == "win32":
            filetypes = [("Executable files", "*.exe"), ("All files", "*.*")]
        
        path = filedialog.askopenfilename(title="Выберите интерпретатор Python", filetypes=filetypes)
        if path:
            self.interpreter_var.set(path)
            
    def save(self):
        self.script_info['display_name'] = self.name_var.get()
        self.script_info['interpreter'] = self.interpreter_var.get()
        self.script_info['autostart'] = self.autostart_var.get()
        self.result = self.script_info
        self.destroy()


class ScriptManagerTkinter:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Script Manager")
        self.root.geometry("1200x800")
        
        # Центрируем окно
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        self.current_theme = "light"
        self.active_scripts = []
        self.saved_scripts = {}
        self.script_frames = []
        self.scripts_file = os.path.join(BASE_PATH, "scripts.json")
        self.settings_file = os.path.join(BASE_PATH, "settings.json")
        self.settings = {}
        self.error_messages = {}
        self.open_consoles = {}
        self.process_output_buffers = {}
        
        self.tray_icon = None
        self.tray_thread = None

        # Для macOS убираем topmost
        if sys.platform != "darwin":
            self.root.protocol('WM_DELETE_WINDOW', self.hide_to_tray)
        else:
            self.root.protocol('WM_DELETE_WINDOW', self.quit_application)

        self.setup_ui()
        self.load_settings()
        self.load_scripts()
        self.start_monitoring()

        if HAS_PYSTRAY and sys.platform != "darwin":
            self.root.after(100, self.setup_tray_icon)

    def apply_theme(self, theme_name):
        """Применяет тему"""
        self.current_theme = theme_name
        colors = THEMES.get(theme_name, THEMES["light"])

        style = ttk.Style()
        style.theme_use('clam')  # Единая тема для всех платформ
        
        style.configure(".", background=colors["bg"], foreground=colors["fg"])
        style.configure("TFrame", background=colors["frame_bg"])
        style.configure("TLabel", background=colors["label_bg"], foreground=colors["label_fg"])
        style.configure("TButton", background=colors["button_bg"], foreground=colors["button_fg"])
        style.configure("Treeview", background=colors["tree_bg"], foreground=colors["tree_fg"],
                       fieldbackground=colors["tree_bg"])
        style.configure("Treeview.Heading", background=colors["button_bg"], 
                       foreground=colors["button_fg"])
        
        self.root.configure(bg=colors["bg"])
        if hasattr(self, 'canvas'):
            self.canvas.configure(bg=colors["bg"])

    def setup_ui(self):
        """Настройка интерфейса"""
        # Меню
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Настройки", command=self.open_settings)
        file_menu.add_separator()
        
        if HAS_PYSTRAY and sys.platform != "darwin":
            file_menu.add_command(label="Свернуть в трей", command=self.hide_to_tray)
        else:
            file_menu.add_command(label="Свернуть", command=self.root.iconify)
        
        file_menu.add_command(label="Выход", command=self.quit_application)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="Светлая тема", command=lambda: self.change_theme("light"))
        view_menu.add_command(label="Тёмная тема", command=lambda: self.change_theme("dark"))
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_info)
        help_menu.add_command(label="GitHub", command=self.open_github)

        # Мониторинг системы
        system_frame = ttk.LabelFrame(self.root, text="Общая нагрузка системы:", padding=10)
        system_frame.pack(fill="x", padx=10, pady=5)

        self.total_cpu_var = tk.IntVar()
        self.total_memory_var = tk.IntVar()

        ttk.Label(system_frame, text="CPU:").grid(row=0, column=0, sticky="w")
        self.total_cpu_bar = ttk.Progressbar(system_frame, variable=self.total_cpu_var, maximum=100)
        self.total_cpu_bar.grid(row=0, column=1, sticky="ew", padx=5)
        self.total_cpu_label = ttk.Label(system_frame, text="0%")
        self.total_cpu_label.grid(row=0, column=2, padx=5)

        ttk.Label(system_frame, text="Память:").grid(row=1, column=0, sticky="w")
        self.total_memory_bar = ttk.Progressbar(system_frame, variable=self.total_memory_var, maximum=100)
        self.total_memory_bar.grid(row=1, column=1, sticky="ew", padx=5)
        self.total_memory_label = ttk.Label(system_frame, text="0%")
        self.total_memory_label.grid(row=1, column=2, padx=5)

        system_frame.columnconfigure(1, weight=1)

        # Активные скрипты
        scripts_frame = ttk.Frame(self.root)
        scripts_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)

        ttk.Label(scripts_frame, text="Активные скрипты:", 
                 font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 5))

        self.canvas = tk.Canvas(scripts_frame, bg=THEMES[self.current_theme]["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(scripts_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Каталог скриптов
        catalog_frame = ttk.Frame(self.root, width=400)
        catalog_frame.pack(side="right", fill="y", padx=10, pady=5)
        catalog_frame.pack_propagate(False)

        saved_frame = ttk.LabelFrame(catalog_frame, text="Каталог скриптов", padding=10)
        saved_frame.pack(fill="both", expand=True)

        buttons_frame = ttk.Frame(saved_frame)
        buttons_frame.pack(fill="x", pady=5)
        
        ttk.Button(buttons_frame, text="Добавить", command=self.add_script).pack(side="left", padx=2)
        ttk.Button(buttons_frame, text="Удалить", command=self.delete_script).pack(side="left", padx=2)
        ttk.Button(buttons_frame, text="Переименовать", 
                  command=self.rename_script_dialog).pack(side="left", padx=2)

        tree_frame = ttk.Frame(saved_frame)
        tree_frame.pack(fill="both", expand=True)

        self.saved_tree = ttk.Treeview(tree_frame, columns=("status",), show="tree headings", height=15)
        self.saved_tree.heading("#0", text="Скрипты")
        self.saved_tree.column("#0", width=250)
        self.saved_tree.heading("status", text="Статус")
        self.saved_tree.column("status", width=100)

        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.saved_tree.yview)
        self.saved_tree.configure(yscrollcommand=tree_scrollbar.set)

        self.saved_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.saved_tree.bind("<Double-Button-1>", self.on_tree_double_click)

        self.apply_theme(self.current_theme)

    def setup_tray_icon(self):
        """Настройка иконки в трее"""
        if not HAS_PYSTRAY:
            return
        
        try:
            image = Image.new('RGB', (64, 64), color='blue')
            draw = ImageDraw.Draw(image)
            draw.text((20, 25), 'PSM', fill='white')
            
            def show_window():
                self.show_from_tray()
            
            menu = pystray.Menu(
                pystray.MenuItem('Открыть', show_window),
                pystray.MenuItem('Выход', self.quit_application)
            )
            
            self.tray_icon = pystray.Icon("psm", image, "Python Script Manager", menu)
            self.tray_icon.run_detached()
        except Exception as e:
            print(f"Ошибка трея: {e}")

    def hide_to_tray(self):
        if HAS_PYSTRAY and self.tray_icon:
            self.root.withdraw()

    def show_from_tray(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def show_info(self):
        """Показывает информацию о программе"""
        info_text = f"""Python Script Manager
Версия 2.0
Платформа: {sys.platform}
Python: {sys.version.split()[0]}

Управление Python-скриптами с мониторингом ресурсов."""
        
        messagebox.showinfo("О программе", info_text)

    def open_github(self):
        webbrowser.open("https://github.com/Vanillllla/ScriptManager")

    def quit_application(self):
        self.save_scripts()
        self.save_settings()
        
        for script_data in self.script_frames:
            if script_data['is_running']:
                self.stop_script(script_data['script_uuid'])
        
        if HAS_PYSTRAY and self.tray_icon:
            self.tray_icon.stop()
        
        self.root.quit()

    def change_theme(self, theme_name):
        self.current_theme = theme_name
        self.apply_theme(theme_name)
        self.settings['theme'] = theme_name
        self.save_settings()

    def open_settings(self):
        dialog = SettingsDialog(self.root, self.settings)
        self.root.wait_window(dialog)
        self.save_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            else:
                self.settings = {
                    'theme': 'light',
                    'performance_monitoring': True,
                    'autostart': False,
                    'default_interpreter': find_system_python()
                }
            
            theme = self.settings.get('theme', 'light')
            self.change_theme(theme)
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            self.settings = {
                'theme': 'light',
                'performance_monitoring': True,
                'autostart': False,
                'default_interpreter': find_system_python()
            }

    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def load_scripts(self):
        try:
            if os.path.exists(self.scripts_file):
                with open(self.scripts_file, 'r', encoding='utf-8') as f:
                    loaded_scripts = json.load(f)
                
                for script_uuid, script_info in loaded_scripts.items():
                    self.saved_scripts[script_uuid] = script_info
                    if script_info.get('is_active', False):
                        self.active_scripts.append(script_uuid)
                        self.create_script_frame(script_uuid)
                
                self.update_saved_tree()
        except Exception as e:
            print(f"Ошибка загрузки скриптов: {e}")

    def save_scripts(self):
        try:
            scripts_to_save = {}
            for script_uuid, script_info in self.saved_scripts.items():
                script_copy = script_info.copy()
                script_copy['is_active'] = script_uuid in self.active_scripts
                scripts_to_save[script_uuid] = script_copy
            
            with open(self.scripts_file, 'w', encoding='utf-8') as f:
                json.dump(scripts_to_save, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения скриптов: {e}")

    def add_script(self):
        filetypes = [("Python files", "*.py"), ("All files", "*")]
        script_path = filedialog.askopenfilename(filetypes=filetypes)
        
        if script_path:
            script_name = os.path.basename(script_path).replace('.py', '')
            script_uuid = str(uuid.uuid4())
            
            script_info = {
                'uuid': script_uuid,
                'name': script_name,
                'display_name': script_name,
                'path': script_path,
                'interpreter': self.settings.get('default_interpreter', find_system_python()),
                'autostart': False
            }
            
            self.saved_scripts[script_uuid] = script_info
            self.active_scripts.append(script_uuid)
            self.create_script_frame(script_uuid)
            self.update_saved_tree()
            self.save_scripts()

    def create_script_frame(self, script_uuid):
        script_info = self.saved_scripts.get(script_uuid)
        if not script_info:
            return
        
        display_name = script_info.get('display_name', script_info['name'])
        
        frame = ttk.LabelFrame(self.scrollable_frame, text=display_name, padding=10)
        frame.pack(fill="x", pady=5, padx=5)
        
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill="x", pady=(0, 8))
        
        console_btn = ttk.Button(controls_frame, text="Консоль", state=tk.DISABLED,
                                command=lambda: self.open_console(script_uuid))
        console_btn.pack(side="right", padx=2)
        
        settings_btn = ttk.Button(controls_frame, text="Настройки",
                                 command=lambda: self.configure_script(script_uuid))
        settings_btn.pack(side="right", padx=2)
        
        remove_btn = ttk.Button(controls_frame, text="Удалить из активных",
                               command=lambda: self.remove_from_active(script_uuid))
        remove_btn.pack(side="right", padx=2)
        
        toggle_btn = ttk.Button(controls_frame, text="Запуск",
                               command=lambda: self.toggle_script(script_uuid))
        toggle_btn.pack(side="right", padx=2)
        
        resources_frame = ttk.Frame(frame)
        resources_frame.pack(fill="x", pady=8)
        
        cpu_var = tk.IntVar()
        memory_var = tk.IntVar()
        
        ttk.Label(resources_frame, text="CPU:").grid(row=0, column=0, sticky="w")
        cpu_bar = ttk.Progressbar(resources_frame, variable=cpu_var, maximum=100)
        cpu_bar.grid(row=0, column=1, sticky="ew", padx=5)
        cpu_label = ttk.Label(resources_frame, text="0%")
        cpu_label.grid(row=0, column=2, padx=5)
        
        ttk.Label(resources_frame, text="Память:").grid(row=1, column=0, sticky="w")
        memory_bar = ttk.Progressbar(resources_frame, variable=memory_var, maximum=100)
        memory_bar.grid(row=1, column=1, sticky="ew", padx=5)
        memory_label = ttk.Label(resources_frame, text="0%")
        memory_label.grid(row=1, column=2, padx=5)
        
        resources_frame.columnconfigure(1, weight=1)
        
        script_frame_data = {
            'frame': frame, 'script_uuid': script_uuid,
            'script_info': script_info, 'process': None,
            'pid': None, 'cpu_var': cpu_var, 'memory_var': memory_var,
            'cpu_label': cpu_label, 'memory_label': memory_label,
            'toggle_btn': toggle_btn, 'console_btn': console_btn,
            'is_running': False
        }
        
        self.script_frames.append(script_frame_data)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def toggle_script(self, script_uuid):
        for script_data in self.script_frames:
            if script_data['script_uuid'] == script_uuid:
                if script_data['is_running']:
                    self.stop_script(script_uuid)
                else:
                    self.start_script(script_uuid)
                break

    def start_script(self, script_uuid):
        for script_data in self.script_frames:
            if script_data['script_uuid'] == script_uuid:
                script_info = script_data['script_info']
                
                try:
                    interpreter = script_info['interpreter']
                    if not os.path.exists(interpreter):
                        interpreter = find_system_python()
                    
                    if sys.platform == "win32":
                        process = subprocess.Popen(
                            [interpreter, script_info['path']],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            universal_newlines=False,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                    else:
                        process = subprocess.Popen(
                            [interpreter, script_info['path']],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            universal_newlines=False
                        )
                    
                    script_data['process'] = process
                    script_data['pid'] = process.pid
                    script_data['is_running'] = True
                    script_data['toggle_btn'].config(text="Остановить")
                    script_data['console_btn'].config(state=tk.NORMAL)
                    
                    self.process_output_buffers[script_uuid] = ""
                    threading.Thread(target=self.monitor_script_output,
                                    args=(script_data,), daemon=True).start()
                    
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось запустить скрипт: {str(e)}")
                break

    def stop_script(self, script_uuid):
        for script_data in self.script_frames:
            if script_data['script_uuid'] == script_uuid and script_data['process']:
                try:
                    script_data['process'].terminate()
                    script_data['process'].wait(timeout=3)
                except:
                    try:
                        script_data['process'].kill()
                    except:
                        pass
                
                script_data['process'] = None
                script_data['pid'] = None
                script_data['is_running'] = False
                script_data['toggle_btn'].config(text="Запуск")
                script_data['console_btn'].config(state=tk.DISABLED)
                script_data['cpu_var'].set(0)
                script_data['memory_var'].set(0)
                script_data['cpu_label'].config(text="0%")
                script_data['memory_label'].config(text="0%")
                break

    def monitor_script_output(self, script_data):
        """Мониторинг вывода скрипта"""
        process = script_data['process']
        script_uuid = script_data['script_uuid']
        
        def read_stream(stream):
            try:
                for line in iter(stream.readline, ''):
                    if line:
                        decoded = line.decode('utf-8', errors='replace')
                        if script_uuid in self.process_output_buffers:
                            self.process_output_buffers[script_uuid] += decoded
                        
                        if script_uuid in self.open_consoles:
                            console = self.open_consoles[script_uuid]
                            if console.winfo_exists():
                                console.after(0, lambda d=decoded: console.append_text(d))
            except Exception as e:
                print(f"Ошибка чтения вывода: {e}")
        
        threading.Thread(target=read_stream, args=(process.stdout,), daemon=True).start()
        threading.Thread(target=read_stream, args=(process.stderr,), daemon=True).start()
        
        process.wait()
        script_data['is_running'] = False
        if script_data['toggle_btn'].winfo_exists():
            script_data['toggle_btn'].config(text="Запуск")
            script_data['console_btn'].config(state=tk.DISABLED)

    def open_console(self, script_uuid):
        for script_data in self.script_frames:
            if script_data['script_uuid'] == script_uuid and script_data['is_running']:
                script_info = script_data['script_info']
                script_name = script_info.get('display_name', script_info['name'])
                
                if script_uuid in self.open_consoles:
                    try:
                        self.open_consoles[script_uuid].lift()
                        return
                    except:
                        del self.open_consoles[script_uuid]
                
                console = ConsoleDialog(self.root, script_name, script_data['process'], self.current_theme)
                if script_uuid in self.process_output_buffers:
                    console.load_historical_output(self.process_output_buffers[script_uuid])
                
                self.open_consoles[script_uuid] = console
                
                def on_close():
                    if script_uuid in self.open_consoles:
                        del self.open_consoles[script_uuid]
                
                console.protocol("WM_DELETE_WINDOW", on_close)
                break

    def update_saved_tree(self):
        self.saved_tree.delete(*self.saved_tree.get_children())
        
        active_node = self.saved_tree.insert("", "end", text="Активные скрипты")
        inactive_node = self.saved_tree.insert("", "end", text="Неактивные скрипты")
        
        for script_uuid in self.active_scripts:
            script_info = self.saved_scripts.get(script_uuid)
            if script_info:
                name = script_info.get('display_name', script_info['name'])
                status = "Запущен" if self.is_script_running(script_uuid) else "Остановлен"
                self.saved_tree.insert(active_node, "end", text=name, values=(status,))
        
        for script_uuid, script_info in self.saved_scripts.items():
            if script_uuid not in self.active_scripts:
                name = script_info.get('display_name', script_info['name'])
                self.saved_tree.insert(inactive_node, "end", text=name, values=("Неактивен",))
        
        self.saved_tree.item(active_node, open=True)
        self.saved_tree.item(inactive_node, open=True)

    def is_script_running(self, script_uuid):
        for script_data in self.script_frames:
            if script_data['script_uuid'] == script_uuid:
                return script_data['is_running']
        return False

    def on_tree_double_click(self, event):
        selection = self.saved_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        parent = self.saved_tree.parent(item)
        
        if parent:
            item_text = self.saved_tree.item(item)["text"]
            parent_text = self.saved_tree.item(parent)["text"]
            
            script_uuid = None
            for uuid, info in self.saved_scripts.items():
                if info.get('display_name', info['name']) == item_text:
                    script_uuid = uuid
                    break
            
            if script_uuid:
                if parent_text == "Активные скрипты":
                    if messagebox.askyesno("Подтверждение", f"Переместить '{item_text}' в неактивные?"):
                        self.remove_from_active(script_uuid)
                elif parent_text == "Неактивные скрипты":
                    self.add_to_active(script_uuid)

    def remove_from_active(self, script_uuid):
        if script_uuid in self.active_scripts:
            self.active_scripts.remove(script_uuid)
        
        for i, script_data in enumerate(self.script_frames):
            if script_data['script_uuid'] == script_uuid:
                if script_data['is_running']:
                    self.stop_script(script_uuid)
                script_data['frame'].destroy()
                self.script_frames.pop(i)
                break
        
        self.update_saved_tree()
        self.save_scripts()

    def add_to_active(self, script_uuid):
        if script_uuid not in self.active_scripts:
            self.active_scripts.append(script_uuid)
            self.create_script_frame(script_uuid)
            self.update_saved_tree()
            self.save_scripts()

    def delete_script(self):
        selection = self.saved_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        parent = self.saved_tree.parent(item)
        
        if not parent:
            return
        
        item_text = self.saved_tree.item(item)["text"]
        script_uuid = None
        
        for uuid, info in self.saved_scripts.items():
            if info.get('display_name', info['name']) == item_text:
                script_uuid = uuid
                break
        
        if script_uuid and messagebox.askyesno("Подтверждение", f"Удалить скрипт '{item_text}'?"):
            if script_uuid in self.active_scripts:
                self.remove_from_active(script_uuid)
            
            del self.saved_scripts[script_uuid]
            self.update_saved_tree()
            self.save_scripts()

    def rename_script_dialog(self):
        """Диалог переименования скрипта"""
        selection = self.saved_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        parent = self.saved_tree.parent(item)
        
        if not parent:
            return
        
        item_text = self.saved_tree.item(item)["text"]
        script_uuid = None
        
        for uuid, info in self.saved_scripts.items():
            if info.get('display_name', info['name']) == item_text:
                script_uuid = uuid
                break
        
        if script_uuid:
            new_name = simpledialog.askstring("Переименовать скрипт", 
                                             "Введите новое имя:", 
                                             initialvalue=item_text)
            if new_name:
                self.rename_script(script_uuid, new_name)
                
    def rename_script(self, script_uuid, new_name):
        """Переименовывает скрипт"""
        if script_uuid in self.saved_scripts:
            script_info = self.saved_scripts[script_uuid]
            script_info['display_name'] = new_name
            
            # Обновляем дерево
            self.update_saved_tree()
            
            # Обновляем фрейм если скрипт активен
            for script_data in self.script_frames:
                if script_data['script_uuid'] == script_uuid:
                    script_data['frame'].configure(text=new_name)
                    break
            
            self.save_scripts()

    def configure_script(self, script_uuid):
        """Настройка скрипта через диалог"""
        if script_uuid not in self.saved_scripts:
            return
        
        script_info = self.saved_scripts[script_uuid]
        
        # Создаем диалог настроек
        dialog = ScriptConfigDialog(self.root, script_info)
        self.root.wait_window(dialog)
        
        if dialog.result:
            # Обновляем информацию о скрипте
            self.saved_scripts[script_uuid] = dialog.result
            
            # Обновляем интерфейс
            new_name = dialog.result.get('display_name', dialog.result['name'])
            
            # Обновляем дерево
            self.update_saved_tree()
            
            # Обновляем фрейм если скрипт активен
            for script_data in self.script_frames:
                if script_data['script_uuid'] == script_uuid:
                    script_data['frame'].configure(text=new_name)
                    script_data['script_info'] = dialog.result
                    break
            
            self.save_scripts()

    def start_monitoring(self):
        def monitor():
            if not HAS_PSUTIL or not self.settings.get('performance_monitoring', True):
                self.total_cpu_var.set(0)
                self.total_memory_var.set(0)
                self.total_cpu_label.config(text="0%")
                self.total_memory_label.config(text="0%")
                
                for script_data in self.script_frames:
                    if script_data['frame'].winfo_exists():
                        script_data['cpu_var'].set(0)
                        script_data['memory_var'].set(0)
                        script_data['cpu_label'].config(text="0%")
                        script_data['memory_label'].config(text="0%")
            else:
                try:
                    system_cpu = psutil.cpu_percent(interval=0.1)
                    system_memory = psutil.virtual_memory().percent
                    
                    self.total_cpu_var.set(int(system_cpu))
                    self.total_memory_var.set(int(system_memory))
                    self.total_cpu_label.config(text=f"{system_cpu:.1f}%")
                    self.total_memory_label.config(text=f"{system_memory:.1f}%")
                    
                    for script_data in self.script_frames:
                        if not script_data['frame'].winfo_exists():
                            continue
                        
                        if script_data['is_running'] and script_data['pid']:
                            try:
                                process = psutil.Process(script_data['pid'])
                                cpu = process.cpu_percent(interval=0.1)
                                memory = process.memory_percent()
                                
                                script_data['cpu_var'].set(int(cpu))
                                script_data['memory_var'].set(int(memory))
                                script_data['cpu_label'].config(text=f"{cpu:.1f}%")
                                script_data['memory_label'].config(text=f"{memory:.1f}%")
                            except:
                                script_data['is_running'] = False
                                script_data['cpu_var'].set(0)
                                script_data['memory_var'].set(0)
                                script_data['cpu_label'].config(text="0%")
                                script_data['memory_label'].config(text="0%")
                        else:
                            script_data['cpu_var'].set(0)
                            script_data['memory_var'].set(0)
                            script_data['cpu_label'].config(text="0%")
                            script_data['memory_label'].config(text="0%")
                except Exception as e:
                    print(f"Ошибка мониторинга: {e}")
            
            self.root.after(1000, monitor)
        
        self.root.after(1000, monitor)


def main():
    """Точка входа с обработкой исключений"""
    try:
        root = tk.Tk()
        
        # Для macOS настройка внешнего вида
        if sys.platform == "darwin":
            # Используем нативный вид
            root.tk.call("tk", "scaling", 2.0)
        
        app = ScriptManagerTkinter(root)
        root.mainloop()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
