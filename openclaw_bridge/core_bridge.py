"""
OpenClaw Bridge 门面调度层

作为主程序的唯一入口，协调各子模块完成复杂工作流。
设计约束：该模块只负责"组合调用"，不应包含具体的业务逻辑。
"""

import os
import copy
import asyncio
import logging
from typing import Dict, Any, Set, Optional, Tuple, List

import httpx

from .sandbox_manager import SandboxManager
from .token_manager import TokenManager
from .feishu_client import FeishuClient
from .openclaw_client import OpenClawClient
from .memory_manager import MemoryManager
from .exceptions import FeishuAuthException, ConfigLoadException


# 配置模块级日志
logger = logging.getLogger(__name__)


class CoreBridge:
    """
    OpenClaw Bridge 门面调度层
    
    职责：
    1. 作为主程序（FastAPI/Sanic 路由）的唯一入口
    2. 协调子模块完成复杂工作流
    3. 管理共享资源生命周期（HTTP 连接池、后台任务）
    
    设计约束：
    该模块只负责"组合调用"，不应包含具体的文件操作或底层网络逻辑。
    """
    
    def __init__(
        self,
        feishu_app_id: str,
        feishu_app_secret: str,
        memory_dir: str = "memory",
        openclaw_gateway_url: Optional[str] = None,
        openclaw_token: Optional[str] = None,
        openclaw_agent_id: Optional[str] = None,
        project_skill_map: Optional[Dict[str, str]] = None
    ) -> None:
        """
        初始化核心桥接层
        
        资源与依赖总管：
        1. 从环境变量读取 OpenClaw 配置
        2. 创建共享 HTTP 连接池
        3. 按依赖顺序实例化子模块
        4. 初始化后台任务强引用集合（GC 防护）
        
        Args:
            feishu_app_id: 飞书应用 ID
            feishu_app_secret: 飞书应用密钥
            memory_dir: 记忆文件存储根目录
            openclaw_gateway_url: OpenClaw Gateway URL（可从环境变量读取）
            openclaw_token: OpenClaw Token（可从环境变量读取）
            openclaw_agent_id: OpenClaw Agent ID（可从环境变量读取）
            project_skill_map: 项目与 Skill 的映射字典（可选）
        """
        # ============ 步骤 1：从环境变量读取 OpenClaw 配置 ============
        self._gateway_url = openclaw_gateway_url or os.getenv("OPENCLAW_GATEWAY_URL", "")
        self._openclaw_token = openclaw_token or os.getenv("OPENCLAW_TOKEN", "")
        self._agent_id = openclaw_agent_id or os.getenv("OPENCLAW_AGENT_ID", "main")
        
        # ============ 步骤 2：创建共享 HTTP 客户端（统一管理连接池）============
        self._http_client = httpx.AsyncClient(timeout=15.0)
        
        # ============ 步骤 3：按依赖顺序实例化子模块 ============
        # 3.1 沙盒管理器（无依赖）
        self._sandbox = SandboxManager(memory_dir=memory_dir)
        
        # 3.2 Token 管理器（依赖 http_client）
        self._token_manager = TokenManager(
            app_id=feishu_app_id,
            app_secret=feishu_app_secret,
            http_client=self._http_client
        )
        
        # 3.3 飞书客户端（依赖 token_manager, http_client）
        self._feishu = FeishuClient(
            token_manager=self._token_manager,
            http_client=self._http_client
        )
        
        # 3.4 OpenClaw 客户端（依赖 http_client）
        self._openclaw = OpenClawClient(
            http_client=self._http_client,
            gateway_url=self._gateway_url,
            token=self._openclaw_token,
            agent_id=self._agent_id,
            project_skill_map=project_skill_map
        )
        
        # 3.5 记忆管理器（依赖 sandbox_manager, openclaw_client）
        self._memory = MemoryManager(
            sandbox_manager=self._sandbox,
            openclaw_client=self._openclaw
        )
        
        # ============ 步骤 4：初始化后台任务强引用集合（GC 防护）============
        self._background_tasks: Set[asyncio.Task] = set()
        
        logger.info("[CoreBridge] 门面调度层初始化完成")
    
    # ============ Property 属性暴露 ============
    
    @property
    def sandbox(self) -> SandboxManager:
        """
        暴露 sandbox_manager 供特殊情况使用
        
        Returns:
            SandboxManager 实例
        """
        return self._sandbox
    
    @property
    def feishu(self) -> FeishuClient:
        """
        暴露 feishu_client 供特殊情况使用
        
        Returns:
            FeishuClient 实例
        """
        return self._feishu
    
    # ============ 核心对外接口 ============
    
    async def authenticate_and_initialize(self, code: str) -> str:
        """
        核心方法一：鉴权换取身份标识 + 初始化用户沙盒
        
        工作流：
        1. 调用 feishu_client 鉴权获取 user_id
        2. 调用 sandbox_manager 确保用户沙盒存在
        
        Args:
            code: 飞书免登授权码
            
        Returns:
            用户身份标识（user_id 或 union_id）
            
        Raises:
            FeishuAuthException: 鉴权失败时抛出
        """
        # 步骤 1：鉴权获取用户身份标识
        user_id = await self._feishu.authenticate_user(code)
        
        # 步骤 2：确保用户沙盒存在（新用户自动初始化）
        self._sandbox.ensure_user_sandbox(user_id)
        
        logger.info(f"[CoreBridge] 用户 {user_id} 鉴权并初始化完成")
        return user_id
    
    async def generate_doubao_config(
        self, 
        user_id: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        核心方法二：生成豆包会话配置
        
        工作流：
        1. 读取用户状态获取 active_project
        2. 动态加载 prompt.json
        3. 返回配置和项目快照
        
        关键设计：
        - 使用 copy.deepcopy() 防止污染全局常量
        - 兜底逻辑：若 prompt.json 读取失败，使用 DEFAULT_CONFIG 深拷贝
        
        Args:
            user_id: 飞书用户身份标识
            
        Returns:
            元组 (config, project_name):
            - config: 完整的豆包会话配置字典
            - project_name: 当前激活的项目名称（用于状态快照）
        """
        # ============ 步骤 1：读取用户状态获取活跃项目 ============
        status_path = self._sandbox.get_user_status_path(user_id)
        default_status = {"active_project": self._sandbox.DEFAULT_ACTIVE_PROJECT}
        
        try:
            if self._sandbox.file_exists(status_path):
                status = await self._sandbox.read_json(status_path)
            else:
                status = default_status
        except Exception as e:
            logger.warning(f"[CoreBridge] 读取状态文件失败: {e}，使用默认状态")
            status = default_status
        
        project_name = status.get("active_project", self._sandbox.DEFAULT_ACTIVE_PROJECT)
        
        # ============ 步骤 2：规范化项目名称 ============
        project_name = self._sandbox.normalize_project_name(project_name)
        
        # ============ 步骤 3：动态加载 prompt.json ============
        prompt_path = self._sandbox.get_prompt_path(user_id, project_name)
        
        try:
            if self._sandbox.file_exists(prompt_path):
                # 深拷贝读取到的配置，防止污染原始数据
                config = copy.deepcopy(await self._sandbox.read_json(prompt_path))
            else:
                # 尝试从模板加载
                template_prompt_path = self._sandbox.join_path(
                    self._sandbox.templates_dir, 
                    project_name, 
                    "prompt.json"
                )
                if self._sandbox.file_exists(template_prompt_path):
                    config = copy.deepcopy(await self._sandbox.read_json(template_prompt_path))
                    logger.info(f"[CoreBridge] 从模板加载配置: {project_name}")
                else:
                    # 兜底：使用默认配置（必须深拷贝！）
                    config = copy.deepcopy(self._sandbox.DEFAULT_CONFIG)
                    logger.warning(f"[CoreBridge] 使用默认兜底配置")
            
            # 验证必要字段
            if "tts" not in config or "dialog" not in config:
                logger.warning("[CoreBridge] 配置文件缺少必要字段，使用默认配置")
                config = copy.deepcopy(self._sandbox.DEFAULT_CONFIG)
                
        except Exception as e:
            logger.warning(f"[CoreBridge] 读取配置文件异常: {e}，使用默认配置")
            config = copy.deepcopy(self._sandbox.DEFAULT_CONFIG)
        
        # ============ 步骤 4：补全默认值 ============
        # 4.1 确保 tts.audio_config 完整
        if "audio_config" not in config.get("tts", {}):
            config.setdefault("tts", {})["audio_config"] = copy.deepcopy(
                self._sandbox.DEFAULT_CONFIG["tts"]["audio_config"]
            )
        
        # 4.2 设置 dialog_context 为空列表
        config.setdefault("dialog", {})["dialog_context"] = []
        
        # 4.3 确保 extra 字段完整
        default_extra = self._sandbox.DEFAULT_CONFIG["dialog"]["extra"]
        if "extra" not in config.get("dialog", {}):
            config.setdefault("dialog", {})["extra"] = copy.deepcopy(default_extra)
        else:
            config["dialog"]["extra"].setdefault("input_mod", default_extra["input_mod"])
            config["dialog"]["extra"].setdefault("model", default_extra["model"])
        
        logger.info(f"[CoreBridge] 生成豆包配置完成，项目: {project_name}")
        
        # 返回元组 (配置, 项目名快照)
        return config, project_name
    
    async def save_dialog_and_notify(
        self, 
        user_id: str, 
        dialog_history: List[Dict[str, Any]], 
        project_snapshot: str
    ) -> None:
        """
        核心方法三：保存对话日志并通知 OpenClaw
        
        工作流：
        1. 调用 memory_manager 分析并保存记忆
        2. 接收 memory_manager 返回的 asyncio.Task
        3. 将 Task 添加到强引用集合，防止 GC 回收
        4. 绑定 done_callback，任务完成后自动清理
        
        GC 防护机制（V2.1）：
        - CoreBridge 负责收集 MemoryManager 返回的 Task
        - 将 Task 放入 `_background_tasks` 强引用集合
        - 绑定 `task.add_done_callback(self._background_tasks.discard)`
        - 防止任务执行中途被 Python GC 清理
        
        Args:
            user_id: 飞书用户身份标识
            dialog_history: 对话历史列表
            project_snapshot: 项目快照
        """
        # 调用 memory_manager，接收返回的 Task
        task = await self._memory.analyze_and_save_memory(
            user_id, dialog_history, project_snapshot
        )
        
        # GC 防护：判断非 None 后加入强引用集合
        if task is not None:
            self._background_tasks.add(task)
            # 任务完成后自动从集合中移除，避免内存泄漏
            task.add_done_callback(self._background_tasks.discard)
            logger.debug(f"[CoreBridge] 后台任务已加入强引用集合，当前任务数: {len(self._background_tasks)}")
    
    async def switch_project(self, user_id: str, project_name: str) -> bool:
        """
        切换用户的活跃项目
        
        工作流：
        1. 规范化项目名称
        2. 验证目标项目是否存在
        3. 组装新状态，委托 sandbox 进行原子写入
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 目标项目名称（可带或不带 _project 后缀）
            
        Returns:
            True 表示切换成功，False 表示失败
        """
        # 步骤 1：规范化项目名称
        normalized_project_name = self._sandbox.normalize_project_name(project_name)
        
        # 步骤 2：验证目标项目是否存在
        project_path = self._sandbox.get_project_path(user_id, normalized_project_name)
        if not self._sandbox.file_exists(project_path):
            logger.warning(f"[CoreBridge] 目标项目 {normalized_project_name} 不存在，切换失败")
            return False
        
        try:
            # 步骤 3：组装新状态
            # 注意：status.json 中存储的是不带后缀的项目名
            new_status = {
                "active_project": normalized_project_name.replace("_project", "")
            }
            
            # 委托 sandbox 进行原子写入
            status_path = self._sandbox.get_user_status_path(user_id)
            await self._sandbox.write_json(status_path, new_status)
            
            logger.info(f"[CoreBridge] 用户 {user_id} 已切换到项目: {normalized_project_name}")
            return True
            
        except Exception as e:
            logger.error(f"[CoreBridge] 切换项目失败: {e}")
            return False
    
    # ============ 后续扩展：消息推送 ============
    
    async def send_text_message(self, user_id: str, text: str) -> bool:
        """
        发送文本消息给指定用户（后续扩展）
        
        Args:
            user_id: 接收用户的 ID
            text: 消息内容
            
        Returns:
            True 表示发送成功
        """
        return await self._feishu.send_text_message(user_id, text)
    
    async def send_card_message(self, user_id: str, card: Dict[str, Any]) -> bool:
        """
        发送卡片消息给指定用户（后续扩展）
        
        Args:
            user_id: 接收用户的 ID
            card: 卡片消息结构体
            
        Returns:
            True 表示发送成功
        """
        return await self._feishu.send_card_message(user_id, card)
    
    # ============ 资源管理 ============
    
    async def close(self) -> None:
        """
        优雅关闭所有资源
        
        工作流：
        1. 等待所有后台任务完成（最多 5 秒）
        2. 关闭共享 HTTP 客户端
        """
        logger.info("[CoreBridge] 开始优雅关闭...")
        
        # 步骤 1：等待后台任务完成
        if self._background_tasks:
            logger.info(f"[CoreBridge] 等待 {len(self._background_tasks)} 个后台任务完成...")
            done, pending = await asyncio.wait(
                self._background_tasks, 
                timeout=5.0
            )
            
            if pending:
                logger.warning(f"[CoreBridge] {len(pending)} 个任务超时未完成，将被强制取消")
                for task in pending:
                    task.cancel()
        
        # 步骤 2：关闭 HTTP 客户端
        await self._http_client.aclose()
        
        logger.info("[CoreBridge] 优雅关闭完成")