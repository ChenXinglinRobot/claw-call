"""
测试脚本：验证多场景动态路由与沙盒隔离架构 (V2.1)

测试内容：
1. 验证沙盒目录结构正确性
2. 验证新用户自动初始化机制
3. 验证动态配置读取（根据用户状态）
4. 验证项目切换功能
5. 验证记忆文件隔离写入
6. 🆕 V2.1: 验证状态快照机制（并发错位防护）
"""

import asyncio
import os
import json
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openclaw_bridge import OpenClawBridge


def test_directory_structure():
    """测试一：验证沙盒目录结构"""
    print("\n" + "="*60)
    print("测试一：验证沙盒目录结构")
    print("="*60)
    
    base_dir = "memory"
    templates_dir = os.path.join(base_dir, "templates")
    users_dir = os.path.join(base_dir, "users")
    
    # 检查 templates 目录
    vocab_template = os.path.join(templates_dir, "vocab_project", "prompt.json")
    interview_template = os.path.join(templates_dir, "interview_project", "prompt.json")
    
    assert os.path.exists(vocab_template), f"模板文件缺失: {vocab_template}"
    assert os.path.exists(interview_template), f"模板文件缺失: {interview_template}"
    print(f"✅ templates/vocab_project/prompt.json 存在")
    print(f"✅ templates/interview_project/prompt.json 存在")
    
    # 检查测试用户目录
    test_user_dir = os.path.join(users_dir, "test_user_123")
    status_file = os.path.join(test_user_dir, "status.json")
    vocab_dir = os.path.join(test_user_dir, "vocab_project")
    interview_dir = os.path.join(test_user_dir, "interview_project")
    
    assert os.path.exists(test_user_dir), f"测试用户目录缺失: {test_user_dir}"
    assert os.path.exists(status_file), f"状态文件缺失: {status_file}"
    assert os.path.exists(vocab_dir), f"词汇项目目录缺失: {vocab_dir}"
    assert os.path.exists(interview_dir), f"访谈项目目录缺失: {interview_dir}"
    print(f"✅ 测试用户目录结构完整")
    
    # 验证状态文件内容
    with open(status_file, 'r', encoding='utf-8') as f:
        status = json.load(f)
    assert "active_project" in status, "状态文件缺少 active_project 字段"
    print(f"✅ 状态文件有效: active_project = {status['active_project']}")
    
    return True


async def test_new_user_initialization():
    """测试二：验证新用户自动初始化机制"""
    print("\n" + "="*60)
    print("测试二：验证新用户自动初始化机制")
    print("="*60)
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir="memory"
    )
    
    test_new_user = "test_auto_init_user_001"
    user_sandbox = os.path.join("memory", "users", test_new_user)
    
    # 清理可能存在的旧测试目录
    import shutil
    if os.path.exists(user_sandbox):
        shutil.rmtree(user_sandbox)
    
    # 验证目录不存在
    assert not os.path.exists(user_sandbox), "测试用户目录应不存在"
    print(f"📂 确认测试用户目录不存在: {user_sandbox}")
    
    # 执行初始化
    result = bridge._ensure_user_sandbox(test_new_user)
    assert result, "新用户初始化失败"
    print(f"✅ 新用户初始化成功")
    
    # 验证初始化结果
    assert os.path.exists(user_sandbox), "用户沙盒目录未创建"
    status_file = os.path.join(user_sandbox, "status.json")
    assert os.path.exists(status_file), "状态文件未创建"
    
    with open(status_file, 'r', encoding='utf-8') as f:
        status = json.load(f)
    
    assert status["active_project"] == "vocab", f"默认项目应为 vocab，实际为 {status['active_project']}"
    print(f"✅ 默认激活项目: {status['active_project']}")
    
    # 验证项目目录复制
    vocab_dir = os.path.join(user_sandbox, "vocab_project")
    interview_dir = os.path.join(user_sandbox, "interview_project")
    assert os.path.exists(vocab_dir), "vocab_project 目录未复制"
    assert os.path.exists(interview_dir), "interview_project 目录未复制"
    print(f"✅ 项目目录复制成功")
    
    # 清理测试目录
    shutil.rmtree(user_sandbox)
    print(f"🧹 已清理测试目录")
    
    await bridge.close()
    return True


async def test_dynamic_config_loading():
    """测试三：验证动态配置读取"""
    print("\n" + "="*60)
    print("测试三：验证动态配置读取")
    print("="*60)
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir="memory"
    )
    
    # 使用已存在的测试用户
    test_user = "test_user_123"
    
    # 读取当前状态
    status = await bridge._read_user_status(test_user)
    print(f"📋 当前状态: {status}")
    
    # 加载配置
    config = await bridge._load_prompt_config(test_user)
    print(f"✅ 配置加载成功")
    print(f"   - bot_name: {config.get('dialog', {}).get('bot_name')}")
    print(f"   - speaker: {config.get('tts', {}).get('speaker')}")
    
    # 验证配置结构
    assert "tts" in config, "配置缺少 tts 字段"
    assert "dialog" in config, "配置缺少 dialog 字段"
    assert "audio_config" in config["tts"], "配置缺少 audio_config"
    print(f"✅ 配置结构验证通过")
    
    await bridge.close()
    return True


async def test_project_switching():
    """测试四：验证项目切换功能"""
    print("\n" + "="*60)
    print("测试四：验证项目切换功能")
    print("="*60)
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir="memory"
    )
    
    test_user = "test_user_123"
    
    # 读取初始状态
    status_before = await bridge._read_user_status(test_user)
    print(f"📋 切换前状态: active_project = {status_before['active_project']}")
    
    # 切换到 interview 项目
    result = await bridge.switch_project(test_user, "interview")
    assert result, "项目切换失败"
    print(f"✅ 项目切换成功: vocab -> interview")
    
    # 验证切换后的状态
    status_after = await bridge._read_user_status(test_user)
    assert status_after["active_project"] == "interview", f"切换后状态错误: {status_after['active_project']}"
    print(f"📋 切换后状态: active_project = {status_after['active_project']}")
    
    # 加载新配置验证
    config = await bridge._load_prompt_config(test_user)
    assert config["dialog"]["bot_name"] == "时光记录员", "配置未正确切换"
    print(f"✅ 配置已同步切换: bot_name = {config['dialog']['bot_name']}")
    
    # 切换回 vocab 项目
    result = await bridge.switch_project(test_user, "vocab")
    assert result, "项目切回失败"
    print(f"✅ 项目切回成功: interview -> vocab")
    
    # 验证切回后的状态
    status_final = await bridge._read_user_status(test_user)
    assert status_final["active_project"] == "vocab", f"切回后状态错误: {status_final['active_project']}"
    print(f"📋 最终状态: active_project = {status_final['active_project']}")
    
    await bridge.close()
    return True


async def test_memory_isolation():
    """测试五：验证记忆文件隔离写入"""
    print("\n" + "="*60)
    print("测试五：验证记忆文件隔离写入")
    print("="*60)
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir="memory"
    )
    
    test_user = "test_user_123"
    
    # 确保当前是 vocab 项目
    await bridge.switch_project(test_user, "vocab")
    
    # 写入 vocab 项目的记忆
    vocab_history = [
        {"role": "user", "text": "我想学单词 abandon"},
        {"role": "assistant", "text": "好的，abandon 意思是放弃、抛弃"}
    ]
    await bridge.analyze_and_save_memory(test_user, vocab_history)
    print(f"✅ vocab 项目记忆写入完成")
    
    # 切换到 interview 项目
    await bridge.switch_project(test_user, "interview")
    
    # 写入 interview 项目的记忆
    interview_history = [
        {"role": "user", "text": "我想聊聊我的童年"},
        {"role": "assistant", "text": "好的，请说说您小时候印象最深的事情"}
    ]
    await bridge.analyze_and_save_memory(test_user, interview_history)
    print(f"✅ interview 项目记忆写入完成")
    
    # 验证文件隔离
    vocab_memory_path = os.path.join("memory", "users", test_user, "vocab_project", "memory_log.md")
    interview_memory_path = os.path.join("memory", "users", test_user, "interview_project", "memory_log.md")
    
    with open(vocab_memory_path, 'r', encoding='utf-8') as f:
        vocab_content = f.read()
    
    with open(interview_memory_path, 'r', encoding='utf-8') as f:
        interview_content = f.read()
    
    # 验证内容隔离
    assert "abandon" in vocab_content, "vocab 记忆文件应包含 abandon"
    assert "童年" in interview_content, "interview 记忆文件应包含 童年"
    assert "abandon" not in interview_content, "interview 记忆文件不应包含 abandon"
    assert "童年" not in vocab_content, "vocab 记忆文件不应包含 童年"
    
    print(f"✅ 记忆文件隔离验证通过")
    print(f"   - vocab_memory 包含: abandon ✅")
    print(f"   - interview_memory 包含: 童年 ✅")
    print(f"   - 无交叉污染 ✅")
    
    await bridge.close()
    return True


async def test_full_session_simulation():
    """测试六：完整会话模拟（V2.1 状态快照验证）"""
    print("\n" + "="*60)
    print("测试六：完整会话模拟（generate_doubao_config + 状态快照）")
    print("="*60)
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir="memory"
    )
    
    test_user = "test_user_123"
    
    # 切换到 vocab 项目
    await bridge.switch_project(test_user, "vocab")
    
    # 🆕 V2.1: 生成豆包配置，返回元组 (config, project_snapshot)
    config, project_snapshot = await bridge.generate_doubao_config(test_user)
    
    print(f"✅ 豆包配置生成成功")
    print(f"   - bot_name: {config['dialog']['bot_name']}")
    print(f"   - speaker: {config['tts']['speaker']}")
    print(f"   - 🆕 project_snapshot: {project_snapshot}")
    
    # 验证快照正确
    assert project_snapshot == "vocab_project", f"快照应为 vocab_project，实际为 {project_snapshot}"
    print(f"✅ 状态快照验证通过")
    
    # 验证 system_role 包含记忆内容
    system_role = config['dialog']['system_role']
    assert "英语学习助手" in system_role, "system_role 应包含人设"
    print(f"✅ system_role 包含人设信息")
    
    # 切换到 interview 项目
    await bridge.switch_project(test_user, "interview")
    
    # 生成新的豆包配置
    config2, project_snapshot2 = await bridge.generate_doubao_config(test_user)
    
    print(f"✅ 切换后配置重新生成")
    print(f"   - bot_name: {config2['dialog']['bot_name']}")
    print(f"   - speaker: {config2['tts']['speaker']}")
    print(f"   - 🆕 project_snapshot: {project_snapshot2}")
    
    # 验证配置已切换
    assert config2['dialog']['bot_name'] == "时光记录员", "配置未正确切换"
    assert config2['tts']['speaker'] != config['tts']['speaker'], "音色应不同"
    assert project_snapshot2 == "interview_project", f"快照应为 interview_project，实际为 {project_snapshot2}"
    print(f"✅ 配置切换验证通过")
    
    await bridge.close()
    return True


async def test_snapshot_concurrency_protection():
    """测试七：🆕 V2.1 验证状态快照防止并发错位"""
    print("\n" + "="*60)
    print("测试七：V2.1 状态快照并发错位防护")
    print("="*60)
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir="memory"
    )
    
    test_user = "test_user_123"
    
    # 1. 会话开始时，用户处于 vocab 项目
    await bridge.switch_project(test_user, "vocab")
    config, snapshot = await bridge.generate_doubao_config(test_user)
    print(f"📋 会话开始时快照: {snapshot}")
    assert snapshot == "vocab_project", "快照应为 vocab_project"
    
    # 2. 模拟通话期间，外部修改了 status.json（如 OpenClaw 切换了项目）
    await bridge.switch_project(test_user, "interview")
    print(f"⚡ 模拟通话期间状态被外部修改: vocab -> interview")
    
    # 3. 验证实时读取会得到新项目
    status_now = await bridge._read_user_status(test_user)
    print(f"📋 当前磁盘状态: {status_now['active_project']}")
    assert status_now['active_project'] == "interview", "磁盘状态已变为 interview"
    
    # 4. 但使用快照回写记忆时，应写入原始项目（vocab）
    dialog_history = [
        {"role": "user", "text": "测试快照机制的单词"},
        {"role": "assistant", "text": "快照确保记忆写入正确的项目"}
    ]
    
    # 使用快照回写
    await bridge.analyze_and_save_memory(test_user, dialog_history, project_snapshot=snapshot)
    print(f"✅ 使用快照回写记忆: {snapshot}")
    
    # 5. 验证记忆被写入了 vocab_project（快照指定的项目），而非 interview_project
    vocab_memory_path = os.path.join("memory", "users", test_user, "vocab_project", "memory_log.md")
    interview_memory_path = os.path.join("memory", "users", test_user, "interview_project", "memory_log.md")
    
    with open(vocab_memory_path, 'r', encoding='utf-8') as f:
        vocab_content = f.read()
    
    with open(interview_memory_path, 'r', encoding='utf-8') as f:
        interview_content = f.read()
    
    # 验证：快照机制确保写入正确位置
    assert "快照确保记忆写入正确的项目" in vocab_content, "vocab 记忆文件应包含快照回写的内容"
    assert "快照确保记忆写入正确的项目" not in interview_content, "interview 记忆文件不应包含快照回写的内容"
    
    print(f"✅ 快照机制验证通过：记忆正确写入 vocab_project")
    print(f"   - 即使磁盘状态已变为 interview，快照确保回写正确")
    
    await bridge.close()
    return True


def print_final_summary():
    """打印最终总结"""
    print("\n" + "="*60)
    print("🎉 所有测试通过！新架构验证成功")
    print("="*60)
    print("""
架构变更总结：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 目录结构变更：
   - 移除：项目根目录 prompt_config.json（全局配置）
   - 新增：memory/templates/（静态只读模板库）
   - 新增：memory/users/{user_id}/（用户独立沙盒）

🔄 核心流程变更：
   1. 新用户首次连接 → 自动从 templates 复制初始化沙盒
   2. 配置读取 → 根据 status.json 的 active_project 动态加载
   3. 记忆回写 → 精确写入当前活跃项目的 memory_log.md
   4. 项目切换 → 原子写入 status.json，实现无缝切换

✨ 新增能力：
   - 多场景支持：vocab（英语学习）/ interview（长辈访谈）
   - 物理隔离：不同项目的数据完全独立，无交叉污染
   - 动态切换：无需重启服务，修改 status.json 即可切换场景
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)


async def main():
    """运行所有测试"""
    print("\n" + "🚀 开始验证多场景动态路由与沙盒隔离架构 (V2.1)")
    print("="*60)
    
    try:
        # 测试一：目录结构验证
        assert test_directory_structure(), "测试一失败"
        
        # 测试二：新用户初始化
        assert await test_new_user_initialization(), "测试二失败"
        
        # 测试三：动态配置读取
        assert await test_dynamic_config_loading(), "测试三失败"
        
        # 测试四：项目切换
        assert await test_project_switching(), "测试四失败"
        
        # 测试五：记忆隔离
        assert await test_memory_isolation(), "测试五失败"
        
        # 测试六：完整会话模拟（V2.1 快照验证）
        assert await test_full_session_simulation(), "测试六失败"
        
        # 🆕 测试七：V2.1 状态快照并发错位防护
        assert await test_snapshot_concurrency_protection(), "测试七失败"
        
        # 打印总结
        print_final_summary()
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)