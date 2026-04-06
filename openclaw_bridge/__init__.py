"""
OpenClaw Bridge 模块

提供统一的飞书鉴权、沙盒管理、记忆归档和 OpenClaw 通信能力。

架构重构进度：第三阶段完成 - 门面调度层 (core_bridge.py)

使用方式：
    from openclaw_bridge import OpenClawBridge
    
    bridge = OpenClawBridge(
        feishu_app_id="your_app_id",
        feishu_app_secret="your_app_secret"
    )
    
    user_id = await bridge.authenticate_and_initialize(code)
    config, project_name = await bridge.generate_doubao_config(user_id)
"""

from .exceptions import (
    OpenClawBridgeException,
    FeishuAuthException,
    SandboxInitException,
    ConfigLoadException,
    OpenClawNotifyException,
    FileWriteException,
)

from .sandbox_manager import SandboxManager
from .token_manager import TokenManager
from .feishu_client import FeishuClient
from .openclaw_client import OpenClawClient
from .memory_manager import MemoryManager

# 门面调度层（使用别名导出，实现零感知升级）
from .core_bridge import CoreBridge as OpenClawBridge


__all__ = [
    # 异常类
    "OpenClawBridgeException",
    "FeishuAuthException",
    "SandboxInitException",
    "ConfigLoadException",
    "OpenClawNotifyException",
    "FileWriteException",
    # 子模块（供高级用法直接访问）
    "SandboxManager",
    "TokenManager",
    "FeishuClient",
    "OpenClawClient",
    "MemoryManager",
    # 门面调度层（主入口）
    "OpenClawBridge",  # 实际指向 CoreBridge
]