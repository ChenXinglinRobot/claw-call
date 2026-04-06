"""
OpenClaw Bridge 终极集成测试

验证 CoreBridge（作为 OpenClawBridge 导入）能否正确协调所有底层 Manager 和 Client。
包含：
1. test_user_lifecycle_integration：完整的用户生命周期测试
2. test_core_bridge_concurrency：并发场景下的 GC 防护验证
"""

import os
import json
import asyncio
import tempfile
import shutil
from unittest.mock import AsyncMock, patch
from typing import Dict, Any

import pytest
import pytest_asyncio

from openclaw_bridge import OpenClawBridge


# ============ pytest-asyncio 配置 ============
pytestmark = pytest.mark.asyncio(loop_scope="function")


# ============ 测试用模板配置 ============

MINIMAL_PROMPT_CONFIG: Dict[str, Any] = {
    "tts": {
        "audio_config": {
            "channel": 1,
            "format": "pcm_s16le",
            "sample_rate": 24000
        },
        "speaker": "zh_female_xiaohe_jupiter_bigtts"
    },
    "dialog": {
        "bot_name": "测试机器人",
        "system_role": "你是一个测试助手。",
        "speaking_style": "简洁",
        "extra": {
            "input_mod": "keep_alive",
            "model": "1.2.1.1"
        }
    }
}


# ============ Fixture：环境隔离与前置准备 ============

@pytest_asyncio.fixture
async def isolated_test_env():
    """
    创建隔离的测试环境
    
    包含：
    - 临时目录作为 memory_dir
    - 完整的模板文件结构
    - 实例化的 CoreBridge
    - 网络 Mock
    """
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="openclaw_test_")
    
    try:
        # 创建模板目录结构
        templates_dir = os.path.join(temp_dir, "templates")
        vocab_project_dir = os.path.join(templates_dir, "vocab_project")
        os.makedirs(vocab_project_dir, exist_ok=True)
        
        # 写入最小有效的 prompt.json
        prompt_path = os.path.join(vocab_project_dir, "prompt.json")
        with open(prompt_path, 'w', encoding='utf-8') as f:
            json.dump(MINIMAL_PROMPT_CONFIG, f, ensure_ascii=False, indent=2)
        
        # 创建 interview_project 模板（用于切换项目测试）
        interview_project_dir = os.path.join(templates_dir, "interview_project")
        os.makedirs(interview_project_dir, exist_ok=True)
        interview_prompt_path = os.path.join(interview_project_dir, "prompt.json")
        with open(interview_prompt_path, 'w', encoding='utf-8') as f:
            interview_config = MINIMAL_PROMPT_CONFIG.copy()
            interview_config["dialog"]["bot_name"] = "访谈机器人"
            json.dump(interview_config, f, ensure_ascii=False, indent=2)
        
        # 实例化 CoreBridge
        bridge = OpenClawBridge(
            feishu_app_id="test_app_id",
            feishu_app_secret="test_app_secret",
            memory_dir=temp_dir,
            openclaw_gateway_url="http://fake-gateway.example.com",
            openclaw_token="fake_token",
            openclaw_agent_id="test_agent"
        )
        
        # Mock FeishuClient.authenticate_user
        bridge._feishu.authenticate_user = AsyncMock(return_value="test_user_123")
        
        # Mock OpenClawClient.notify_memory_settlement
        async def mock_notify_with_delay(*args, **kwargs):
            """模拟延迟 0.1 秒的通知，用于验证 GC 防护"""
            await asyncio.sleep(0.1)
            return True
        
        bridge._openclaw.notify_memory_settlement = AsyncMock(
            side_effect=mock_notify_with_delay
        )
        
        yield {
            "bridge": bridge,
            "temp_dir": temp_dir,
            "templates_dir": templates_dir
        }
    
    finally:
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


# ============ 测试 1：完整用户生命周期 ============

@pytest.mark.asyncio
async def test_user_lifecycle_integration(isolated_test_env):
    """
    测试完整的用户生命周期
    
    流程：
    1. 登录：调用 authenticate_and_initialize
    2. 配置：调用 generate_doubao_config
    3. 保存：调用 save_dialog_and_notify，验证 GC 防护
    4. 切换：调用 switch_project
    5. 关闭：调用 close，验证资源清理
    """
    bridge = isolated_test_env["bridge"]
    temp_dir = isolated_test_env["temp_dir"]
    
    user_id = "test_user_123"
    
    # ============ 步骤 1：登录 ============
    result_user_id = await bridge.authenticate_and_initialize("fake_code")
    
    # 断言 1.1：返回正确的 user_id
    assert result_user_id == user_id, f"期望返回 {user_id}，实际返回 {result_user_id}"
    
    # 断言 1.2：status.json 被正确创建
    status_path = bridge.sandbox.get_user_status_path(user_id)
    assert os.path.exists(status_path), "status.json 未被创建"
    
    with open(status_path, 'r', encoding='utf-8') as f:
        status = json.load(f)
    assert "active_project" in status, "status.json 缺少 active_project 字段"
    
    print("✅ 步骤 1 通过：登录成功，status.json 已创建")
    
    # ============ 步骤 2：配置 ============
    config, project_name = await bridge.generate_doubao_config(user_id)
    
    # 断言 2.1：配置被成功读取
    assert isinstance(config, dict), "config 应为字典类型"
    assert "tts" in config, "config 缺少 tts 字段"
    assert "dialog" in config, "config 缺少 dialog 字段"
    
    # 断言 2.2：项目名称正确
    assert project_name == "vocab_project", f"期望项目名为 vocab_project，实际为 {project_name}"
    
    # 断言 2.3：配置是深拷贝，修改不影响原始数据
    config["dialog"]["bot_name"] = "被修改的名字"
    config_reloaded, _ = await bridge.generate_doubao_config(user_id)
    assert config_reloaded["dialog"]["bot_name"] == "测试机器人", "配置深拷贝失败，原始数据被污染"
    
    print("✅ 步骤 2 通过：配置读取成功，深拷贝验证通过")
    
    # ============ 步骤 3：保存与 GC 验证 ============
    dialog_history = [
        {"role": "user", "text": "你好"},
        {"role": "assistant", "text": "你好！有什么可以帮助你的吗？"}
    ]
    
    await bridge.save_dialog_and_notify(user_id, dialog_history, project_name)
    
    # 断言 3.1：memory_log.md 被成功写入
    memory_log_path = bridge.sandbox.get_memory_log_path(user_id, project_name)
    assert os.path.exists(memory_log_path), "memory_log.md 未被创建"
    
    with open(memory_log_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "你好" in content, "对话内容未写入 memory_log.md"
    assert "🧑 User" in content or "User" in content, "对话格式不正确"
    
    # 断言 3.2：GC 防护验证 - Task 被成功保护
    assert len(bridge._background_tasks) == 1, \
        f"期望 _background_tasks 为 1，实际为 {len(bridge._background_tasks)}"
    
    print("✅ 步骤 3 通过：对话已保存，GC 防护生效")
    
    # ============ 步骤 4：切换项目 ============
    switch_result = await bridge.switch_project(user_id, "interview")
    
    # 断言 4.1：切换成功
    assert switch_result is True, "项目切换失败"
    
    # 断言 4.2：status.json 已更新
    with open(status_path, 'r', encoding='utf-8') as f:
        updated_status = json.load(f)
    assert updated_status["active_project"] == "interview", \
        f"期望 active_project 为 interview，实际为 {updated_status['active_project']}"
    
    print("✅ 步骤 4 通过：项目切换成功")
    
    # ============ 步骤 5：优雅关闭 ============
    await bridge.close()
    
    # 断言 5.1：后台任务被清理
    assert len(bridge._background_tasks) == 0, \
        f"关闭后 _background_tasks 应为 0，实际为 {len(bridge._background_tasks)}"
    
    print("✅ 步骤 5 通过：优雅关闭完成，资源已清理")
    print("\n🎉 test_user_lifecycle_integration 全部通过！")


# ============ 测试 2：并发场景测试 ============

@pytest.mark.asyncio
async def test_core_bridge_concurrency(isolated_test_env):
    """
    测试并发场景下的 GC 防护机制
    
    流程：
    1. 同时发起 10 次 save_dialog_and_notify 调用
    2. 断言执行瞬间 _background_tasks 为 10
    3. 调用 close() 等待完成
    4. 断言任务被全部清空
    5. 断言 memory_log.md 包含 10 条记录
    """
    bridge = isolated_test_env["bridge"]
    temp_dir = isolated_test_env["temp_dir"]
    
    user_id = "test_user_123"
    
    # 先完成登录和初始化
    await bridge.authenticate_and_initialize("fake_code")
    _, project_name = await bridge.generate_doubao_config(user_id)
    
    # 准备 10 组不同的对话历史
    dialog_histories = [
        [
            {"role": "user", "text": f"这是第 {i+1} 次对话"},
            {"role": "assistant", "text": f"收到第 {i+1} 次对话"}
        ]
        for i in range(10)
    ]
    
    # ============ 并发执行 10 次保存 ============
    # 使用 asyncio.gather 同时发起
    tasks = [
        bridge.save_dialog_and_notify(user_id, dialog, project_name)
        for dialog in dialog_histories
    ]
    
    # 立即发起所有调用（不等待）
    await asyncio.gather(*tasks)
    
    # 断言 1：执行完毕瞬间，_background_tasks 应为 10
    assert len(bridge._background_tasks) == 10, \
        f"期望并发时 _background_tasks 为 10，实际为 {len(bridge._background_tasks)}"
    
    print(f"✅ 并发测试：成功捕获 10 个后台任务")
    
    # ============ 优雅关闭 ============
    await bridge.close()
    
    # 断言 2：任务被全部清空
    assert len(bridge._background_tasks) == 0, \
        f"关闭后 _background_tasks 应为 0，实际为 {len(bridge._background_tasks)}"
    
    print("✅ 关闭测试：所有后台任务已清理")
    
    # ============ 验证文件写入 ============
    memory_log_path = bridge.sandbox.get_memory_log_path(user_id, project_name)
    
    with open(memory_log_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 断言 3：10 条记录全部写入
    for i in range(10):
        assert f"第 {i+1} 次对话" in content, f"第 {i+1} 条对话记录未写入"
    
    print("✅ 文件验证：10 条对话记录全部写入 memory_log.md")
    print("\n🎉 test_core_bridge_concurrency 全部通过！")


# ============ 入口：直接运行测试 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])