"""
飞书 Token 生命周期管理器

负责管理飞书应用的各类 Token，提供自动缓存和刷新机制。
"""

import time
import httpx
from typing import Dict, Any, Optional

from .exceptions import FeishuAuthException


class TokenManager:
    """
    飞书 Token 生命周期管理器
    
    职责：
    1. 管理应用级 tenant_access_token（需缓存和自动刷新）
    2. 管理用户级 user_access_token（通过授权码换取）
    3. 提供 Token 自动刷新机制，避免过期
    """
    
    def __init__(
        self, 
        app_id: str, 
        app_secret: str,
        http_client: httpx.AsyncClient
    ) -> None:
        """
        初始化 Token 管理器
        
        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            http_client: 共享的 HTTP 客户端（由 CoreBridge 注入）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self._http_client = http_client
        
        # tenant_access_token 缓存
        self._tenant_token: Optional[str] = None
        self._tenant_token_expires_at: float = 0  # 过期时间戳
    
    async def get_tenant_access_token(self) -> str:
        """
        获取 tenant_access_token（应用级）
        
        自动缓存和刷新机制：
        1. 若缓存有效（未过期），直接返回
        2. 若缓存无效或不存在，调用飞书 API 获取新 Token
        
        Returns:
            有效的 tenant_access_token
            
        Raises:
            FeishuAuthException: Token 获取失败时抛出
        """
        # 检查缓存是否有效（提前 60 秒刷新，避免边界情况）
        if self._tenant_token and time.time() < self._tenant_token_expires_at - 60:
            return self._tenant_token
        
        # 缓存无效，刷新 Token
        await self._refresh_tenant_token()
        return self._tenant_token
    
    async def exchange_code_for_user_token(self, code: str) -> Dict[str, Any]:
        """
        通过授权码换取用户 access_token 和身份信息
        
        Args:
            code: 飞书免登授权码
            
        Returns:
            包含 access_token 和用户信息的字典:
            {
                "access_token": "u-xxx",
                "user_id": "xxx",
                "union_id": "xxx"
            }
            
        Raises:
            FeishuAuthException: 换取失败时抛出
        """
        token_url = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "code": code
        }
        
        try:
            response = await self._http_client.post(token_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            access_token = data.get("access_token")
            if not access_token:
                raise FeishuAuthException(
                    "获取用户 access_token 失败",
                    {"response": data}
                )
            
            return data
            
        except httpx.HTTPError as e:
            raise FeishuAuthException(
                f"飞书授权码换取失败: {str(e)}",
                {"error": str(e)}
            )
    
    # ============ 缓存抽象层（为多进程扩展预留）============
    
    def _get_cached_token(self) -> Optional[str]:
        """
        内部方法：从缓存获取 Token（当前为内存缓存）
        
        设计意图：
        - 当前实现：直接返回内存变量 self._tenant_token
        - 未来扩展：可替换为 Redis 获取，无需修改上层调用代码
          示例：return await redis.get("feishu:tenant_token")
        
        Returns:
            缓存的 Token 字符串，若不存在则返回 None
        """
        return self._tenant_token
    
    def _set_cached_token(self, token: str, expires_at: float) -> None:
        """
        内部方法：设置 Token 缓存（当前为内存缓存）
        
        设计意图：
        - 当前实现：直接设置内存变量
        - 未来扩展：可替换为 Redis 存储，支持多 Worker 共享
          示例：await redis.set("feishu:tenant_token", token, ex=7200)
        
        Args:
            token: 要缓存的 Token 字符串
            expires_at: 过期时间戳
        """
        self._tenant_token = token
        self._tenant_token_expires_at = expires_at
    
    async def _refresh_tenant_token(self) -> None:
        """
        内部方法：调用飞书 API 刷新 tenant_access_token
        
        Raises:
            FeishuAuthException: Token 刷新失败时抛出
        """
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = await self._http_client.post(token_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            tenant_token = data.get("tenant_access_token")
            expire_seconds = data.get("expire", 7200)
            
            if not tenant_token:
                raise FeishuAuthException(
                    "获取 tenant_access_token 失败",
                    {"response": data}
                )
            
            # 计算过期时间戳：当前时间 + 有效期秒数
            expires_at = time.time() + expire_seconds
            self._set_cached_token(tenant_token, expires_at)
            
        except httpx.HTTPError as e:
            raise FeishuAuthException(
                f"飞书 tenant_access_token 刷新失败: {str(e)}",
                {"error": str(e)}
            )