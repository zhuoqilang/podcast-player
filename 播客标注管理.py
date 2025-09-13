import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os
import sqlite3
import subprocess
import json
import webbrowser

class PodcastAnnotationManager:
    def __init__(self, root):
        self.root = root
        self.root.title("播客标注管理")
        self.root.geometry("1800x1000")

        # 设置样式
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("微软雅黑", 12))
        self.style.configure("TButton", font=("微软雅黑", 12))
        self.style.configure("TEntry", font=("微软雅黑", 14))
        self.style.configure("TText", font=("微软雅黑", 14))
        self.style.configure("TListbox", font=("微软雅黑", 12))
        self.style.configure("TLabelframe.Label", font=("微软雅黑", 14, "bold"))

        # 文件路径
        self.program_dir = os.path.dirname(os.path.abspath(__file__))
        self.system_db_path = os.path.join(self.program_dir, "podcast_system.db")
        self.albums_dir = os.path.join(self.program_dir, "albums")
        self.current_album_id = ""
        self.current_album_path = ""
        self.album_db_path = ""

        # 数据存储
        self.nodes = {}  # {node_name: {'name': name, 'description': description}}
        self.edges = []  # [{'source': source_name, 'target': target_name}]
        self.audio_info = []  # 存储音频信息 (id, filename, duration, title, annotation)
        self.current_node_name = None  # 当前选中的节点名称
        self.system_db_conn = None  # 系统数据库连接
        self.album_db_conn = None  # 专辑数据库连接

        # 创建状态栏变量
        self.status_var = tk.StringVar()

        # 创建界面
        self.create_widgets()

        # 初始化数据库
        self.init_system_database()
        self.show_album_list_interface()  # 启动时显示专辑列表

    def create_widgets(self):
        # 主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        # 不立即pack，等待选择专辑后再显示

    def show_album_list_interface(self):
        # 清空现有界面
        for widget in self.root.winfo_children():
            widget.destroy()

        album_frame = ttk.Frame(self.root, padding="10")
        album_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(album_frame, text="播客标注管理 - 选择专辑",
                  font=("微软雅黑", 14, "bold")).pack(pady=30)

        center_frame = ttk.Frame(album_frame)
        center_frame.pack(expand=True, fill=tk.BOTH, padx=50, pady=20)

        # 创建滚动条
        scrollbar = ttk.Scrollbar(center_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建专辑列表框
        self.album_listbox = tk.Listbox(center_frame, yscrollcommand=scrollbar.set, font=("微软雅黑", 12), width=50, height=15)
        self.album_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.album_listbox.yview)
        self.album_listbox.bind('<Double-1>', self.on_album_select)

        # 加载现有专辑
        self.load_existing_albums()

        # 按钮框架
        btn_frame = ttk.Frame(album_frame)
        btn_frame.pack(side=tk.BOTTOM, pady=50)

        ttk.Button(btn_frame, text="刷新列表", command=self.load_existing_albums).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="输入专辑ID", command=self.init_input_frame).pack(side=tk.RIGHT, padx=10)

    def load_existing_albums(self):
        # 清空列表
        self.album_listbox.delete(0, tk.END)
        self.albums = []  # 存储专辑信息 [(album_id, album_name, album_path)]

        # 检查albums目录是否存在
        if not os.path.exists(self.albums_dir):
            messagebox.showwarning("警告", f"找不到专辑目录: {self.albums_dir}")
            return

        # 获取albums目录下的所有子目录
        try:
            for dir_name in os.listdir(self.albums_dir):
                dir_path = os.path.join(self.albums_dir, dir_name)
                # 检查是否是目录，并且目录名以"album_"开头
                if os.path.isdir(dir_path) and dir_name.startswith("album_"):
                    # 提取专辑ID
                    album_id = dir_name[len("album_"):]
                    # 检查专辑数据库文件是否存在
                    album_db_path = os.path.join(dir_path, f"album_{album_id}.db")
                    if os.path.exists(album_db_path):
                        # 尝试从数据库中获取专辑名称
                        album_name = f"专辑 {album_id}"
                        try:
                            temp_conn = sqlite3.connect(album_db_path)
                            cursor = temp_conn.cursor()
                            cursor.execute("SELECT title FROM album_info LIMIT 1")
                            result = cursor.fetchone()
                            if result and result[0]:
                                album_name = result[0]
                            temp_conn.close()
                        except Exception as e:
                            print(f"获取专辑名称失败: {str(e)}")

                        # 添加到列表
                        self.albums.append((album_id, album_name, dir_path))
                        self.album_listbox.insert(tk.END, f"{album_name} (ID: {album_id})")

            if not self.albums:
                self.album_listbox.insert(tk.END, "没有找到任何专辑数据")
                self.album_listbox.configure(state=tk.DISABLED)
            else:
                self.album_listbox.configure(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("错误", f"加载专辑列表失败: {str(e)}")

    def on_album_select(self, event):
        selection = self.album_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.albums):
                album_id, album_name, album_path = self.albums[index]
                self.select_album(album_id, album_path)

    def select_album(self, album_id, album_path):
        # 设置专辑变量
        self.current_album_id = album_id
        self.current_album_path = album_path
        self.album_db_path = os.path.join(self.current_album_path, f"album_{album_id}.db")

        if not os.path.exists(self.album_db_path):
            messagebox.showerror("错误", f"找不到专辑数据库文件: {self.album_db_path}\n请先使用播客预处理程序获取专辑信息")
            return

        # 检查文件是否为符号链接，如果是，尝试获取实际路径
        if os.path.islink(self.album_db_path):
            try:
                # 获取符号链接指向的实际文件路径
                real_db_path = os.path.realpath(self.album_db_path)
                self.update_status(f"检测到符号链接，实际路径: {real_db_path}")
                
                # 检查实际文件是否可写
                if not os.access(real_db_path, os.W_OK):
                    # 如果实际文件不可写，尝试创建一个可写的副本
                    temp_dir = os.environ.get('TEMP', '.')
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    temp_db_path = os.path.join(temp_dir, f"temp_album_{album_id}.db")
                    import shutil
                    shutil.copy2(real_db_path, temp_db_path)
                    # 确保临时文件有写入权限
                    os.chmod(temp_db_path, 0o666)  # 给予读写权限
                    self.album_db_path = temp_db_path
                    self.update_status(f"已创建数据库副本用于编辑: {temp_db_path}")
                else:
                    self.album_db_path = real_db_path
            except Exception as e:
                self.update_status(f"处理符号链接失败: {str(e)}")
        
        # 检查文件是否可写
            if os.path.exists(self.album_db_path) and not os.access(self.album_db_path, os.W_OK):
                # 使用字符串替换确保路径在Windows上正确显示
                display_path = self.album_db_path.replace('\\', '\\\\')
                messagebox.showwarning("文件权限警告", f"数据库文件不可写，将创建临时副本用于编辑\n{display_path}")
                # 创建临时副本，尝试多个备选路径
                temp_paths = []
                # 首选系统TEMP目录
                temp_dir = os.environ.get('TEMP', '.')
                temp_paths.append(os.path.join(temp_dir, f"temp_album_{album_id}.db"))
                # 备选1：当前目录
                temp_paths.append(os.path.join('.', f"temp_album_{album_id}.db"))
                # 备选2：程序目录
                temp_paths.append(os.path.join(self.program_dir, f"temp_album_{album_id}.db"))
                
                # 尝试创建临时副本
                temp_db_path = None
                for path in temp_paths:
                    try:
                        # 确保目标目录存在
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        # 尝试复制文件
                        import shutil
                        shutil.copy2(self.album_db_path, path)
                        # 尝试设置权限（在Windows上可能会失败，但继续执行）
                        try:
                            os.chmod(path, 0o666)  # 给予读写权限
                        except Exception:
                            pass
                        temp_db_path = path
                        break  # 成功创建临时副本后退出循环
                    except Exception as e:
                        self.update_status(f"创建临时副本失败 ({path}): {str(e)}")
                        continue
                
                if temp_db_path:
                    self.album_db_path = temp_db_path
                    self.update_status(f"已成功创建数据库临时副本: {temp_db_path}")
                else:
                    messagebox.showerror("错误", "无法创建数据库临时副本，请检查文件权限")
                    return

        # 初始化专辑数据库连接，使用可读写模式
        try:
            # 确保以可读写模式打开数据库，避免只读问题
            # 添加更多参数确保在Windows上正确处理锁定问题
            # 先尝试基本连接方式，这种方式在Windows上更稳定
            self.album_db_conn = sqlite3.connect(self.album_db_path, check_same_thread=False, timeout=10)
            self.update_status(f"已连接到数据库: {self.album_db_path}")
            
            # 测试写入权限
            cursor = self.album_db_conn.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")  # 使用WAL模式提高并发性能
            cursor.execute("CREATE TABLE IF NOT EXISTS test_write (id INTEGER)")
            cursor.execute("DROP TABLE IF EXISTS test_write")
            self.album_db_conn.commit()
            self.update_status(f"数据库写入权限测试通过")
        except sqlite3.OperationalError as e:
            if "attempt to write a readonly database" in str(e) or "database is locked" in str(e):
                # 再次尝试创建新的临时副本，确保使用最新的文件状态
                self.update_status(f"数据库连接失败，尝试创建新的临时副本: {str(e)}")
                try:
                    temp_dir = os.environ.get('TEMP', '.')
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    new_temp_path = os.path.join(temp_dir, f"temp_album_{album_id}_new.db")
                    import shutil
                    shutil.copy2(self.album_db_path, new_temp_path)
                    os.chmod(new_temp_path, 0o666)
                    self.album_db_path = new_temp_path
                    self.update_status(f"已创建新的数据库临时副本: {new_temp_path}")
                    
                    # 再次尝试连接新的临时副本
                    self.album_db_conn = sqlite3.connect(new_temp_path, check_same_thread=False, timeout=10)
                    self.update_status(f"已成功连接到新的临时副本")
                except Exception as e2:
                    messagebox.showerror("数据库错误", f"创建并连接临时副本失败: {str(e2)}")
                    return
            else:
                messagebox.showerror("数据库错误", f"连接专辑数据库失败: {str(e)}")
                return
        except Exception as e:
            messagebox.showerror("数据库错误", f"连接专辑数据库失败: {str(e)}")
            return

        # 显示主界面
        self.show_main_interface()

        # 加载数据
        self.load_data()
        self.load_audio_data()
        self.update_status(f"已加载专辑: {album_id}")

    def load_album(self):
        album_id = self.album_id_var.get().strip()

        if not album_id.isdigit():
            messagebox.showerror("输入错误", "专辑ID必须是数字")
            return

        # 检查专辑文件夹是否存在
        self.current_album_id = album_id
        self.current_album_path = os.path.join(self.albums_dir, f"album_{album_id}")
        self.album_db_path = os.path.join(self.current_album_path, f"album_{album_id}.db")

        if not os.path.exists(self.album_db_path):
            messagebox.showerror("错误", f"找不到专辑数据库文件: {self.album_db_path}\n请先使用播客预处理程序获取专辑信息")
            return

        # 检查文件是否为符号链接，如果是，尝试获取实际路径
        if os.path.islink(self.album_db_path):
            try:
                # 获取符号链接指向的实际文件路径
                real_db_path = os.path.realpath(self.album_db_path)
                self.update_status(f"检测到符号链接，实际路径: {real_db_path}")
                
                # 检查实际文件是否可写
                if not os.access(real_db_path, os.W_OK):
                    # 如果实际文件不可写，尝试创建一个可写的副本
                    temp_dir = os.environ.get('TEMP', '.')
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    temp_db_path = os.path.join(temp_dir, f"temp_album_{album_id}.db")
                    import shutil
                    shutil.copy2(real_db_path, temp_db_path)
                    # 确保临时文件有写入权限
                    os.chmod(temp_db_path, 0o666)  # 给予读写权限
                    self.album_db_path = temp_db_path
                    self.update_status(f"已创建数据库副本用于编辑: {temp_db_path}")
                else:
                    self.album_db_path = real_db_path
            except Exception as e:
                self.update_status(f"处理符号链接失败: {str(e)}")
        
        # 检查文件是否可写
        if os.path.exists(self.album_db_path) and not os.access(self.album_db_path, os.W_OK):
            # 使用字符串替换确保路径在Windows上正确显示
            display_path = self.album_db_path.replace('\\', '\\\\')
            messagebox.showwarning("文件权限警告", f"数据库文件不可写，将创建临时副本用于编辑\n{display_path}")
            # 创建临时副本，尝试多个备选路径
            temp_paths = []
            # 首选系统TEMP目录
            temp_dir = os.environ.get('TEMP', '.')
            temp_paths.append(os.path.join(temp_dir, f"temp_album_{album_id}.db"))
            # 备选1：当前目录
            temp_paths.append(os.path.join('.', f"temp_album_{album_id}.db"))
            # 备选2：程序目录
            temp_paths.append(os.path.join(self.program_dir, f"temp_album_{album_id}.db"))
            
            # 尝试创建临时副本
            temp_db_path = None
            for path in temp_paths:
                try:
                    # 确保目标目录存在
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    # 尝试复制文件
                    import shutil
                    shutil.copy2(self.album_db_path, path)
                    # 尝试设置权限（在Windows上可能会失败，但继续执行）
                    try:
                        os.chmod(path, 0o666)  # 给予读写权限
                    except Exception:
                        pass
                    temp_db_path = path
                    break  # 成功创建临时副本后退出循环
                except Exception as e:
                    self.update_status(f"创建临时副本失败 ({path}): {str(e)}")
                    continue
            
            if temp_db_path:
                self.album_db_path = temp_db_path
                self.update_status(f"已成功创建数据库临时副本: {temp_db_path}")
            else:
                messagebox.showerror("错误", "无法创建数据库临时副本，请检查文件权限")
                return

        # 初始化专辑数据库连接，使用可读写模式
        try:
            # 确保以可读写模式打开数据库，避免只读问题
            # 添加更多参数确保在Windows上正确处理锁定问题
            # 先尝试基本连接方式，这种方式在Windows上更稳定
            self.album_db_conn = sqlite3.connect(self.album_db_path, check_same_thread=False, timeout=10)
            self.update_status(f"已连接到数据库: {self.album_db_path}")
            
            # 测试写入权限
            cursor = self.album_db_conn.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")  # 使用WAL模式提高并发性能
            cursor.execute("CREATE TABLE IF NOT EXISTS test_write (id INTEGER)")
            cursor.execute("DROP TABLE IF EXISTS test_write")
            self.album_db_conn.commit()
            self.update_status(f"数据库写入权限测试通过")
        except sqlite3.OperationalError as e:
            if "attempt to write a readonly database" in str(e) or "database is locked" in str(e):
                # 再次尝试创建新的临时副本，确保使用最新的文件状态
                self.update_status(f"数据库连接失败，尝试创建新的临时副本: {str(e)}")
                try:
                    temp_dir = os.environ.get('TEMP', '.')
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    new_temp_path = os.path.join(temp_dir, f"temp_album_{album_id}_new.db")
                    import shutil
                    shutil.copy2(self.album_db_path, new_temp_path)
                    os.chmod(new_temp_path, 0o666)
                    self.album_db_path = new_temp_path
                    self.update_status(f"已创建新的数据库临时副本: {new_temp_path}")
                    
                    # 再次尝试连接新的临时副本
                    self.album_db_conn = sqlite3.connect(new_temp_path, check_same_thread=False, timeout=10)
                    self.update_status(f"已成功连接到新的临时副本")
                except Exception as e2:
                    messagebox.showerror("数据库错误", f"创建并连接临时副本失败: {str(e2)}")
                    return
            else:
                messagebox.showerror("数据库错误", f"连接专辑数据库失败: {str(e)}")
                return
        except Exception as e:
            messagebox.showerror("数据库错误", f"连接专辑数据库失败: {str(e)}")
            return

        # 显示主界面
        self.show_main_interface()

        # 加载数据
        self.load_data()
        self.load_audio_data()
        self.update_status(f"已加载专辑ID: {album_id}")

    def init_input_frame(self):
        # 清空现有界面
        for widget in self.root.winfo_children():
            widget.destroy()

        input_frame = ttk.Frame(self.root, padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(input_frame, text="播客标注管理 - 输入专辑ID",
                  font=("微软雅黑", 14, "bold")).pack(pady=30)

        center_frame = ttk.Frame(input_frame)
        center_frame.pack(expand=True)

        ttk.Label(center_frame, text="喜马拉雅专辑ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.album_id_var = tk.StringVar()
        ttk.Entry(center_frame, textvariable=self.album_id_var, width=50).grid(row=0, column=1, sticky=tk.W, pady=5)

        # 按钮框架
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side=tk.BOTTOM, pady=50)

        ttk.Button(btn_frame, text="返回专辑列表", command=self.show_album_list_interface).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="加载专辑", command=self.load_album).pack(side=tk.RIGHT, padx=10)

    def show_main_interface(self):
        # 清空现有界面
        for widget in self.root.winfo_children():
            widget.destroy()

        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 左侧节点列表
        left_frame = ttk.Frame(self.main_frame, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5)
        left_frame.pack_propagate(False)

        # 搜索和操作按钮区
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_type)  # 输入时实时搜索节点
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind('<Return>', self.on_search_enter)  # 回车触发增强搜索

        ttk.Label(left_frame, text="关键词列表", font=("微软雅黑", 14, "bold")).pack(pady=5)

        # 节点列表框
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.node_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("微软雅黑", 12))
        self.node_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.node_listbox.yview)
        self.node_listbox.bind('<<ListboxSelect>>', self.on_node_select)
        self.node_listbox.bind('<Double-1>', self.on_node_double_click)

        # 节点操作按钮
        node_btn_frame = ttk.Frame(left_frame)
        node_btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(node_btn_frame, text="添加关键词", command=self.add_node).pack(side=tk.LEFT, padx=5)
        ttk.Button(node_btn_frame, text="删除关键词", command=self.delete_node).pack(side=tk.LEFT, padx=5)
        ttk.Button(node_btn_frame, text="重新载入", command=self.reload_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(node_btn_frame, text="切换专辑", command=self.init_input_frame).pack(side=tk.LEFT, padx=5)

        # 中间边关系区域
        middle_frame = ttk.Frame(self.main_frame, width=500)
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5)
        middle_frame.pack_propagate(False)

        # 节点详情
        node_detail_frame = ttk.LabelFrame(middle_frame, text="关键词详情", padding="10")
        node_detail_frame.pack(fill=tk.X, pady=5)

        ttk.Label(node_detail_frame, text="名称:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(
            node_detail_frame,
            textvariable=self.name_var,
            width=60,
            font=("微软雅黑", 12)
        )
        self.name_entry.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(node_detail_frame, text="描述:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.desc_text = tk.Text(
            node_detail_frame,
            width=50,
            height=3,
            font=("微软雅黑", 12),
            wrap=tk.WORD
        )
        self.desc_text.grid(row=1, column=1, sticky=tk.W + tk.E, pady=5)
        node_detail_frame.columnconfigure(1, weight=1)
        self.desc_text.bind("<Return>", lambda event: self.save_node() or "break")

        # 边详情
        edge_frame = ttk.LabelFrame(middle_frame, text="关键词关系", padding="10")
        edge_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 左右两部分布局
        left_relation_frame = ttk.Frame(edge_frame, width=250)
        left_relation_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        right_relation_frame = ttk.Frame(edge_frame, width=250)
        right_relation_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # 左侧：上级节点、本节点、下级节点
        # 上级节点（高度6行）
        parent_frame = ttk.Frame(left_relation_frame)
        parent_frame.pack(fill=tk.X, pady=5)

        # 标题和按钮在同一行
        parent_title_frame = ttk.Frame(parent_frame)
        parent_title_frame.pack(fill=tk.X, anchor=tk.W)  # 左对齐
        ttk.Label(parent_title_frame, text="上级关键词:", font=("微软雅黑", 12)).pack(side=tk.LEFT, padx=5)

        # 上级节点按钮（移到标题右侧）
        ttk.Button(
            parent_title_frame,
            text="+",
            command=self.add_parent,
            width=3
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            parent_title_frame,
            text="-",
            command=self.delete_parent,
            width=3
        ).pack(side=tk.LEFT, padx=2)

        # 上级节点带滚动条
        parent_list_frame = ttk.Frame(parent_frame)
        parent_list_frame.pack(fill=tk.X, pady=3)
        parent_scrollbar = ttk.Scrollbar(parent_list_frame)
        parent_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.parent_listbox = tk.Listbox(
            parent_list_frame,
            height=4,
            font=("微软雅黑", 12),
            width=20,
            yscrollcommand=parent_scrollbar.set
        )
        self.parent_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        parent_scrollbar.config(command=self.parent_listbox.yview)
        self.parent_listbox.bind('<Double-1>', self.on_relation_node_click)

        # 本节点显示
        current_node_frame = ttk.Frame(left_relation_frame, relief=tk.RAISED, padding=5)
        current_node_frame.pack(fill=tk.X, pady=10)
        ttk.Label(current_node_frame, text="本关键词:", font=("微软雅黑", 12)).pack(anchor=tk.W)
        self.current_node_label = ttk.Label(
            current_node_frame,
            text="",
            font=("微软雅黑", 14, "bold"),
            wraplength=200
        )
        self.current_node_label.pack(fill=tk.X, pady=5)

        # 下级节点
        child_frame = ttk.Frame(left_relation_frame)
        child_frame.pack(fill=tk.X, pady=5)

        # 标题和按钮在同一行
        child_title_frame = ttk.Frame(child_frame)
        child_title_frame.pack(fill=tk.X, anchor=tk.W)  # 左对齐
        ttk.Label(child_title_frame, text="下级关键词:", font=("微软雅黑", 12)).pack(side=tk.LEFT, padx=5)

        # 下级节点按钮（移到标题右侧）
        ttk.Button(
            child_title_frame,
            text="+",
            command=self.add_child,
            width=3
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            child_title_frame,
            text="-",
            command=self.delete_child,
            width=3
        ).pack(side=tk.LEFT, padx=2)

        # 下级节点带滚动条
        child_list_frame = ttk.Frame(child_frame)
        child_list_frame.pack(fill=tk.X, pady=3)
        child_scrollbar = ttk.Scrollbar(child_list_frame)
        child_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.child_listbox = tk.Listbox(
            child_list_frame,
            height=19,
            font=("微软雅黑", 12),
            width=20,
            yscrollcommand=child_scrollbar.set
        )
        self.child_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        child_scrollbar.config(command=self.child_listbox.yview)
        self.child_listbox.bind('<Double-1>', self.on_relation_node_click)

        # 右侧：同级节点（带滚动条）
        sibling_frame = ttk.Frame(right_relation_frame)
        sibling_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Label(sibling_frame, text="同级关键词:", font=("微软雅黑", 12)).pack(anchor=tk.W)

        # 同级节点带滚动条
        sibling_list_frame = ttk.Frame(sibling_frame)
        sibling_list_frame.pack(fill=tk.BOTH, expand=True, pady=3)

        sibling_yscroll = ttk.Scrollbar(sibling_list_frame)
        sibling_yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        sibling_xscroll = ttk.Scrollbar(sibling_list_frame, orient=tk.HORIZONTAL)
        sibling_xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.sibling_listbox = tk.Listbox(
            sibling_list_frame,
            font=("微软雅黑", 12),
            width=25,
            yscrollcommand=sibling_yscroll.set,
            xscrollcommand=sibling_xscroll.set
        )
        self.sibling_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sibling_listbox.bind('<Double-1>', self.on_relation_node_click)

        sibling_yscroll.config(command=self.sibling_listbox.yview)
        sibling_xscroll.config(command=self.sibling_listbox.xview)

        # 右侧相关音频区域
        right_frame = ttk.Frame(self.main_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        right_frame.pack_propagate(False)

        # 相关音频
        audio_frame = ttk.LabelFrame(right_frame, text="相关音频", padding="10")
        audio_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 音频列表
        audio_list_frame = ttk.Frame(audio_frame)
        audio_list_frame.pack(fill=tk.BOTH, expand=True)

        # 横向滚动条
        xscrollbar = ttk.Scrollbar(audio_list_frame, orient=tk.HORIZONTAL)
        xscrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # 纵向滚动条
        yscrollbar = ttk.Scrollbar(audio_list_frame)
        yscrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 音频列表框
        self.audio_listbox = tk.Listbox(
            audio_list_frame,
            yscrollcommand=yscrollbar.set,
            xscrollcommand=xscrollbar.set,
            font=('微软雅黑', 12),
            height=15,
            width=30,
            selectmode=tk.EXTENDED  # 启用多选模式
        )
        self.audio_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.audio_listbox.bind('<Double-1>', self.play_audio_and_edit)  # 双击播放并编辑标注
        self.audio_listbox.bind('<<ListboxSelect>>', self.on_audio_select)  # 选中音频时提取关键词
        self.audio_listbox.bind('<Button-3>', self.show_audio_context_menu)  # 绑定右键菜单事件

        # 配置滚动条
        yscrollbar.config(command=self.audio_listbox.yview)
        xscrollbar.config(command=self.audio_listbox.xview)

        # 状态栏
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_status(self, message):
        self.status_var.set(message)

    def init_system_database(self):
        try:
            # 连接数据库 - 使用可读写模式
            self.system_db_conn = sqlite3.connect(f"file:{self.system_db_path}?mode=rwc", uri=True)
            cursor = self.system_db_conn.cursor()

            # 创建必要的表（如果不存在）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                node TEXT PRIMARY KEY,
                description TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS edges (
                parent_node TEXT,
                child_node TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (parent_node, child_node),
                FOREIGN KEY (parent_node) REFERENCES nodes (node),
                FOREIGN KEY (child_node) REFERENCES nodes (node)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            self.system_db_conn.commit()

        except Exception as e:
            messagebox.showerror("数据库错误", f"初始化系统数据库失败: {str(e)}")
            if self.system_db_conn:
                self.system_db_conn.close()
                self.system_db_conn = None

    def reload_data(self):
        try:
            # 重置数据
            self.nodes = {}
            self.edges = []
            self.audio_info = []

            # 清空界面
            self.node_listbox.delete(0, tk.END)
            self.parent_listbox.delete(0, tk.END)
            self.child_listbox.delete(0, tk.END)
            self.sibling_listbox.delete(0, tk.END)  # 清空同级节点列表
            self.audio_listbox.delete(0, tk.END)
            self.name_var.set("")
            self.desc_text.delete(1.0, tk.END)
            self.current_node_label.config(text="")
            self.current_node_name = None

            # 重新加载数据
            self.load_data()
            self.load_audio_data()
            self.update_status("重新载入完成 - 所有数据已更新")
        except Exception as e:
            messagebox.showerror("错误", f"重新载入失败: {str(e)}")
            self.update_status(f"重新载入失败: {str(e)}")

    def load_data(self):
        try:
            if self.system_db_conn:
                cursor = self.system_db_conn.cursor()
                
                # 加载节点
                cursor.execute("SELECT node, description FROM nodes")
                rows = cursor.fetchall()
                for row in rows:
                    node_name, description = row
                    self.nodes[node_name] = {
                        'name': node_name,
                        'description': description
                    }
                    self.node_listbox.insert(tk.END, node_name)

                # 加载边
                cursor.execute("SELECT parent_node, child_node FROM edges")
                rows = cursor.fetchall()
                for row in rows:
                    parent_node, child_node = row
                    self.edges.append({
                        'source': parent_node,
                        'target': child_node
                    })

                self.update_status(f"加载完成 - 关键词: {len(self.nodes)}, 关系: {len(self.edges)}")

        except Exception as e:
            messagebox.showerror("错误", f"加载数据失败: {str(e)}")
            self.update_status(f"加载失败: {str(e)}")

    def load_audio_data(self):
        try:
            if self.album_db_conn:
                cursor = self.album_db_conn.cursor()
                # 修改SQL查询，添加获取url字段
                cursor.execute("SELECT id, filename, duration, title, annotation, url FROM episodes ORDER BY id")
                rows = cursor.fetchall()
                
                self.audio_info = []
                for row in rows:
                    id, filename, duration, title, annotation, url = row
                    self.audio_info.append((id, filename, duration, title, annotation, url))
                
                # 调整排序：未标注的内容（标注内容和文件名完全相同）排在前面
                # 未标注定义为标注内容和文件名完全相同的情况
                self.audio_info.sort(key=lambda x: 0 if (x[4] and x[4] == x[1]) else 1)
                
                # 清空列表并重新插入排序后的数据
                self.audio_listbox.delete(0, tk.END)
                
                for item in self.audio_info:
                    id, filename, duration, title, annotation, url = item
                    # 使用标注内容而不是标题显示在列表中
                    display_text = annotation if annotation else title
                    
                    # 如果有标注内容，处理关键词突出显示
                    if annotation:
                        display_text = self.format_annotated_text(annotation)
                    
                    self.audio_listbox.insert(tk.END, display_text)

                self.update_status(f"音频数据加载完成 - 共 {len(self.audio_info)} 条记录")
        except Exception as e:
            messagebox.showerror("错误", f"加载音频数据失败: {str(e)}")
            self.update_status(f"音频加载失败: {str(e)}")

    def format_annotated_text(self, annotation):
        """格式化标注文本，突出显示关键词"""
        if not annotation or not self.nodes:
            return annotation
        
        formatted_text = annotation
        marked_positions = []  # 记录已经被标记的位置范围
        
        # 将节点名称按长度排序，优先匹配较长的关键词
        sorted_nodes = sorted(self.nodes.keys(), key=len, reverse=True)
        
        # 检查每个关键词是否在标注中出现
        for node_name in sorted_nodes:
            start_pos = 0
            while True:
                start_pos = formatted_text.find(node_name, start_pos)
                if start_pos == -1:
                    break
                
                end_pos = start_pos + len(node_name)
                
                # 检查该位置是否已经被标记过
                overlap = False
                for (marked_start, marked_end) in marked_positions:
                    if not (end_pos <= marked_start or start_pos >= marked_end):
                        overlap = True
                        break
                
                if not overlap:
                    # 在关键词前后添加特殊标记来表示加粗
                    # 使用【】包围关键词以突出显示
                    formatted_text = formatted_text[:start_pos] + f"【{node_name}】" + formatted_text[end_pos:]
                    # 更新标记位置（注意替换后文本长度变化）
                    new_end_pos = start_pos + len(f"【{node_name}】")
                    marked_positions.append((start_pos, new_end_pos))
                    # 跳过已标记的部分继续查找
                    start_pos = new_end_pos
                else:
                    # 如果位置已被标记，跳过这个位置
                    start_pos += 1
        
        return formatted_text

    def save_node(self):
        if not self.current_node_name:
            return

        old_data = {
            'name': self.current_node_name,
            'description': self.nodes[self.current_node_name]['description']
        }

        new_name = self.name_var.get()
        new_description = self.desc_text.get(1.0, tk.END).strip()

        if old_data['name'] == new_name and old_data['description'] == new_description:
            return

        try:
            if self.system_db_conn:
                cursor = self.system_db_conn.cursor()
                
                # 如果节点名称发生变化，需要先更新边表
                if old_data['name'] != new_name:
                    # 更新边表中的源节点
                    cursor.execute(
                        "UPDATE edges SET parent_node = ? WHERE parent_node = ?",
                        (new_name, old_data['name'])
                    )
                    # 更新边表中的目标节点
                    cursor.execute(
                        "UPDATE edges SET child_node = ? WHERE child_node = ?",
                        (new_name, old_data['name'])
                    )
                    # 删除旧节点
                    cursor.execute("DELETE FROM nodes WHERE node = ?", (old_data['name'],))
                    # 从本地数据中删除旧节点
                    del self.nodes[old_data['name']]
                
                # 插入或更新新节点
                cursor.execute(
                    "INSERT OR REPLACE INTO nodes (node, description) VALUES (?, ?)",
                    (new_name, new_description)
                )
                
                self.system_db_conn.commit()
                
                # 更新本地数据
                self.nodes[new_name] = {
                    'name': new_name,
                    'description': new_description
                }
                
                # 更新界面
                for i in range(self.node_listbox.size()):
                    if self.node_listbox.get(i) == old_data['name']:
                        self.node_listbox.delete(i)
                        self.node_listbox.insert(i, new_name)
                        self.node_listbox.selection_set(i)
                        break
                
                self.current_node_name = new_name
                self.current_node_label.config(text=new_name)
                self.update_edge_lists(new_name)  # 更新所有关系列表
                self.update_status(f"关键词 '{new_name}' 已更新")
        except Exception as e:
            messagebox.showerror("错误", f"保存关键词失败: {str(e)}")
            self.update_status(f"保存失败: {str(e)}")
            if self.system_db_conn:
                self.system_db_conn.rollback()

    def add_node(self):
        name = simpledialog.askstring("添加关键词", "请输入关键词名称:")
        if name:
            if name in self.nodes:
                messagebox.showwarning("警告", f"关键词 '{name}' 已存在")
                return

            # 使用自定义对话框获取描述
            description = self.show_custom_description_dialog() or ""

            try:
                if self.system_db_conn:
                    cursor = self.system_db_conn.cursor()
                    cursor.execute(
                        "INSERT INTO nodes (node, description) VALUES (?, ?)",
                        (name, description)
                    )
                    self.system_db_conn.commit()
                    
                    # 更新本地数据
                    self.nodes[name] = {
                        'name': name,
                        'description': description
                    }
                    self.node_listbox.insert(tk.END, name)
                    
                    self.update_status(f"添加关键词: {name}")
            except Exception as e:
                messagebox.showerror("错误", f"添加关键词失败: {str(e)}")
                self.update_status(f"添加失败: {str(e)}")
                if self.system_db_conn:
                    self.system_db_conn.rollback()

    def show_custom_description_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("添加关键词描述")
        dialog.geometry("800x150")  # 宽度足够容纳40汉字（约800像素）
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="请输入关键词描述:", font=("微软雅黑", 12)).pack(pady=10, padx=10, anchor=tk.W)

        input_var = tk.StringVar()
        input_entry = ttk.Entry(
            dialog,
            textvariable=input_var,
            font=("微软雅黑", 12),
            width=60  # 约60字符宽度（40汉字足够）
        )
        input_entry.pack(pady=5, padx=10, fill=tk.X, expand=True)
        input_entry.focus_set()

        result = [None]

        def on_ok():
            result[0] = input_var.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=10)

        dialog.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: on_cancel())

        self.root.wait_window(dialog)
        return result[0]

    def delete_node(self):
        selection = self.node_listbox.curselection()
        if selection:
            index = selection[0]
            node_name = self.node_listbox.get(index)

            if node_name and messagebox.askyesno("确认", f"确定要删除关键词 '{node_name}' 吗？"):
                try:
                    if self.system_db_conn:
                        cursor = self.system_db_conn.cursor()
                        
                        # 删除相关的边
                        cursor.execute("DELETE FROM edges WHERE parent_node = ? OR child_node = ?", (node_name, node_name))
                        
                        # 删除节点
                        cursor.execute("DELETE FROM nodes WHERE node = ?", (node_name,))
                        
                        self.system_db_conn.commit()
                        
                        # 更新本地数据
                        self.edges = [e for e in self.edges if e['source'] != node_name and e['target'] != node_name]
                        if node_name in self.nodes:
                            del self.nodes[node_name]
                        self.node_listbox.delete(index)
                        
                        # 清空相关界面
                        if self.current_node_name == node_name:
                            self.name_var.set("")
                            self.desc_text.delete(1.0, tk.END)
                            self.current_node_label.config(text="")
                            self.parent_listbox.delete(0, tk.END)
                            self.child_listbox.delete(0, tk.END)
                            self.sibling_listbox.delete(0, tk.END)
                            self.current_node_name = None
                        
                        self.update_status(f"删除关键词: {node_name}")
                except Exception as e:
                    messagebox.showerror("错误", f"删除关键词失败: {str(e)}")
                    self.update_status(f"删除失败: {str(e)}")
                    if self.system_db_conn:
                        self.system_db_conn.rollback()

    def add_parent(self):
        if not self.current_node_name:
            messagebox.showwarning("警告", "请先选择一个关键词")
            return

        parent_name = simpledialog.askstring("添加上级关键词", "请输入上级关键词名称:")

        if parent_name:
            # 检查上级节点是否存在
            if parent_name not in self.nodes:
                if messagebox.askyesno("关键词不存在", f"关键词 '{parent_name}' 不存在，是否新建？"):
                    description = self.show_custom_description_dialog() or ""
                    try:
                        if self.system_db_conn:
                            cursor = self.system_db_conn.cursor()
                            cursor.execute(
                                "INSERT INTO nodes (node, description) VALUES (?, ?)",
                                (parent_name, description)
                            )
                            self.system_db_conn.commit()
                            
                            # 更新本地数据
                            self.nodes[parent_name] = {
                                'name': parent_name,
                                'description': description
                            }
                            self.node_listbox.insert(tk.END, parent_name)
                            self.update_status(f"新建关键词: {parent_name}")
                    except Exception as e:
                        messagebox.showerror("错误", f"添加关键词失败: {str(e)}")
                        self.update_status(f"添加失败: {str(e)}")
                        if self.system_db_conn:
                            self.system_db_conn.rollback()
                        return
                else:
                    return

            if parent_name == self.current_node_name:
                messagebox.showwarning("警告", "关键词不能是自己的上级")
                return

            # 检查关系是否已存在
            for edge in self.edges:
                if edge['source'] == parent_name and edge['target'] == self.current_node_name:
                    messagebox.showwarning("警告", "该上级关系已存在")
                    return

            try:
                if self.system_db_conn:
                    cursor = self.system_db_conn.cursor()
                    cursor.execute(
                        "INSERT INTO edges (parent_node, child_node) VALUES (?, ?)",
                        (parent_name, self.current_node_name)
                    )
                    self.system_db_conn.commit()
                    
                    # 更新本地数据
                    self.edges.append({'source': parent_name, 'target': self.current_node_name})
                    self.parent_listbox.insert(tk.END, parent_name)
                    self.update_edge_lists(self.current_node_name)  # 更新同级节点
                    
                    self.update_status(f"添加上级关系: {parent_name} -> {self.current_node_name}")
            except Exception as e:
                messagebox.showerror("错误", f"添加关系失败: {str(e)}")
                self.update_status(f"添加失败: {str(e)}")
                if self.system_db_conn:
                    self.system_db_conn.rollback()

    def add_child(self):
        if not self.current_node_name:
            messagebox.showwarning("警告", "请先选择一个关键词")
            return

        child_name = simpledialog.askstring("添加下级关键词", "请输入下级关键词名称:")

        if child_name:
            # 检查下级节点是否存在
            if child_name not in self.nodes:
                if messagebox.askyesno("关键词不存在", f"关键词 '{child_name}' 不存在，是否新建？"):
                    description = self.show_custom_description_dialog() or ""
                    try:
                        if self.system_db_conn:
                            cursor = self.system_db_conn.cursor()
                            cursor.execute(
                                "INSERT INTO nodes (node, description) VALUES (?, ?)",
                                (child_name, description)
                            )
                            self.system_db_conn.commit()
                            
                            # 更新本地数据
                            self.nodes[child_name] = {
                                'name': child_name,
                                'description': description
                            }
                            self.node_listbox.insert(tk.END, child_name)
                            self.update_status(f"新建关键词: {child_name}")
                    except Exception as e:
                        messagebox.showerror("错误", f"添加关键词失败: {str(e)}")
                        self.update_status(f"添加失败: {str(e)}")
                        if self.system_db_conn:
                            self.system_db_conn.rollback()
                        return
                else:
                    return

            if child_name == self.current_node_name:
                messagebox.showwarning("警告", "关键词不能是自己的下级")
                return

            # 检查关系是否已存在
            for edge in self.edges:
                if edge['source'] == self.current_node_name and edge['target'] == child_name:
                    messagebox.showwarning("警告", "该下级关系已存在")
                    return

            try:
                if self.system_db_conn:
                    cursor = self.system_db_conn.cursor()
                    cursor.execute(
                        "INSERT INTO edges (parent_node, child_node) VALUES (?, ?)",
                        (self.current_node_name, child_name)
                    )
                    self.system_db_conn.commit()
                    
                    # 更新本地数据
                    self.edges.append({'source': self.current_node_name, 'target': child_name})
                    self.child_listbox.insert(tk.END, child_name)
                    self.update_edge_lists(self.current_node_name)  # 更新同级节点
                    
                    self.update_status(f"添加下级关系: {self.current_node_name} -> {child_name}")
            except Exception as e:
                messagebox.showerror("错误", f"添加关系失败: {str(e)}")
                self.update_status(f"添加失败: {str(e)}")
                if self.system_db_conn:
                    self.system_db_conn.rollback()

    def delete_parent(self):
        if not self.current_node_name:
            messagebox.showwarning("警告", "请先选择一个关键词")
            return

        selection = self.parent_listbox.curselection()
        if selection:
            index = selection[0]
            parent_name = self.parent_listbox.get(index)

            if parent_name and messagebox.askyesno("确认", f"确定要删除上级关系 '{parent_name} -> {self.current_node_name}' 吗？"):
                try:
                    if self.system_db_conn:
                        cursor = self.system_db_conn.cursor()
                        cursor.execute(
                            "DELETE FROM edges WHERE parent_node = ? AND child_node = ?",
                            (parent_name, self.current_node_name)
                        )
                        self.system_db_conn.commit()
                        
                        # 更新本地数据
                        self.edges = [e for e in self.edges if
                                      not (e['source'] == parent_name and e['target'] == self.current_node_name)]
                        self.parent_listbox.delete(index)
                        self.update_edge_lists(self.current_node_name)  # 更新同级节点
                        
                        self.update_status(f"删除上级关系: {parent_name} -> {self.current_node_name}")
                except Exception as e:
                    messagebox.showerror("错误", f"删除关系失败: {str(e)}")
                    self.update_status(f"删除失败: {str(e)}")
                    if self.system_db_conn:
                        self.system_db_conn.rollback()

    def delete_child(self):
        if not self.current_node_name:
            messagebox.showwarning("警告", "请先选择一个关键词")
            return

        selection = self.child_listbox.curselection()
        if selection:
            index = selection[0]
            child_name = self.child_listbox.get(index)

            if child_name and messagebox.askyesno("确认", f"确定要删除下级关系 '{self.current_node_name} -> {child_name}' 吗？"):
                try:
                    if self.system_db_conn:
                        cursor = self.system_db_conn.cursor()
                        cursor.execute(
                            "DELETE FROM edges WHERE parent_node = ? AND child_node = ?",
                            (self.current_node_name, child_name)
                        )
                        self.system_db_conn.commit()
                        
                        # 更新本地数据
                        self.edges = [e for e in self.edges if
                                      not (e['source'] == self.current_node_name and e['target'] == child_name)]
                        self.child_listbox.delete(index)
                        self.update_edge_lists(self.current_node_name)  # 更新同级节点
                        
                        self.update_status(f"删除下级关系: {self.current_node_name} -> {child_name}")
                except Exception as e:
                    messagebox.showerror("错误", f"删除关系失败: {str(e)}")
                    self.update_status(f"删除失败: {str(e)}")
                    if self.system_db_conn:
                        self.system_db_conn.rollback()

    def on_search_type(self, *args):
        search_term = self.search_var.get().strip().lower()
        self.node_listbox.delete(0, tk.END)
        count = 0

        if not search_term:
            for node_name in self.nodes:
                self.node_listbox.insert(tk.END, node_name)
                count += 1
        else:
            exact_match = False
            for node_name, data in self.nodes.items():
                if node_name.lower() == search_term:
                    self.node_listbox.insert(tk.END, node_name)
                    exact_match = True
                    count += 1
                    self.node_listbox.selection_set(0)
                    self.on_node_select(None)
                    break

            if not exact_match:
                for node_name, data in self.nodes.items():
                    if search_term in node_name.lower() or search_term in data['description'].lower():
                        self.node_listbox.insert(tk.END, node_name)
                        count += 1

        self.update_status(f"搜索完成 - 找到 {count} 个匹配关键词")

    def on_search_enter(self, event):
        search_term = self.search_var.get().strip().lower()

        self.node_listbox.delete(0, tk.END)
        node_count = 0

        if search_term:
            for node_name, data in self.nodes.items():
                if (node_name.lower() == search_term or
                        search_term in node_name.lower() or
                        search_term in data['description'].lower()):
                    self.node_listbox.insert(tk.END, node_name)
                    node_count += 1

            self.search_related_audio(search_term)

            if node_count == 0:
                self.current_node_name = None
                self.update_status(f"未找到匹配关键词，使用搜索词搜索音频")
            else:
                self.current_node_name = None
                self.update_status(f"找到 {node_count} 个匹配关键词，同时显示相关音频")

            self.name_var.set("")
            self.desc_text.delete(1.0, tk.END)
            self.current_node_label.config(text="")
            self.parent_listbox.delete(0, tk.END)
            self.child_listbox.delete(0, tk.END)
            self.sibling_listbox.delete(0, tk.END)  # 清空同级节点列表
        else:
            # 当搜索框为空时，恢复完整的关键词列表和音频列表
            for node_name in self.nodes:
                self.node_listbox.insert(tk.END, node_name)
                node_count += 1

            # 加载所有音频数据，恢复音频列表到完整状态
            self.load_audio_data()

            self.current_node_name = None
            self.update_status(f"显示所有关键词 - 共 {node_count} 个")

            self.name_var.set("")
            self.desc_text.delete(1.0, tk.END)
            self.current_node_label.config(text="")
            self.parent_listbox.delete(0, tk.END)
            self.child_listbox.delete(0, tk.END)
            self.sibling_listbox.delete(0, tk.END)  # 清空同级节点列表

        return "break"

    def on_node_select(self, event):
        selection = self.node_listbox.curselection()
        if selection:
            index = selection[0]
            node_name = self.node_listbox.get(index)
            if node_name in self.nodes:
                self.current_node_name = node_name
                self.name_var.set(self.nodes[node_name]['name'])
                self.desc_text.delete(1.0, tk.END)
                self.desc_text.insert(tk.END, self.nodes[node_name]['description'])
                self.current_node_label.config(text=node_name)
                self.update_edge_lists(node_name)  # 更新所有关系列表，包括同级
                self.search_related_audio(node_name)

    def on_node_double_click(self, event):
        self.on_node_select(event)

    def on_relation_node_click(self, event):
        widget = event.widget
        if widget in (self.parent_listbox, self.child_listbox, self.sibling_listbox):
            selection = widget.curselection()
            if selection:
                index = selection[0]
                node_name = widget.get(index)
                if node_name in self.nodes:
                    self.node_listbox.selection_clear(0, tk.END)

                    found_index = -1
                    for i in range(self.node_listbox.size()):
                        if self.node_listbox.get(i) == node_name:
                            found_index = i
                            break

                    if found_index == -1:
                        found_index = self.node_listbox.size()
                        self.node_listbox.insert(tk.END, node_name)

                    self.node_listbox.selection_set(found_index)
                    self.node_listbox.see(found_index)

                    self.current_node_name = node_name
                    self.on_node_select(None)

    def update_edge_lists(self, node_name):
        self.parent_listbox.delete(0, tk.END)
        self.child_listbox.delete(0, tk.END)
        self.sibling_listbox.delete(0, tk.END)

        # 获取上级节点
        parents = []
        for edge in self.edges:
            if edge['target'] == node_name:
                parent_name = edge['source']
                parents.append(parent_name)
                self.parent_listbox.insert(tk.END, parent_name)

        # 获取下级节点
        for edge in self.edges:
            if edge['source'] == node_name:
                self.child_listbox.insert(tk.END, edge['target'])

        # 获取同级节点
        siblings = set()  # 使用集合去重

        # 1. 拥有相同父节点的节点（除了自己）
        for parent_name in parents:
            for edge in self.edges:
                if edge['source'] == parent_name and edge['target'] != node_name:
                    sibling_name = edge['target']
                    siblings.add(sibling_name)

        # 2. 拥有相同子节点的节点
        # 先获取当前节点的所有子节点
        current_children = [edge['target'] for edge in self.edges if edge['source'] == node_name]

        # 查找所有也拥有这些子节点的其他节点
        for child_name in current_children:
            for edge in self.edges:
                if edge['target'] == child_name and edge['source'] != node_name:
                    sibling_name = edge['source']
                    siblings.add(sibling_name)

        # 转换为列表并添加到界面
        for sibling_name in siblings:
            self.sibling_listbox.insert(tk.END, sibling_name)

    def search_related_audio(self, keyword):
        self.audio_listbox.delete(0, tk.END)
        self.audio_info = []

        if not keyword:
            self.update_status("请输入搜索词或选择一个关键词查看相关音频")
            return

        keyword_lower = keyword.lower()
        try:
            if self.album_db_conn:
                cursor = self.album_db_conn.cursor()
                cursor.execute("SELECT id, filename, duration, title, annotation, url FROM episodes ORDER BY id")
                rows = cursor.fetchall()
                
                for row in rows:
                    id, filename, duration, title, annotation, url = row
                    if annotation and keyword_lower in annotation.lower():
                        # 存储url信息
                        self.audio_info.append((id, filename, duration, title, annotation, url))
        except Exception as e:
            messagebox.showerror("错误", f"搜索音频失败: {str(e)}")
            self.update_status(f"搜索失败: {str(e)}")
            return

        # 按标注内容（字符串）倒序排列
        self.audio_info.sort(key=lambda x: x[4].lower(), reverse=True)

        for item in self.audio_info:
            # 使用标注内容而不是标题显示在列表中
            display_text = item[4] if item[4] else item[3]
            self.audio_listbox.insert(tk.END, display_text)

        node_count = len(self.nodes)
        edge_count = len(self.edges)
        self.status_var.set(f"关键词: {node_count}, 关系: {edge_count} - 找到 {len(self.audio_info)} 个相关音频")

    def play_audio(self, event):
        selection = self.audio_listbox.curselection()
        if selection:
            index = selection[0]
            try:
                if 0 <= index < len(self.audio_info):
                    # 获取包括url在内的音频信息
                    id, filename, duration, title, annotation, url = self.audio_info[index]
                    if url:
                        try:
                            # 使用url而不是本地文件
                            webbrowser.open(url)
                            self.update_status(f"正在播放音频: {title}")
                        except Exception as e:
                            messagebox.showerror("错误", f"播放音频失败: {str(e)}")
                    else:
                        # 如果没有url，才尝试使用本地文件
                        if filename:
                            audio_file = os.path.join(self.current_album_path, filename)
                            if os.path.exists(audio_file):
                                try:
                                    subprocess.run(['start', '', audio_file], shell=True, check=True)
                                    self.update_status(f"正在播放本地音频: {filename}")
                                except Exception as e:
                                    messagebox.showerror("错误", f"播放音频失败: {str(e)}")
                            else:
                                messagebox.showwarning("警告", f"音频文件不存在: {audio_file}")
                        else:
                            messagebox.showwarning("警告", "未找到对应的音频文件名或播放地址")
                else:
                    messagebox.showwarning("警告", "无效的音频选择")
            except Exception as e:
                messagebox.showerror("错误", f"获取音频信息失败: {str(e)}")

    def play_audio_and_edit(self, event):
        """双击音频时，同时播放和打开编辑窗口"""
        # 先播放音频
        self.play_audio(event)
        
        # 然后打开标注编辑窗口
        selection = self.audio_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.audio_info):
                # 获取包括url在内的音频信息
                id, filename, duration, title, old_annotation, url = self.audio_info[index]
                
                new_annotation = self.show_custom_input_dialog(
                    title="编辑标注",
                    prompt="请输入新的标注内容:",
                    initial_value=old_annotation
                )
                
                if new_annotation is not None and new_annotation != old_annotation:
                    # 更新数据库
                    try:
                        if self.album_db_conn:
                            cursor = self.album_db_conn.cursor()
                            cursor.execute(
                                "UPDATE episodes SET annotation = ?, updated = CURRENT_TIMESTAMP WHERE id = ?",
                                (new_annotation, id)
                            )
                            self.album_db_conn.commit()
                              
                            # 更新本地数据，保持url信息
                            self.audio_info[index] = (id, filename, duration, title, new_annotation, url)
                            self.audio_listbox.delete(index)
                            # 更新列表显示为新的标注内容
                            self.audio_listbox.insert(index, new_annotation)
                              
                            self.update_status(f"已更新音频标注: {title}")
                    except Exception as e:
                        messagebox.showerror("错误", f"保存标注失败: {str(e)}")
                        self.update_status(f"保存失败: {str(e)}")
                        if self.album_db_conn:
                            self.album_db_conn.rollback()

    def on_audio_select(self, event):
        """选中音频时提取关键词（支持多选）"""
        selection = self.audio_listbox.curselection()
        if selection:
            try:
                # 合并所有选中标注的关键词
                all_keywords = set()
                
                for index in selection:
                    if 0 <= index < len(self.audio_info):
                        # 获取包括url在内的音频信息
                        id, filename, duration, title, annotation, url = self.audio_info[index]
                        
                        if annotation:
                            # 提取关键词并添加到集合中（自动去重）
                            keywords = self.extract_keywords(annotation)
                            all_keywords.update(keywords)
                
                # 如果有提取到关键词，更新关键词列表
                if all_keywords:
                    self.update_keyword_list_for_audio(list(all_keywords))
                else:
                    # 如果没有关键词，清空列表并显示提示
                    self.node_listbox.delete(0, tk.END)
                    self.node_listbox.insert(tk.END, "(选中的标注中没有包含任何关键词)")
                    self.node_listbox.configure(state='disabled')
            except Exception as e:
                self.update_status(f"提取关键词失败: {str(e)}")

    def extract_keywords(self, text):
        """从文本中提取关键词"""
        keywords = []
        if not text or not self.nodes:
            return keywords
            
        # 转换为小写以便不区分大小写匹配
        text_lower = text.lower()
        
        # 遍历所有现有关键词，检查是否在文本中出现
        for node_name in self.nodes:
            # 宽松匹配：只要关键词在文本中出现（包含）就算匹配成功
            node_lower = node_name.lower()
            if node_lower in text_lower:
                keywords.append(node_name)
        
        return keywords

    def update_keyword_list_for_audio(self, keywords):
        """更新关键词列表，只显示当前音频标注中包含的关键词"""
        # 保存当前选中的关键词
        current_selection = self.node_listbox.curselection()
        current_selected_keyword = None
        if current_selection:
            current_selected_keyword = self.node_listbox.get(current_selection[0])
            
        # 清空关键词列表
        self.node_listbox.delete(0, tk.END)
        
        # 只添加当前音频标注中包含的关键词
        if keywords:
            for keyword in keywords:
                self.node_listbox.insert(tk.END, keyword)
            self.node_listbox.configure(state='normal')  # 启用列表
        else:
            # 如果没有匹配的关键词，显示提示信息
            self.node_listbox.insert(tk.END, "(当前标注中没有包含任何关键词)")
            self.node_listbox.configure(state='disabled')  # 禁用列表
                    
        # 恢复之前选中的关键词
        if current_selected_keyword:
            for i in range(self.node_listbox.size()):
                if self.node_listbox.get(i) == current_selected_keyword:
                    self.node_listbox.selection_set(i)
                    self.node_listbox.see(i)
                    break

    def show_audio_context_menu(self, event):
        """显示音频列表的右键菜单"""
        selection = self.audio_listbox.curselection()
        if not selection:
            return
            
        # 创建右键菜单
        context_menu = tk.Menu(self.root, tearoff=0)
        
        # 添加编辑单个标注的菜单项
        if len(selection) == 1:
            context_menu.add_command(label="编辑标注", command=self.edit_single_annotation)
        
        # 添加批量操作的菜单项
        if len(selection) >= 1:
            context_menu.add_command(label="批量增加标注", command=self.batch_add_annotation)
        
        # 添加全选菜单项
        context_menu.add_separator()
        context_menu.add_command(label="全选", command=self.select_all_audio)
        context_menu.add_command(label="取消选择", command=self.deselect_all_audio)
        
        # 在鼠标位置显示菜单
        context_menu.post(event.x_root, event.y_root)
    
    def select_all_audio(self):
        """全选音频列表"""
        self.audio_listbox.selection_set(0, tk.END)
        # 触发选择事件
        self.on_audio_select(None)
    
    def deselect_all_audio(self):
        """取消选择所有音频"""
        self.audio_listbox.selection_clear(0, tk.END)
    
    def edit_single_annotation(self):
        """编辑单个音频标注"""
        selection = self.audio_listbox.curselection()
        if not selection or len(selection) != 1:
            return

        index = selection[0]
        if 0 <= index < len(self.audio_info):
            # 获取包括url在内的音频信息
            id, filename, duration, title, old_annotation, url = self.audio_info[index]

            new_annotation = self.show_custom_input_dialog(
                title="编辑标注",
                prompt="请输入新的标注内容:",
                initial_value=old_annotation
            )

            if new_annotation is not None and new_annotation != old_annotation:
                # 更新数据库
                try:
                    if self.album_db_conn:
                        cursor = self.album_db_conn.cursor()
                        cursor.execute(
                            "UPDATE episodes SET annotation = ?, updated = CURRENT_TIMESTAMP WHERE id = ?",
                            (new_annotation, id)
                        )
                        self.album_db_conn.commit()
                          
                        # 更新本地数据，保持url信息
                        self.audio_info[index] = (id, filename, duration, title, new_annotation, url)
                        self.audio_listbox.delete(index)
                        # 更新列表显示为新的标注内容
                        self.audio_listbox.insert(index, new_annotation)
                          
                        self.update_status(f"已更新音频标注: {title}")
                except Exception as e:
                    messagebox.showerror("错误", f"保存标注失败: {str(e)}")
                    self.update_status(f"保存失败: {str(e)}")
                    if self.album_db_conn:
                        self.album_db_conn.rollback()
    
    def batch_add_annotation(self):
        """批量增加标注内容到选中标注的末尾"""
        selection = self.audio_listbox.curselection()
        if not selection:
            return
        
        # 显示输入框获取要添加的内容
        content_to_add = self.show_custom_input_dialog(
            title="批量增加标注",
            prompt="请输入要添加到所有选中标注末尾的内容:",
            initial_value=""
        )
        
        if content_to_add is None or content_to_add.strip() == "":
            return
        
        # 处理所有选中的音频
        updated_count = 0
        try:
            if self.album_db_conn:
                cursor = self.album_db_conn.cursor()
                
                for index in selection:
                    if 0 <= index < len(self.audio_info):
                        # 获取包括url在内的音频信息
                        id, filename, duration, title, old_annotation, url = self.audio_info[index]
                        
                        # 在原有标注末尾添加新内容
                        new_annotation = old_annotation + content_to_add
                        
                        # 更新数据库
                        cursor.execute(
                            "UPDATE episodes SET annotation = ?, updated = CURRENT_TIMESTAMP WHERE id = ?",
                            (new_annotation, id)
                        )
                        
                        # 更新本地数据，保持url信息
                        self.audio_info[index] = (id, filename, duration, title, new_annotation, url)
                        self.audio_listbox.delete(index)
                        # 更新列表显示为新的标注内容
                        self.audio_listbox.insert(index, new_annotation)
                        
                        updated_count += 1
                
                self.album_db_conn.commit()
                self.update_status(f"已批量更新 {updated_count} 个音频标注")
        except Exception as e:
            messagebox.showerror("错误", f"批量保存标注失败: {str(e)}")
            self.update_status(f"批量保存失败: {str(e)}")
            if self.album_db_conn:
                self.album_db_conn.rollback()

    def show_custom_input_dialog(self, title, prompt, initial_value=""):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("1200x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=prompt, font=("微软雅黑", 12)).pack(pady=10, padx=10, anchor=tk.W)

        input_var = tk.StringVar(value=initial_value)
        input_entry = ttk.Entry(
            dialog,
            textvariable=input_var,
            font=("微软雅黑", 12),
            width=80
        )
        input_entry.pack(pady=5, padx=10, fill=tk.X, expand=True)
        input_entry.focus_set()

        result = [None]

        def on_ok():
            result[0] = input_var.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=10)

        dialog.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: on_cancel())

        self.root.wait_window(dialog)

        return result[0]

    def __del__(self):
        if hasattr(self, 'system_db_conn') and self.system_db_conn:
            self.system_db_conn.close()
        if hasattr(self, 'album_db_conn') and self.album_db_conn:
            self.album_db_conn.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = PodcastAnnotationManager(root)
    root.mainloop()