"""
飞书官方 API 聚合层

封装所有飞书官方 API 调用，不包含任何文件操作或业务逻辑。
"""

import httpx
from typing import Dict, Any

from .exceptions import FeishuAuthException
from .token_manager import TokenManager


class FeishuClient:
    """
    飞书官方 API 聚合层
    
    职责：
    1. 处理所有向飞书官方 API 发起的 HTTP 请求
    2. 提供免登鉴权接口
    3. 提供消息推送接口（后续扩展）
    
    设计约束：
    该模块只面向飞书官方服务器，不了解任何关于 OpenClaw 或本地记忆文件的信息。
    """
    
    def __init__(
        self, 
        token_manager: TokenManager,
        http_client: httpx.AsyncClient
    ) -> None:
        """
        初始化飞书客户端
        
        Args:
            token_manager: Token 管理器（依赖注入）
            http_client: 共享的 HTTP 客户端（依赖注入）
        """
        self._token_manager = token_manager
        self._http_client = http_client
    
    async def authenticate_user(self, code: str) -> str:
        """
        核心方法：鉴权换取用户身份标识
        
        将前端 H5 传来的免登 code 置换为 user_id 或 union_id
        
        Args:
            code: 飞书免登授权码
            
        Returns:
            用户身份标识（user_id 或 union_id）
            
        Raises:
            FeishuAuthException: 鉴权失败时抛出
        """
        # 1. 通过授权码换取用户 access_token
        token_data = await self._token_manager.exchange_code_for_user_token(code)
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise FeishuAuthException(
                "获取用户 access_token 失败",
                {"response": token_data}
            )
        
        # 2. 获取用户信息
        user_identifier = await self._get_user_info(access_token)
        return user_identifier
    
    async def _get_user_info(self, access_token: str) -> str:
        """
        内部方法：通过 access_token 获取用户信息
        
        Args:
            access_token: 用户级 access_token
            
        Returns:
            用户身份标识（user_id 或 union_id）
            
        Raises:
            FeishuAuthException: 获取用户信息失败时抛出
        """
        user_info_url = "https://open.feishu.cn/open-apis/authen/v1/user_info"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = await self._http_client.get(user_info_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                raise FeishuAuthException(
                    f"获取用户信息失败: {data.get('msg')}",
                    {"code": data.get("code"), "response": data}
                )
            
            user_info = data.get("data", data)
            user_identifier = user_info.get("user_id") or user_info.get("union_id")
            
            if not user_identifier:
                raise FeishuAuthException(
                    "无法从飞书接口提取到有效的 user_id 或 union_id",
                    {"response": data}
                )
            
            return user_identifier
            
        except httpx.HTTPError as e:
            raise FeishuAuthException(
                f"飞书用户信息接口请求异常: {str(e)}",
                {"error": str(e)}
            )
    
    # ============ 后续扩展：消息推送接口 ============
    
    async def send_text_message(self, user_id: str, text: str) -> bool:
        """
        发送文本消息给指定用户（后续扩展）
        
        Args:
            user_id: 接收用户的 ID
            text: 消息内容
            
        Returns:
            True 表示发送成功
            
        Raises:
            FeishuAuthException: 发送失败时抛出
        """
        # 获取 tenant_access_token
        tenant_token = await self._token_manager.get_tenant_access_token()
        
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "receive_id_type": "user_id",
            "content": f'{{"text":"{text}"}}',
            "msg_type": "text"
        }
        
        try:
            response = await self._http_client.post(
                send_url,
                headers=headers,
                params={"receive_id": user_id},
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                raise FeishuAuthException(
                    f"发送消息失败: {data.get('msg')}",
                    {"code": data.get("code"), "response": data}
                )
            
            return True
            
        except httpx.HTTPError as e:
            raise FeishuAuthException(
                f"飞书消息发送接口请求异常: {str(e)}",
                {"error": str(e)}
            )
    
    async def send_card_message(self, user_id: str, card: Dict[str, Any]) -> bool:
        """
        发送卡片消息给指定用户（后续扩展）
        
        Args:
            user_id: 接收用户的 ID
            card: 卡片消息结构体
            
        Returns:
            True 表示发送成功
            
        Raises:
            FeishuAuthException: 发送失败时抛出
        """
        import json
        
        # 获取 tenant_access_token
        tenant_token = await self._token_manager.get_tenant_access_token()
        
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "receive_id_type": "user_id",
            "content": json.dumps(card, ensure_ascii=False),
            "msg_type": "interactive"
        }
        
        try:
            response = await self._http_client.post(
                send_url,
                headers=headers,
                params={"receive_id": user_id},
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                raise FeishuAuthException(
                    f"发送卡片消息失败: {data.get('msg')}",
                    {"code": data.get("code"), "response": data}
                )
            
            return True
            
        except httpx.HTTPError as e:
            raise FeishuAuthException(
                f"飞书卡片消息发送接口请求异常: {str(e)}",
                {"error": str(e)}
            )