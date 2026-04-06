"""
OpenClaw 网关通信层

封装 OpenClaw Gateway 的 HTTP 通信协议，支持记忆结算通知和项目-Skill 映射。
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional

from .exceptions import OpenClawNotifyException


# 配置模块级日志
logger = logging.getLogger(__name__)


class OpenClawClient:
    """
    OpenClaw 网关通信层
    
    职责：
    1. 封装 OpenClaw Gateway 的 HTTP 通信
    2. 发送记忆结算通知
    3. 维护项目与 Skill 的映射关系
    
    设计约束：
    动态配置（如 PROJECT_SKILL_MAP）应作为初始化参数传入，避免硬编码。
    """
    
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        gateway_url: str,
        token: str,
        agent_id: str,
        project_skill_map: Optional[Dict[str, str]] = None
    ) -> None:
        """
        初始化 OpenClaw 客户端
        
        Args:
            http_client: 共享的 HTTP 客户端（依赖注入）
            gateway_url: OpenClaw Gateway URL
            token: OpenClaw Token
            agent_id: OpenClaw Agent ID
            project_skill_map: 项目与 Skill 的映射字典（可选，有默认值）
        """
        self._http_client = http_client
        self._gateway_url = gateway_url
        self._token = token
        self._agent_id = agent_id
        
        # 项目与 Skill 的映射（可从外部配置注入）
        self._project_skill_map = project_skill_map or {
            "vocab_project": "vocab-learning-planner",
            "interview_project": "elder-interview-planner"
        }
    
    def get_skill_for_project(self, project_name: str) -> str:
        """
        获取项目对应的 Skill 名称
        
        Args:
            project_name: 项目名称（需带 _project 后缀）
            
        Returns:
            对应的 Skill 名称，若未找到则返回默认值
        """
        skill = self._project_skill_map.get(project_name)
        if skill:
            return skill
        
        # 未找到映射，返回默认 Skill
        logger.warning(
            f"项目 '{project_name}' 未配置 Skill 映射，使用默认 Skill"
        )
        return "elder-interview-planner"
    
    async def notify_memory_settlement(
        self, 
        user_id: str, 
        project_name: str, 
        project_path: str,
        archive_info: Dict[str, Any]
    ) -> bool:
        """
        发送记忆结算通知给 OpenClaw
        
        使用 Fire-and-Forget 模式，非阻塞发送 HTTP POST 请求。
        
        Args:
            user_id: 用户身份标识
            project_name: 项目名称（需带 _project 后缀）
            project_path: 项目绝对路径（用于 OpenClaw 定位文件）
            archive_info: 归档信息字典，包含：
                - triggered: bool, 是否触发归档
                - archived_file: str, 归档文件名（若触发）
                - char_count: int, 字符数
            
        Returns:
            True 表示通知成功，False 表示失败
            
        Raises:
            OpenClawNotifyException: 通知失败时抛出（可选）
        """
        # 获取项目对应的 Skill
        target_skill = self.get_skill_for_project(project_name)
        
        # 获取项目绝对路径
        abs_project_path = os.path.abspath(project_path)
        
        # 根据是否触发归档，动态生成指令内容
        if archive_info and archive_info.get("triggered"):
            archived_file = archive_info.get("archived_file", "")
            char_count = archive_info.get("char_count", 0)
            content = (
                f"[系统通知] 用户 {user_id} 的 {project_name} 语音通话结束。\n"
                f"【项目绝对路径】: {abs_project_path}\n"
                f"⚠️ 【强制指令】：请立即调用并执行你的『{target_skill}』技能来完成本次任务！\n"
                f"本次通话触发了强制分卷，原始日志（{char_count} 字符）已移至 raw_archives/{archived_file}。"
                f"请立即进入该绝对路径，执行长文本提炼，生成摘要到 episodes/ 中，并更新 master_profile.md 和 prompt.json。"
            )
        else:
            char_count = archive_info.get("char_count", 0)
            content = (
                f"[系统通知] 用户 {user_id} 的 {project_name} 语音通话结束。\n"
                f"【项目绝对路径】: {abs_project_path}\n"
                f"⚠️ 【强制指令】：请立即调用并执行你的『{target_skill}』技能来完成本次任务！\n"
                f"当前 memory_log.md 累计 {char_count} 字符。"
                f"请立即进入该绝对路径读取 memory_log.md，更新 master_profile.md 和 prompt.json。"
            )
        
        # 构建请求负载
        payload = {
            "model": "openclaw",
            "messages": [{"role": "user", "content": content}],
            "user": "phonecall-system"  # 使用系统身份，避免污染用户聊天界面
        }
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self._agent_id,
        }
        
        try:
            response = await self._http_client.post(
                self._gateway_url, 
                headers=headers, 
                json=payload
            )
            response.raise_for_status()
            
            logger.info(
                f"[OpenClawClient] 记忆结算通知发送成功，状态码: {response.status_code}，"
                f"触发技能: {target_skill}"
            )
            return True
            
        except httpx.HTTPStatusError as e:
            error_msg = f"OpenClaw 通知失败 (HTTP {e.response.status_code}): {e.response.text}"
            logger.error(f"[OpenClawClient] {error_msg}")
            raise OpenClawNotifyException(
                error_msg,
                {
                    "status_code": e.response.status_code,
                    "response": e.response.text,
                    "user_id": user_id,
                    "project_name": project_name
                }
            )
            
        except httpx.HTTPError as e:
            error_msg = f"OpenClaw 通知失败（网络异常）: {str(e)}"
            logger.error(f"[OpenClawClient] {error_msg}")
            raise OpenClawNotifyException(
                error_msg,
                {
                    "error": str(e),
                    "user_id": user_id,
                    "project_name": project_name
                }
            )
    
    @property
    def project_skill_map(self) -> Dict[str, str]:
        """获取当前的项目-Skill 映射（只读）"""
        return self._project_skill_map.copy()