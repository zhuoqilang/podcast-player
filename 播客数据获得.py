import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
import requests
import xml.etree.ElementTree as ET
import json
import os
import sys
import re
import sqlite3
from datetime import timedelta, datetime
from urllib.parse import urlparse
import time


class PodcastDataGetter:
    def __init__(self, root):
        self.root = root
        self.root.title("播客数据获得")
        self.root.geometry("700x500")
        self.root.minsize(600, 400)

        # 设置中文字体
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("SimHei", 10))
        self.style.configure("TButton", font=("SimHei", 10))
        self.style.configure("TEntry", font=("SimHei", 10))
        self.style.configure("Treeview", font=("SimHei", 10))

        # 文件路径 - 适配PyInstaller打包
        if getattr(sys, 'frozen', False):
            # 打包为可执行文件时
            if hasattr(sys, '_MEIPASS'):
                # _MEIPASS是PyInstaller创建的临时文件夹
                # 对于onefile模式，使用可执行文件所在目录
                self.program_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                self.program_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # 脚本模式
            self.program_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.albums_dir = os.path.join(self.program_dir, "albums")
        # 确保albums目录存在
        os.makedirs(self.albums_dir, exist_ok=True)

        # 日志文件路径
        self.log_file_path = os.path.join(self.program_dir, "podcast_download_log.txt")
        
        # 数据存储
        self.current_album_id = ""  # 当前专辑ID
        self.system_db_conn = None  # 系统全局数据库连接
        self.album_db_conn = None  # 当前专辑数据库连接
        self.system_db_path = os.path.join(self.program_dir, "podcast_system.db")  # 全局数据库路径
        
        # 多专辑处理标志
        self.batch_processing = False

        # 初始化
        self.init_system_database()

        # 显示主界面
        self.show_main_interface()

    def scan_and_import_albums(self):
        """扫描albums文件夹并将所有专辑信息导入到系统数据库"""
        
        if not os.path.exists(self.albums_dir):
            messagebox.showwarning("警告", f"找不到专辑目录: {self.albums_dir}")
            return
        
        try:
            # 获取albums目录下的所有子目录
            imported_count = 0
            folders = [f for f in os.listdir(self.albums_dir) if os.path.isdir(os.path.join(self.albums_dir, f))]
            
            for folder in folders:
                # 检查是否是专辑文件夹（以"album_"开头）
                if folder.startswith("album_"):
                    album_id = folder[len("album_"):]
                    album_folder = os.path.join(self.albums_dir, folder)
                    album_db_path = os.path.join(album_folder, f"album_{album_id}.db")
                    
                    # 检查专辑数据库是否存在
                    if os.path.exists(album_db_path):
                        # 尝试从专辑数据库中获取专辑名称
                        album_title = f"专辑 {album_id}"
                        
                        # 连接专辑数据库
                        try:
                            album_conn = sqlite3.connect(album_db_path)
                            album_cursor = album_conn.cursor()
                            
                            # 尝试从album_info表获取专辑标题
                            album_cursor.execute("SELECT title FROM album_info LIMIT 1")
                            result = album_cursor.fetchone()
                            if result:
                                album_title = result[0]
                            
                            album_conn.close()
                        except Exception as e:
                            print(f"读取专辑 {album_id} 信息错误: {str(e)}")
                            
                        # 更新系统数据库
                        if self.system_db_conn:
                            cursor = self.system_db_conn.cursor()
                            cursor.execute('''
                            INSERT OR REPLACE INTO albums (id, title, update_time)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                            ''', (album_id, album_title))
                            self.system_db_conn.commit()
                            imported_count += 1
            
            # 重新加载专辑列表
            self.load_existing_albums()
            
            messagebox.showinfo("导入完成", f"成功导入 {imported_count} 个专辑信息到系统数据库")
            
        except Exception as e:
            messagebox.showerror("导入错误", f"扫描和导入专辑信息时出错: {str(e)}")
            
    def show_main_interface(self):
        """显示主界面，包含输入框和已有专辑列表"""
        for widget in self.root.winfo_children():
            widget.destroy()

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="播客数据获得", font=("SimHei", 14, "bold")).pack(pady=20)

        # 输入区域
        input_frame = ttk.LabelFrame(main_frame, text="输入新专辑ID", padding="10")
        input_frame.pack(fill=tk.X, pady=10)

        ttk.Label(input_frame, text="喜马拉雅专辑ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.album_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.album_id_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(input_frame, text="获取数据", command=self.fetch_album_data).grid(row=0, column=2, padx=10)

        # 已有专辑列表区域
        albums_frame = ttk.LabelFrame(main_frame, text="已有专辑", padding="10")
        albums_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # 创建列表框和滚动条
        self.albums_tree = ttk.Treeview(albums_frame, columns=("id", "title"), show="headings")
        self.albums_tree.heading("id", text="专辑ID")
        self.albums_tree.heading("title", text="专辑标题")
        self.albums_tree.column("id", width=100, anchor=tk.CENTER)
        self.albums_tree.column("title", width=500, anchor=tk.W)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(albums_frame, orient="vertical", command=self.albums_tree.yview)
        self.albums_tree.configure(yscrollcommand=scrollbar.set)

        # 绑定双击事件
        self.albums_tree.bind("<Double-1>", self.on_album_select)

        # 布局
        self.albums_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        # 添加扫描导入按钮
        ttk.Button(btn_frame, text="扫描并导入所有专辑", command=self.scan_and_import_albums).pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_frame, text="刷新列表", command=self.load_existing_albums).pack(side=tk.RIGHT, padx=10)

        # 加载已有专辑
        self.load_existing_albums()

    def load_existing_albums(self):
        """加载已有的专辑列表"""
        # 清空列表
        for item in self.albums_tree.get_children():
            self.albums_tree.delete(item)

        try:
            if self.system_db_conn:
                cursor = self.system_db_conn.cursor()
                cursor.execute("SELECT id, title FROM albums ORDER BY update_time DESC")
                albums = cursor.fetchall()

                for album in albums:
                    album_id, title = album
                    self.albums_tree.insert("", tk.END, values=(album_id, title), tags=(album_id,))
        except Exception as e:
            messagebox.showerror("数据库错误", f"加载专辑列表失败: {str(e)}")

    def on_album_select(self, event):
        """处理专辑选择事件"""
        selection = self.albums_tree.selection()
        if not selection:
            return

        item = selection[0]
        tags = self.albums_tree.item(item, "tags")
        if tags and len(tags) > 0:
            album_id = tags[0]
            # 询问是否更新该专辑
            if messagebox.askyesno("更新确认", f"是否更新专辑 '{self.albums_tree.item(item, 'values')[1]}' 的数据?"):
                self.fetch_album_data(album_id)

    def log_result(self, album_id, success, message):
        """记录专辑处理结果到日志文件"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "成功" if success else "失败"
        log_entry = f"[{timestamp}] 专辑ID: {album_id} - {status} - {message}\n"
        
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(log_entry)
            # 同时输出到控制台
            print(log_entry.strip())
        except Exception as e:
            print(f"写入日志失败: {str(e)}")
    
    def fetch_album_data(self, album_id=None):
        """从网络获取专辑信息和数据"""
        # 处理多个专辑ID的情况
        if album_id is None:
            album_id_input = self.album_id_var.get().strip()
            # 用空格分割输入的ID，支持多个专辑ID
            album_ids = album_id_input.split()
            
            # 如果输入为空，提示用户
            if not album_ids:
                messagebox.showinfo("提示", "请输入专辑ID")
                return
            
            # 如果输入多个ID，逐个处理
            if len(album_ids) > 1:
                # 批量处理标志设为True
                self.batch_processing = True
                
                # 创建批量处理进度界面
                for widget in self.root.winfo_children():
                    widget.destroy()
                
                main_frame = ttk.Frame(self.root, padding="10")
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                ttk.Label(main_frame, text="播客数据获得 - 批量处理",
                          font=("SimHei", 14, "bold")).pack(pady=10)
                
                # 专辑总进度
                album_progress_frame = ttk.LabelFrame(main_frame, text="专辑处理进度")
                album_progress_frame.pack(fill=tk.X, padx=20, pady=10)
                
                self.album_progress_var = tk.DoubleVar()
                album_progress = ttk.Progressbar(album_progress_frame, variable=self.album_progress_var, maximum=len(album_ids))
                album_progress.pack(fill=tk.X, padx=10, pady=5)
                
                self.album_status_var = tk.StringVar(value=f"准备处理第1个专辑 (共{len(album_ids)}个)")
                ttk.Label(album_progress_frame, textvariable=self.album_status_var).pack(pady=5)
                
                # 当前专辑处理状态
                current_album_frame = ttk.LabelFrame(main_frame, text="当前专辑处理详情")
                current_album_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
                
                self.current_album_status_var = tk.StringVar(value="等待开始处理...")
                ttk.Label(current_album_frame, textvariable=self.current_album_status_var, wraplength=600).pack(pady=5)
                
                self.current_item_progress_var = tk.DoubleVar()
                self.current_item_progress = ttk.Progressbar(current_album_frame, variable=self.current_item_progress_var)
                self.current_item_progress.pack(fill=tk.X, padx=10, pady=5)
                
                self.root.update()
                
                # 记录批量处理开始
                self.log_result("批量处理开始", True, f"共{len(album_ids)}个专辑ID待处理")
                
                # 逐个处理每个专辑ID
                for i, album_id in enumerate(album_ids):
                    # 更新专辑进度
                    self.album_progress_var.set(i)
                    self.album_status_var.set(f"正在处理第{i+1}个专辑: {album_id} (共{len(album_ids)}个)")
                    self.root.update()
                    
                    # 检查专辑ID是否有效
                    if not album_id.isdigit():
                        self.log_result(album_id, False, "专辑ID不是有效的数字")
                        self.current_album_status_var.set(f"专辑ID {album_id} 不是有效的数字，已跳过")
                        self.root.update()
                        continue
                    
                    # 调用实际的数据获取方法
                    self._fetch_single_album_data(album_id)
                    
                    # 确保UI更新
                    self.root.update()
                
                # 所有专辑处理完毕
                self.album_progress_var.set(len(album_ids))
                self.album_status_var.set(f"已完成所有{len(album_ids)}个专辑的处理")
                self.current_album_status_var.set("批量处理已完成！")
                self.root.update()
                
                self.log_result("批量处理结束", True, f"已完成{len(album_ids)}个专辑的处理")
                self.batch_processing = False
                
                # 添加完成按钮
                btn_frame = ttk.Frame(main_frame)
                btn_frame.pack(pady=20)
                ttk.Button(btn_frame, text="返回主界面", command=self.show_main_interface).pack()
                
                return
            else:
                # 只有一个ID，直接使用
                album_id = album_ids[0]
        
        # 检查专辑ID是否有效
        if not album_id.isdigit():
            messagebox.showerror("输入错误", "专辑ID必须是数字")
            return
        
        # 调用实际的数据获取方法
        self._fetch_single_album_data(album_id)

    def _fetch_single_album_data(self, album_id):
        """获取单个专辑的数据"""
        # 创建专辑文件夹
        self.current_album_id = album_id
        self.album_folder = os.path.join(self.albums_dir, f"album_{album_id}")
        os.makedirs(self.album_folder, exist_ok=True)

        # 准备数据路径
        self.input_data = {
            "album_id": album_id,
            "album_folder": self.album_folder,
            "db_path": os.path.join(self.album_folder, f"album_{album_id}.db"),
            "original_xml_path": os.path.join(self.album_folder, f"original_{album_id}.xml")
        }
        
        # 非批量处理时才显示进度界面
        if not self.batch_processing:
            # 清空主框架，显示进度界面
            for widget in self.root.winfo_children():
                widget.destroy()

            main_frame = ttk.Frame(self.root, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="播客数据获得 - 获取专辑数据",
                      font=("SimHei", 14, "bold")).pack(pady=10)

            status_frame = ttk.Frame(main_frame)
            status_frame.pack(expand=True, fill=tk.BOTH)

            status_var = tk.StringVar(value="正在从网络获取专辑信息...")
            ttk.Label(status_frame, textvariable=status_var, font=("SimHei", 12)).pack(pady=20)

            progress = ttk.Progressbar(status_frame, mode="indeterminate")
            progress.pack(fill=tk.X, padx=50, pady=20)
            progress.start()

            self.root.update()
        else:
            # 批量处理时更新状态变量和进度条
            class BatchStatusVar:
                def set(self, value):
                    if hasattr(self, 'manager') and hasattr(self.manager, 'current_album_status_var'):
                        self.manager.current_album_status_var.set(value)
                        self.manager.root.update()
            
            class BatchProgress:
                def start(self):
                    if hasattr(self, 'manager'):
                        self.manager.current_item_progress_var.set(0)
                        self.manager.root.update()
                def stop(self):
                    pass
            
            status_var = BatchStatusVar()
            status_var.manager = self
            
            progress = BatchProgress()
            progress.manager = self

        try:
            # 检查XML是否需要更新
            xml_needs_update = True
            if os.path.exists(self.input_data["original_xml_path"]):
                # 始终更新XML以获取最新数据
                if not self.batch_processing:
                    status_var.set("已有XML文件，正在更新...")
                    self.root.update()

            # 构建RSS URL
            rss_url = f"https://www.ximalaya.com/album/{album_id}.xml"
            if not self.batch_processing:
                status_var.set(f"正在访问: {rss_url}")
                self.root.update()

            # 发送请求获取XML
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(rss_url, headers=headers, timeout=15)
            response.raise_for_status()

            if not response.content.strip():
                raise ValueError("服务器返回空内容")

            # 保存原始XML
            with open(self.input_data["original_xml_path"], "wb") as f:
                f.write(response.content)
            if not self.batch_processing:
                ttk.Label(main_frame, text=f"原始XML已保存至: {self.input_data['original_xml_path']}",
                          font=("SimHei", 9)).pack(pady=5)

            # 连接专辑数据库
            self.init_album_database()
            
            # 连接系统数据库
            if not hasattr(self, 'system_db_conn') or not self.system_db_conn:
                self.init_system_database()

            # 解析XML
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                error_line = e.position[0]
                error_col = e.position[1]
                raise ValueError(f"XML解析错误（行: {error_line}, 列: {error_col}）：{str(e)}")

            # 提取专辑标题
            album_title = "未知专辑"
            channel = root.find(".//channel")
            if channel:
                album_title = channel.findtext("title", "未知专辑").strip()

                # 更新专辑信息到系统数据库
                self.update_album_info(album_id, album_title)

            # 查找所有item元素
            items = root.findall(".//item")

            if not items:
                self.log_result(album_id, False, "未找到专辑中的单集信息")
                if not self.batch_processing:
                    self.show_main_interface()
                return

            # 单集处理进度
            if not self.batch_processing:
                progress_var = tk.DoubleVar()
                item_progress = ttk.Progressbar(status_frame, variable=progress_var, maximum=len(items))
                item_progress.pack(fill=tk.X, padx=50, pady=5)

                item_status_var = tk.StringVar(value="开始处理单集...")
                ttk.Label(status_frame, textvariable=item_status_var).pack(pady=5)

                self.root.update()
            else:
                # 批量处理时更新进度条和状态
                progress_var = self.current_item_progress_var
                # 设置进度条最大值
                self.current_item_progress.configure(maximum=len(items))
                
                class BatchItemStatusVar:
                    def set(self, value):
                        if hasattr(self, 'manager') and hasattr(self.manager, 'current_album_status_var'):
                            self.manager.current_album_status_var.set(value)
                            self.manager.root.update()
                
                item_status_var = BatchItemStatusVar()
                item_status_var.manager = self

            new_items_count = 0
            for i, item in enumerate(items):
                title = item.findtext("title", "").strip()
                if not title:
                    title = f"未命名单集_{i + 1}"

                # 更新进度
                progress_var.set(i + 1)
                item_status_var.set(f"正在处理: {title[:30]}... ({i + 1}/{len(items)})")
                self.root.update()

                # 提取时长
                duration = self.extract_duration(item)

                # 提取音频URL
                audio_url = self.extract_enclosure_url(item)
                if not audio_url:
                    audio_url = item.findtext("link", "").strip()

                # 生成文件名（使用标题的哈希值避免重复）
                filename = f"episode_{hash(title)}_{i + 1}.mp3"

                # 检查是否已存在该条目
                if not self.check_episode_exists(title):
                    # 新增条目，标注初始值为标题
                    self.add_episode({
                        "filename": filename,
                        "duration": duration,
                        "title": title,
                        "annotation": title,  # 标注初始值等于标题
                        "url": audio_url
                    })
                    new_items_count += 1

                # 控制请求频率
                if i % 5 == 0 and i > 0:
                    time.sleep(1)

            # 记录成功信息
            success_message = f"共处理 {len(items)} 个单集，新增 {new_items_count} 个"
            self.log_result(album_id, True, success_message)
            
            if not self.batch_processing:
                status_var.set(f"成功获取专辑数据，{success_message}")
                progress.stop()

                # 返回按钮
                btn_frame = ttk.Frame(main_frame)
                btn_frame.pack(pady=20)
                ttk.Button(btn_frame, text="返回主界面", command=self.show_main_interface).pack()

        except Exception as e:
            progress.stop()
            
            # 记录错误信息
            error_msg = f"获取或解析专辑数据时出错: {str(e)}"
            self.log_result(album_id, False, error_msg)
            
            if not self.batch_processing:
                status_var.set(f"获取专辑数据失败")

                btn_frame = ttk.Frame(main_frame)
                btn_frame.pack(pady=20)

                ttk.Button(btn_frame, text="重试", command=lambda: self._fetch_single_album_data(album_id)).pack(side=tk.LEFT, padx=10)
                ttk.Button(btn_frame, text="返回", command=self.show_main_interface).pack(side=tk.LEFT, padx=10)

                # 非批量处理时仍显示错误弹窗，但批量处理时自动跳过
                messagebox.showerror("错误", error_msg)

    def init_system_database(self):
        """初始化系统全局数据库，包含专辑列表"""
        try:
            # 连接数据库
            self.system_db_conn = sqlite3.connect(self.system_db_path)
            cursor = self.system_db_conn.cursor()

            # 创建专辑列表表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS albums (
                id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                cover_url TEXT,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            self.system_db_conn.commit()

        except Exception as e:
            messagebox.showerror("数据库错误", f"初始化系统数据库失败: {str(e)}")
            if self.system_db_conn:
                self.system_db_conn.close()
                self.system_db_conn = None

    def init_album_database(self):
        """初始化专辑数据库，只包含单集数据"""
        try:
            # 连接数据库
            self.album_db_conn = sqlite3.connect(self.input_data["db_path"])
            cursor = self.album_db_conn.cursor()

            # 创建专辑信息表（仅存储当前专辑的基本信息）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_info (
                id TEXT PRIMARY KEY,
                title TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建单集表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                duration TEXT,
                title TEXT UNIQUE,
                annotation TEXT,
                url TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            self.album_db_conn.commit()

        except Exception as e:
            messagebox.showerror("数据库错误", f"初始化专辑数据库失败: {str(e)}")
            if self.album_db_conn:
                self.album_db_conn.close()
                self.album_db_conn = None

    def update_album_info(self, album_id, title):
        """更新专辑数据库中的专辑信息"""
        if not self.album_db_conn:
            return

        # 更新专辑数据库
        cursor = self.album_db_conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO album_info (id, title, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (album_id, title))
        self.album_db_conn.commit()

        # 更新系统数据库
        if self.system_db_conn:
            cursor = self.system_db_conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO albums (id, title, update_time)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (album_id, title))
            self.system_db_conn.commit()

    def check_episode_exists(self, title):
        """检查单集是否已存在"""
        if not self.album_db_conn:
            return False

        cursor = self.album_db_conn.cursor()
        cursor.execute('SELECT id FROM episodes WHERE title = ?', (title,))
        return cursor.fetchone() is not None

    def add_episode(self, episode_data):
        """添加新单集"""
        if not self.album_db_conn:
            return

        cursor = self.album_db_conn.cursor()
        cursor.execute('''
        INSERT INTO episodes (filename, duration, title, annotation, url)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            episode_data["filename"],
            episode_data["duration"],
            episode_data["title"],
            episode_data["annotation"],
            episode_data["url"]
        ))
        self.album_db_conn.commit()

    def extract_duration(self, item):
        """从XML元素中提取时长信息"""
        # 尝试1: 直接查找duration标签
        duration = item.findtext("duration", "").strip()
        if duration:
            return self.format_duration(duration)

        # 尝试2: 查找itunes:duration标签
        itunes_duration = item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration", "").strip()
        if itunes_duration:
            return self.format_duration(itunes_duration)

        # 尝试3: 从描述中提取时长
        description = item.findtext("description", "").strip()
        if description:
            match = re.search(r'时长[:：]\s*(\d+[:：]\d+(:\d+)?|\d+)', description)
            if match:
                return self.format_duration(match.group(1))

        # 尝试4: 从标题中提取时长
        title = item.findtext("title", "").strip()
        if title:
            match = re.search(r'\[(\d+[:：]\d+(:\d+)?|\d+)\]', title)
            if match:
                return self.format_duration(match.group(1))

        return ""

    def format_duration(self, duration_str):
        """标准化时长格式"""
        if not duration_str or duration_str.strip() == "":
            return ""

        duration_str = duration_str.strip()

        if duration_str.isdigit():
            seconds = int(duration_str)
            return str(timedelta(seconds=seconds))

        parts = duration_str.split(':')
        try:
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return f"00:{minutes:02d}:{seconds:02d}"
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except ValueError:
            pass

        return duration_str

    def extract_enclosure_url(self, item):
        """专门提取<enclosure>标签中的URL"""
        # 查找所有enclosure标签
        enclosures = item.findall("enclosure")
        for enclosure in enclosures:
            # 检查是否包含url属性且type是音频类型
            if ('url' in enclosure.attrib and
                    'type' in enclosure.attrib and
                    enclosure.attrib['type'].startswith('audio/')):

                # 清理URL中的可能的双斜杠问题
                url = enclosure.attrib['url']
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:  # 确保是完整URL
                    # 修复可能的双斜杠问题
                    if url.startswith('//') and not url.startswith('http'):
                        return f"https:{url}"
                    return url

        return ""

    def __del__(self):
        """析构函数，关闭数据库连接"""
        if self.system_db_conn:
            self.system_db_conn.close()
        if self.album_db_conn:
            self.album_db_conn.close()


if __name__ == "__main__":
    root = tk.Tk()
    app = PodcastDataGetter(root)
    root.mainloop()