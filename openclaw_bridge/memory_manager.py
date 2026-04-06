"""
会话记忆与归档策略管理器

负责对话日志格式化、记忆水位检测、分卷归档和 OpenClaw 通知协调。
设计约束：强依赖 SandboxManager 提供的读写接口，不直接操作文件系统。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# 注意：不导入 os，所有文件操作通过 SandboxManager 完成

from .sandbox_manager import SandboxManager
from .openclaw_client import OpenClawClient


# 配置模块级日志
logger = logging.getLogger(__name__)


class MemoryManager:
    """
    会话记忆与归档策略管理器
    
    职责：
    1. 格式化并保存对话日志
    2. 检测记忆水位并触发归档
    3. 协调 OpenClaw 结算通知
    
    设计约束：
    强依赖 SandboxManager 提供的读写接口，不直接操作文件系统。
    """
    
    def __init__(
        self, 
        sandbox_manager: SandboxManager,
        openclaw_client: OpenClawClient
    ) -> None:
        """
        初始化记忆管理器
        
        Args:
            sandbox_manager: 沙盒管理器（依赖注入）
            openclaw_client: OpenClaw 客户端（依赖注入）
        """
        self._sandbox = sandbox_manager
        self._openclaw = openclaw_client
    
    def _format_dialog_history(self, dialog_history: List[Dict[str, Any]]) -> str:
        """
        内部方法：格式化对话历史为 Markdown 格式
        
        将 JSON 格式的对话列表转化为带有时间戳的 Markdown 字符串，
        格式为 "## 会话记录 (时间)" 后跟对话内容。
        
        Args:
            dialog_history: 对话历史列表，每项包含 role 和 text 字段
            
        Returns:
            格式化后的 Markdown 字符串
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建会话记录头部
        log_content = f"\n\n## 会话记录 ({current_time})\n"
        
        # 遍历对话历史，逐条格式化
        for turn in dialog_history:
            role = "🧑 User" if turn.get("role") == "user" else "🤖 AI"
            text = turn.get("text", "")
            log_content += f"**{role}**: {text}\n"
        
        return log_content
    
    async def check_and_archive_memory(
        self, 
        user_id: str, 
        project_name: str
    ) -> Dict[str, Any]:
        """
        弹性水位检测与归档动作
        
        检测 memory_log.md 的字符数：
        - 若 >= ARCHIVE_THRESHOLD_CHARS (35000) 字符，触发分卷归档
        - 若 < ARCHIVE_THRESHOLD_CHARS 字符，安全水位，不执行切分
        
        归档流程：
        1. 确保 raw_archives 目录存在
        2. 异步读取 memory_log.md 内容
        3. 计算字符数，判断是否达到阈值
        4. 若达到阈值，扫描现有卷号，生成新卷号
        5. 调用 execute_archive_transaction 执行原子归档事务
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 项目名称（需带 _project 后缀）
            
        Returns:
            归档信息字典：
            - {"triggered": False, "char_count": N} 未触发归档
            - {"triggered": True, "archived_file": "raw_vol_001.md", "char_count": N} 触发归档
            - {"triggered": False, "reason": "..."} 异常情况
        """
        # 获取相关路径
        memory_path = self._sandbox.get_memory_log_path(user_id, project_name)
        raw_archives_dir = self._sandbox.get_raw_archives_path(user_id, project_name)
        
        # 确保 raw_archives 目录存在
        self._sandbox.ensure_directory(raw_archives_dir)
        
        # 检查 memory_log.md 是否存在
        if not self._sandbox.file_exists(memory_path):
            logger.warning(f"[MemoryManager] 记忆文件不存在: {memory_path}")
            return {"triggered": False, "reason": "memory_log_not_found"}
        
        try:
            # 异步读取文件内容
            content = await self._sandbox.read_file(memory_path)
            char_count = len(content)
            
            logger.info(f"[MemoryManager] 水位检测: 当前 memory_log.md 字符数: {char_count}")
            
            # 判断是否达到归档阈值
            if char_count >= self._sandbox.ARCHIVE_THRESHOLD_CHARS:
                # 触发分卷归档
                # 扫描 raw_archives 目录，找到下一个卷号
                existing_vols = self._sandbox.list_directory(raw_archives_dir)
                
                # 过滤出归档文件并解析卷号
                max_vol = 0
                for vol_file in existing_vols:
                    if vol_file.startswith("raw_vol_") and vol_file.endswith(".md"):
                        try:
                            # 文件名格式: raw_vol_001.md
                            vol_num_str = vol_file.replace("raw_vol_", "").replace(".md", "")
                            vol_num = int(vol_num_str)
                            max_vol = max(max_vol, vol_num)
                        except ValueError:
                            # 文件名格式异常，跳过
                            continue
                
                # 生成新卷号
                next_index = max_vol + 1
                new_filename = f"raw_vol_{next_index:03d}.md"
                
                # 构建归档文件完整路径（通过 sandbox 的 join_path 方法）
                new_filepath = self._sandbox.join_path(raw_archives_dir, new_filename)
                
                # 执行原子归档事务
                actual_char_count, success = await self._sandbox.execute_archive_transaction(
                    memory_path, 
                    new_filepath
                )
                
                if success:
                    logger.info(
                        f"[MemoryManager] 触发弹性分卷，当前字数: {actual_char_count}，"
                        f"已归档为 {new_filename}"
                    )
                    return {
                        "triggered": True,
                        "archived_file": new_filename,
                        "char_count": actual_char_count
                    }
                else:
                    return {"triggered": False, "reason": "archive_transaction_failed"}
            
            # 安全水位，不执行切分
            return {"triggered": False, "char_count": char_count}
            
        except FileNotFoundError:
            logger.warning(f"[MemoryManager] 记忆文件不存在: {memory_path}")
            return {"triggered": False, "reason": "memory_log_not_found"}
        except Exception as e:
            logger.error(f"[MemoryManager] 归档检测异常: {e}")
            return {"triggered": False, "error": str(e)}
    
    async def analyze_and_save_memory(
        self, 
        user_id: str, 
        dialog_history: List[Dict[str, Any]], 
        project_snapshot: str
    ) -> Optional[asyncio.Task]:
        """
        核心方法：对话日志回写与记忆更新
        
        工作流：
        1. 格式化对话日志
        2. 追加写入到 memory_log.md（通过 sandbox_manager）
        3. 检测水位并执行归档
        4. 异步通知 OpenClaw 执行记忆结算
        
        GC 防护机制（V2.1 新增）：
        - 触发 OpenClaw 异步通知时，将创建的 asyncio.Task 返回给调用方
        - 调用方（CoreBridge）负责持有强引用，防止任务被 GC 回收
        
        Args:
            user_id: 飞书用户身份标识
            dialog_history: 对话历史列表，每项包含 role 和 text 字段
            project_snapshot: 项目快照（从 SessionManager 获取，通话开始时锁定）
            
        Returns:
            asyncio.Task: 后台异步通知任务，由 CoreBridge 持有强引用；
            若 dialog_history 为空则返回 None
        """
        # ============ Early Return 防御 ============
        if not dialog_history:
            logger.debug("[MemoryManager] 对话历史为空，跳过记忆保存")
            return None
        
        # 规范化项目名称（安全校验 + 自动补全后缀）
        project_name = self._sandbox.normalize_project_name(project_snapshot)
        
        logger.info(f"[MemoryManager] 使用状态快照回写记忆: {project_name}")
        
        # 获取记忆文件路径
        file_path = self._sandbox.get_memory_log_path(user_id, project_name)
        
        # ============ 步骤 1: 格式化对话日志 ============
        log_content = self._format_dialog_history(dialog_history)
        
        # ============ 步骤 2: 追加写入 memory_log.md ============
        await self._sandbox.write_file(file_path, log_content, mode='a')
        
        logger.info(
            f"[MemoryManager] 用户 {user_id} 的记忆文件已更新完毕 "
            f"(项目: {project_name})"
        )
        
        # ============ 步骤 3: 检测水位并执行归档 ============
        archive_info = await self.check_and_archive_memory(user_id, project_name)
        
        # ============ 步骤 4: 异步通知 OpenClaw（Fire-and-Forget）============
        # 获取项目路径
        project_path = self._sandbox.get_project_path(user_id, project_name)
        
        # 创建异步通知任务
        task = asyncio.create_task(
            self._openclaw.notify_memory_settlement(
                user_id=user_id,
                project_name=project_name,
                project_path=project_path,
                archive_info=archive_info
            )
        )
        
        # 返回 Task 供上层持有强引用，防止 GC 回收
        return task