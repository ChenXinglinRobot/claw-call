"""
OpenClaw Bridge 全局异常中心

所有模块的自定义异常统一在此定义，避免循环引用问题。
各模块应从此文件导入异常类，而非自行定义。

使用示例：
    from openclaw_bridge.exceptions import FeishuAuthException, SandboxInitException
    
    # 抛出异常
    raise FeishuAuthException(f"获取 Token 失败: {response}")
    
    # 上层统一捕获
    try:
        await bridge.authenticate_and_initialize(code)
    except OpenClawBridgeException as e:
        logger.error(f"桥接层异常: {e}")
"""

from typing import Optional, Any


class OpenClawBridgeException(Exception):
    """
    OpenClaw Bridge 基础异常类
    
    所有模块级异常应继承此类，便于上层统一捕获。
    
    Attributes:
        message: 异常描述信息
        details: 额外的异常详情（可选）
    
    Example:
        >>> raise OpenClawBridgeException("基础错误")
        OpenClawBridgeException: 基础错误
    """
    
    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        """
        初始化基础异常
        
        Args:
            message: 异常描述信息
            details: 额外的异常详情（如原始响应数据、错误码等）
        """
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """返回异常的字符串表示"""
        if self.details:
            return f"{self.message} (详情: {self.details})"
        return self.message


class FeishuAuthException(OpenClawBridgeException):
    """
    飞书授权相关异常
    
    触发场景：
    - Token 获取失败（access_token 或 tenant_access_token）
    - 用户信息获取失败
    - 授权码换取失败
    - 飞书 API 返回错误码
    
    Example:
        >>> raise FeishuAuthException("获取 Token 失败", {"code": 10001, "msg": "invalid code"})
    """
    pass


class SandboxInitException(OpenClawBridgeException):
    """
    沙盒初始化相关异常
    
    触发场景：
    - 模板目录不存在，无法复制
    - 沙盒目录创建失败（权限不足、磁盘空间不足）
    - 用户状态文件损坏无法恢复
    - 项目目录结构升级失败
    
    Example:
        >>> raise SandboxInitException("模板目录不存在", "/path/to/templates")
    """
    pass


class ConfigLoadException(OpenClawBridgeException):
    """
    配置加载相关异常
    
    触发场景：
    - prompt.json 解析失败（JSON 格式错误）
    - 必要配置字段缺失（如缺少 tts 或 dialog 字段）
    - 配置文件损坏或为空
    - status.json 读取失败
    
    Example:
        >>> raise ConfigLoadException("配置文件解析失败", {"file": "prompt.json", "error": "JSONDecodeError"})
    """
    pass


class OpenClawNotifyException(OpenClawBridgeException):
    """
    OpenClaw 通知相关异常
    
    触发场景：
    - 记忆结算通知发送失败
    - HTTP 请求超时或网络错误
    - OpenClaw Gateway 返回错误状态码
    - 认证失败（Token 无效）
    
    Example:
        >>> raise OpenClawNotifyException("通知发送失败", {"status_code": 500, "response": "Internal Server Error"})
    """
    pass


class FileWriteException(OpenClawBridgeException):
    """
    文件写入相关异常
    
    触发场景：
    - 原子写入过程中临时文件创建失败
    - 文件权限不足
    - 磁盘空间不足
    - os.replace 原子操作失败
    
    Example:
        >>> raise FileWriteException("原子写入失败", {"file": "status.json", "reason": "permission denied"})
    """
    pass