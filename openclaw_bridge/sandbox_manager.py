"""
沙盒与文件 I/O 管理器

系统中唯一允许直接操作底层文件系统的模块，提供异步文件读写、原子写入和并发锁保护。
"""

import os
import re
import json
import shutil
import asyncio
import aiofiles
from typing import Dict, Any

from .exceptions import SandboxInitException, FileWriteException, ConfigLoadException


class SandboxManager:
    """沙盒与文件 I/O 管理器，负责用户目录管理和文件读写操作。"""
    
    # ============ 全局常量集中管理 ============
    
    DEFAULT_CONFIG: Dict[str, Any] = {
        "tts": {
            "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000},
            "speaker": "zh_female_xiaohe_jupiter_bigtts"
        },
        "dialog": {
            "bot_name": "小爪",
            "system_role": "你是小爪，一个耐心且专业的英语学习助手。请根据以下用户的专属学习计划和历史记忆引导其背单词：",
            "speaking_style": "温柔耐心，像朋友一样聊天，语速适中",
            "extra": {"input_mod": "keep_alive", "model": "1.2.1.1"}
        }
    }
    
    DEFAULT_ACTIVE_PROJECT: str = "vocab"
    ARCHIVE_THRESHOLD_CHARS: int = 35000
    
    def __init__(self, memory_dir: str = "memory") -> None:
        self.memory_dir = memory_dir
        self.templates_dir = os.path.join(memory_dir, "templates")
        self.users_dir = os.path.join(memory_dir, "users")
        self._file_locks: Dict[str, asyncio.Lock] = {}
        self._lock_pool_mutex = asyncio.Lock()
        self.ensure_core_directories()
    
    # ============ 路径获取方法 ============
    
    def get_user_sandbox_path(self, user_id: str) -> str:
        """获取用户沙盒根路径。"""
        return os.path.join(self.users_dir, user_id)
    
    def get_user_status_path(self, user_id: str) -> str:
        """获取用户状态文件路径（status.json）。"""
        return os.path.join(self.get_user_sandbox_path(user_id), "status.json")
    
    def get_project_path(self, user_id: str, project_name: str) -> str:
        """获取用户特定项目目录路径。"""
        return os.path.join(self.get_user_sandbox_path(user_id), project_name)
    
    def get_prompt_path(self, user_id: str, project_name: str) -> str:
        """获取用户特定项目的 prompt.json 路径。"""
        return os.path.join(self.get_project_path(user_id, project_name), "prompt.json")
    
    def get_memory_log_path(self, user_id: str, project_name: str) -> str:
        """获取用户特定项目的记忆日志路径。"""
        return os.path.join(self.get_project_path(user_id, project_name), "memory_log.md")
    
    def get_raw_archives_path(self, user_id: str, project_name: str) -> str:
        """获取用户特定项目的原始归档目录路径。"""
        return os.path.join(self.get_project_path(user_id, project_name), "raw_archives")
    
    # ============ 目录初始化方法 ============
    
    def ensure_core_directories(self) -> None:
        """确保核心目录结构存在。"""
        try:
            os.makedirs(self.memory_dir, exist_ok=True)
            os.makedirs(self.users_dir, exist_ok=True)
            if not os.path.exists(self.templates_dir):
                print(f"[SandboxManager] 警告：模板目录 {self.templates_dir} 不存在，新用户初始化将失败！")
        except OSError as e:
            raise SandboxInitException(f"核心目录创建失败: {e}", {"dir": self.memory_dir})
    
    def ensure_user_sandbox(self, user_id: str) -> bool:
        """确保用户沙盒存在，若不存在则从模板初始化。"""
        user_sandbox_path = self.get_user_sandbox_path(user_id)
        status_path = self.get_user_status_path(user_id)
        
        if os.path.exists(user_sandbox_path) and os.path.exists(status_path):
            self.ensure_project_structure_upgraded(user_id)
            return True
        
        print(f"[SandboxManager] 检测到新用户 {user_id}，开始初始化沙盒...")
        
        if not os.path.exists(self.templates_dir):
            raise SandboxInitException(
                "模板目录不存在，无法初始化用户沙盒",
                {"templates_dir": self.templates_dir}
            )
        
        try:
            shutil.copytree(self.templates_dir, user_sandbox_path)
            default_status = {"active_project": self.DEFAULT_ACTIVE_PROJECT}
            self._write_json_sync(status_path, default_status)
            self.ensure_project_structure_upgraded(user_id)
            print(f"[SandboxManager] 用户 {user_id} 沙盒初始化完成，默认项目: {self.DEFAULT_ACTIVE_PROJECT}")
            return True
        except Exception as e:
            print(f"[SandboxManager] 沙盒初始化失败: {e}")
            return False
    
    def ensure_project_structure_upgraded(self, user_id: str) -> None:
        """确保用户所有项目的目录结构已升级到最新版本。"""
        user_sandbox_path = self.get_user_sandbox_path(user_id)
        
        for item in os.listdir(user_sandbox_path):
            project_path = os.path.join(user_sandbox_path, item)
            
            if not os.path.isdir(project_path) or not item.endswith("_project"):
                continue
            
            # 创建 raw_archives 目录
            raw_archives_dir = os.path.join(project_path, "raw_archives")
            if not os.path.exists(raw_archives_dir):
                os.makedirs(raw_archives_dir, exist_ok=True)
            
            # 创建 episodes 目录
            episodes_dir = os.path.join(project_path, "episodes")
            if not os.path.exists(episodes_dir):
                os.makedirs(episodes_dir, exist_ok=True)
            
            # 创建 master_profile.md 文件
            master_profile_path = os.path.join(project_path, "master_profile.md")
            if not os.path.exists(master_profile_path):
                project_display_name = item.replace("_project", "")
                default_content = (
                    f"# {project_display_name} 全局大纲\n\n"
                    f"> 本文件由系统自动生成，用于存储二级记忆（L2）。\n\n"
                    f"## 核心要点\n\n- \n\n## 待办事项\n\n- \n"
                )
                self._write_file_sync(master_profile_path, default_content)
    
    # ============ 文件读写方法 ============
    
    async def get_file_lock(self, file_path: str) -> asyncio.Lock:
        """获取文件专属异步锁，确保同一文件的并发写入串行化。"""
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        
        if normalized_path in self._file_locks:
            return self._file_locks[normalized_path]
        
        # 慢速路径：创建新锁时保护锁池
        async with self._lock_pool_mutex:
            if normalized_path not in self._file_locks:
                self._file_locks[normalized_path] = asyncio.Lock()
            return self._file_locks[normalized_path]
    
    async def read_file(self, file_path: str) -> str:
        """异步读取文件内容。"""
        lock = await self.get_file_lock(file_path)
        async with lock:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                return await f.read()
    
    async def write_file(self, file_path: str, content: str, mode: str = 'w') -> None:
        """
        异步写入文件（带锁保护 + 原子写入）。
        
        - 覆盖模式 ('w')：使用原子写入策略（先写 .tmp，再 os.replace）
        - 追加模式 ('a')：直接追加
        """
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        lock = await self.get_file_lock(file_path)
        
        async with lock:
            try:
                if mode == 'a':
                    # 追加模式：直接追加
                    async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
                        await f.write(content)
                else:
                    # 覆盖模式：原子写入
                    tmp_path = file_path + '.tmp'
                    async with aiofiles.open(tmp_path, mode='w', encoding='utf-8') as f:
                        await f.write(content)
                    # 原子操作：重命名覆盖
                    os.replace(tmp_path, file_path)
                    
            except Exception as e:
                tmp_path = file_path + '.tmp'
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                raise FileWriteException(
                    f"文件写入失败: {e}",
                    {"file": file_path, "mode": mode, "error": str(e)}
                )
    
    async def read_json(self, file_path: str) -> Dict[str, Any]:
        """异步读取 JSON 文件并解析为字典。"""
        lock = await self.get_file_lock(file_path)
        
        async with lock:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
            
            if not content.strip():
                raise ConfigLoadException("配置文件为空", {"file": file_path})
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                raise ConfigLoadException(
                    f"JSON 解析失败: {e}",
                    {"file": file_path, "error": str(e)}
                )
    
    async def write_json(self, file_path: str, data: Dict[str, Any]) -> None:
        """异步写入字典到 JSON 文件（带锁保护 + 原子写入）。"""
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        lock = await self.get_file_lock(file_path)
        
        async with lock:
            try:
                tmp_path = file_path + '.tmp'
                content = json.dumps(data, ensure_ascii=False, indent=4)
                async with aiofiles.open(tmp_path, mode='w', encoding='utf-8') as f:
                    await f.write(content)
                # 原子操作：重命名覆盖
                os.replace(tmp_path, file_path)
                
            except Exception as e:
                tmp_path = file_path + '.tmp'
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                raise FileWriteException(
                    f"JSON 文件写入失败: {e}",
                    {"file": file_path, "error": str(e)}
                )
    
    # ============ 同步写入方法（用于初始化阶段）============
    
    def _write_file_sync(self, file_path: str, content: str) -> None:
        """同步写入文件（用于初始化阶段），采用原子写入策略。"""
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        tmp_path = file_path + '.tmp'
        
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            os.replace(tmp_path, file_path)  # 原子覆盖
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise FileWriteException(
                f"同步文件写入失败: {e}",
                {"file": file_path, "error": str(e)}
            )
    
    def _write_json_sync(self, file_path: str, data: Dict[str, Any]) -> None:
        """同步写入 JSON 文件（用于初始化阶段），采用原子写入策略。"""
        content = json.dumps(data, ensure_ascii=False, indent=4)
        self._write_file_sync(file_path, content)
    
    # ============ 工具方法 ============
    
    def normalize_project_name(self, project_name: str) -> str:
        """规范化项目名称：安全校验 + 自动补全 _project 后缀。"""
        base_name = project_name.replace("_project", "")
        
        # 安全校验：仅允许字母、数字、下划线、连字符
        if not re.match(r'^[\w\-]+$', base_name):
            print(f"[SandboxManager] 警告：项目名 '{base_name}' 包含非法字符，回退为默认项目")
            base_name = self.DEFAULT_ACTIVE_PROJECT
        
        return f"{base_name}_project"
    
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在。"""
        return os.path.exists(file_path)
    
    def move_file(self, src_path: str, dst_path: str) -> None:
        """移动文件（原子操作）。"""
        os.replace(src_path, dst_path)
    
    def ensure_directory(self, dir_path: str) -> None:
        """确保目录存在。"""
        os.makedirs(dir_path, exist_ok=True)
    
    def list_directory(self, dir_path: str) -> list:
        """
        列出目录中的所有文件名
        
        Args:
            dir_path: 目录路径
            
        Returns:
            文件名列表，若目录不存在则返回空列表
        """
        if not os.path.exists(dir_path):
            return []
        return os.listdir(dir_path)
    
    def join_path(self, *path_parts: str) -> str:
        """
        安全拼接路径
        
        Args:
            *path_parts: 路径片段
            
        Returns:
            拼接后的完整路径
        """
        return os.path.join(*path_parts)
    
    async def execute_archive_transaction(
        self, 
        memory_log_path: str, 
        archive_path: str
    ) -> tuple:
        """
        执行归档事务（原子操作）
        
        在单一锁保护下完成：读取内容 → 移动文件 → 创建新空文件
        确保整个过程不会被其他并发写入打断
        
        Args:
            memory_log_path: 原始记忆日志文件路径
            archive_path: 归档目标文件路径
            
        Returns:
            元组 (char_count, success):
            - char_count: 原文件字符数
            - success: 是否成功执行归档
            
        Raises:
            FileWriteException: 归档过程中发生错误
        """
        # 获取 memory_log 文件的专属锁
        lock = await self.get_file_lock(memory_log_path)
        
        async with lock:
            try:
                # 1. 读取现有内容
                async with aiofiles.open(memory_log_path, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                char_count = len(content)
                
                # 2. 移动文件（原子操作）
                os.replace(memory_log_path, archive_path)
                
                # 3. 创建新的空 memory_log.md
                async with aiofiles.open(memory_log_path, mode='w', encoding='utf-8') as f:
                    await f.write("")
                
                return (char_count, True)
                
            except Exception as e:
                raise FileWriteException(
                    f"归档事务执行失败: {e}",
                    {"memory_log": memory_log_path, "archive": archive_path, "error": str(e)}
                )
