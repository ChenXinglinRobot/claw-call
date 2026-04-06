"""
第二阶段：网络层剥离 - 模块测试

测试 TokenManager, FeishuClient, OpenClawClient 的导入和基本结构。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
import inspect

# 测试模块导入
print("=" * 60)
print("第二阶段：网络层剥离 - 模块导入测试")
print("=" * 60)

# 1. 测试 TokenManager
from openclaw_bridge import TokenManager

print("\n✅ TokenManager 导入成功")
print(f"   - 方法签名:")
print(f"     - __init__: {inspect.signature(TokenManager.__init__)}")
print(f"     - get_tenant_access_token: {inspect.signature(TokenManager.get_tenant_access_token)}")
print(f"     - exchange_code_for_user_token: {inspect.signature(TokenManager.exchange_code_for_user_token)}")
print(f"     - _get_cached_token: {inspect.signature(TokenManager._get_cached_token)}")
print(f"     - _set_cached_token: {inspect.signature(TokenManager._set_cached_token)}")

# 验证缓存抽象层存在
assert hasattr(TokenManager, '_get_cached_token'), "缺失 _get_cached_token 方法"
assert hasattr(TokenManager, '_set_cached_token'), "缺失 _set_cached_token 方法"
print("   ✓ 缓存抽象层方法已实现（为 Redis 扩展预留）")

# 2. 测试 FeishuClient
from openclaw_bridge import FeishuClient

print("\n✅ FeishuClient 导入成功")
print(f"   - 方法签名:")
print(f"     - __init__: {inspect.signature(FeishuClient.__init__)}")
print(f"     - authenticate_user: {inspect.signature(FeishuClient.authenticate_user)}")
print(f"     - send_text_message: {inspect.signature(FeishuClient.send_text_message)}")

# 3. 测试 OpenClawClient
from openclaw_bridge import OpenClawClient

print("\n✅ OpenClawClient 导入成功")
print(f"   - 方法签名:")
print(f"     - __init__: {inspect.signature(OpenClawClient.__init__)}")
print(f"     - get_skill_for_project: {inspect.signature(OpenClawClient.get_skill_for_project)}")
print(f"     - notify_memory_settlement: {inspect.signature(OpenClawClient.notify_memory_settlement)}")

# 4. 测试依赖注入模式
print("\n" + "=" * 60)
print("依赖注入模式验证")
print("=" * 60)

# 创建模拟的 httpx.AsyncClient
mock_client = httpx.AsyncClient(timeout=15.0)

# TokenManager 接收 http_client
token_manager = TokenManager(
    app_id="test_app_id",
    app_secret="test_secret",
    http_client=mock_client
)
print("\n✅ TokenManager 依赖注入成功（接收 httpx.AsyncClient）")

# FeishuClient 接收 TokenManager 和 http_client
feishu_client = FeishuClient(
    token_manager=token_manager,
    http_client=mock_client
)
print("✅ FeishuClient 依赖注入成功（接收 TokenManager + httpx.AsyncClient）")

# OpenClawClient 接收 http_client 和配置参数
openclaw_client = OpenClawClient(
    http_client=mock_client,
    gateway_url="http://localhost:12392/v1/chat/completions",
    token="test_token",
    agent_id="test_agent",
    project_skill_map={"vocab_project": "vocab-learning-planner"}
)
print("✅ OpenClawClient 依赖注入成功（接收 httpx.AsyncClient + 配置参数）")

# 5. 测试 project_skill_map 动态映射
print("\n" + "=" * 60)
print("项目-Skill 动态映射验证")
print("=" * 60)

skill = openclaw_client.get_skill_for_project("vocab_project")
print(f"\n vocab_project -> {skill}")
assert skill == "vocab-learning-planner", "Skill 映射错误"

# 测试默认值
skill_default = openclaw_client.get_skill_for_project("unknown_project")
print(f" unknown_project -> {skill_default} (默认)")

print("\n" + "=" * 60)
print("🎉 第二阶段网络层模块测试全部通过！")
print("=" * 60)

# 关闭 mock client
import asyncio
asyncio.run(mock_client.aclose())