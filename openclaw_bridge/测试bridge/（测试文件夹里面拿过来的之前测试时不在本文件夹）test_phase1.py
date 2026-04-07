"""
第一阶段重构验证测试

测试目标：
1. 验证 OpenClawBridge 成功集成 SandboxManager
2. 验证公共接口通过文件系统产生正确结果
3. 不调用任何私有方法，仅验证文件层面表现

运行方式：python 测试文件/test_phase1.py
"""

import os
import sys
import json
import shutil
import asyncio
import tempfile
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from openclaw_bridge import OpenClawBridge, SandboxManager


# ============ 测试辅助函数 ============

def create_minimal_templates(templates_dir: str) -> None:
    """
    创建最小化的模板目录结构
    
    Args:
        templates_dir: 模板目录路径
    """
    # 创建 vocab_project 模板
    vocab_dir = os.path.join(templates_dir, "vocab_project")
    os.makedirs(vocab_dir, exist_ok=True)
    
    vocab_prompt = {
        "tts": {
            "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000},
            "speaker": "zh_female_xiaohe_jupiter_bigtts"
        },
        "dialog": {
            "bot_name": "小爪",
            "system_role": "你是小爪，一个耐心且专业的英语学习助手。",
            "speaking_style": "温柔耐心，像朋友一样聊天",
            "extra": {"input_mod": "keep_alive", "model": "1.2.1.1"}
        }
    }
    
    with open(os.path.join(vocab_dir, "prompt.json"), 'w', encoding='utf-8') as f:
        json.dump(vocab_prompt, f, ensure_ascii=False, indent=4)
    
    # 创建必要的子目录
    os.makedirs(os.path.join(vocab_dir, "raw_archives"), exist_ok=True)
    os.makedirs(os.path.join(vocab_dir, "episodes"), exist_ok=True)
    
    # 创建 master_profile.md
    with open(os.path.join(vocab_dir, "master_profile.md"), 'w', encoding='utf-8') as f:
        f.write("# vocab 全局大纲\n\n> 本文件由系统自动生成。\n")
    
    # 创建 interview_project 模板
    interview_dir = os.path.join(templates_dir, "interview_project")
    os.makedirs(interview_dir, exist_ok=True)
    
    interview_prompt = {
        "tts": {
            "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000},
            "speaker": "zh_female_xiaohe_jupiter_bigtts"
        },
        "dialog": {
            "bot_name": "小爪",
            "system_role": "你是小爪，一个专业的访谈助手。",
            "speaking_style": "专业且亲切",
            "extra": {"input_mod": "keep_alive", "model": "1.2.1.1"}
        }
    }
    
    with open(os.path.join(interview_dir, "prompt.json"), 'w', encoding='utf-8') as f:
        json.dump(interview_prompt, f, ensure_ascii=False, indent=4)
    
    os.makedirs(os.path.join(interview_dir, "raw_archives"), exist_ok=True)
    os.makedirs(os.path.join(interview_dir, "episodes"), exist_ok=True)
    
    with open(os.path.join(interview_dir, "master_profile.md"), 'w', encoding='utf-8') as f:
        f.write("# interview 全局大纲\n\n> 本文件由系统自动生成。\n")


def print_test_header(test_name: str) -> None:
    """打印测试标题"""
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print('='*60)


def print_result(passed: bool, message: str) -> None:
    """打印测试结果"""
    status = "✅ 通过" if passed else "❌ 失败"
    print(f"  {status}: {message}")


# ============ 测试用例 ============

async def test_1_bridge_instantiation(temp_dir: str) -> bool:
    """
    测试 1：实例化 OpenClawBridge，验证其内部是否成功挂载了 SandboxManager 实例
    """
    print_test_header("测试 1：OpenClawBridge 实例化与 SandboxManager 集成")
    
    # 创建模板目录
    templates_dir = os.path.join(temp_dir, "templates")
    create_minimal_templates(templates_dir)
    
    # 实例化 OpenClawBridge
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir=temp_dir
    )
    
    # 验证 1：bridge.sandbox 是否存在
    has_sandbox = hasattr(bridge, 'sandbox') and bridge.sandbox is not None
    print_result(has_sandbox, "bridge.sandbox 属性存在")
    
    # 验证 2：bridge.sandbox 是否为 SandboxManager 实例
    is_correct_type = isinstance(bridge.sandbox, SandboxManager)
    print_result(is_correct_type, f"bridge.sandbox 是 SandboxManager 实例")
    
    # 验证 3：SandboxManager 的 memory_dir 是否正确设置
    correct_dir = bridge.sandbox.memory_dir == temp_dir
    print_result(correct_dir, f"SandboxManager.memory_dir 正确设置为 {temp_dir}")
    
    # 验证 4：核心目录是否已创建
    users_dir_exists = os.path.exists(os.path.join(temp_dir, "users"))
    print_result(users_dir_exists, "核心目录 'users/' 已创建")
    
    all_passed = has_sandbox and is_correct_type and correct_dir and users_dir_exists
    
    print(f"\n  📊 测试 1 结果: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")
    return all_passed


async def test_2_switch_project(temp_dir: str) -> bool:
    """
    测试 2：调用 bridge.switch_project()，验证 status.json 是否被正确创建/修改
    """
    print_test_header("测试 2：switch_project() 与 status.json 原子写入")
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir=temp_dir
    )
    
    test_user_id = "test_user_001"
    
    # 步骤 1：确保用户沙盒存在（模拟用户首次访问）
    bridge.sandbox.ensure_user_sandbox(test_user_id)
    print_result(True, f"用户沙盒已初始化: {test_user_id}")
    
    # 步骤 2：调用 switch_project（应该切换到 interview_project）
    result = await bridge.switch_project(test_user_id, "interview")
    print_result(result, "switch_project('interview') 返回 True")
    
    # 验证 1：status.json 文件存在
    status_path = bridge.sandbox.get_user_status_path(test_user_id)
    status_exists = os.path.exists(status_path)
    print_result(status_exists, f"status.json 文件存在: {status_path}")
    
    # 验证 2：status.json 内容正确
    with open(status_path, 'r', encoding='utf-8') as f:
        status_content = json.load(f)
    
    correct_active_project = status_content.get("active_project") == "interview"
    print_result(correct_active_project, f"active_project 正确为 'interview'")
    
    # 验证 3：原子写入特征 - 无 .tmp 残留文件
    tmp_files = [f for f in os.listdir(os.path.dirname(status_path)) if f.endswith('.tmp')]
    no_tmp残留 = len(tmp_files) == 0
    print_result(no_tmp残留, f"无 .tmp 残留文件（原子写入正常）")
    
    all_passed = result and status_exists and correct_active_project and no_tmp残留
    
    print(f"\n  📊 测试 2 结果: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")
    return all_passed


async def test_3_analyze_and_save_memory(temp_dir: str) -> bool:
    """
    测试 3：调用 bridge.analyze_and_save_memory() 写入模拟对话，验证 memory_log.md 是否被正确追加
    """
    print_test_header("测试 3：analyze_and_save_memory() 与 memory_log.md 追加写入")
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir=temp_dir
    )
    
    test_user_id = "test_user_002"
    
    # 确保用户沙盒存在
    bridge.sandbox.ensure_user_sandbox(test_user_id)
    
    # 获取 memory_log.md 路径
    memory_path = bridge.sandbox.get_memory_log_path(test_user_id, "vocab_project")
    
    # 步骤 1：首次写入对话
    dialog_history_1 = [
        {"role": "user", "text": "你好，我想学英语"},
        {"role": "assistant", "text": "你好！很高兴能帮助你学习英语。"}
    ]
    
    await bridge.analyze_and_save_memory(test_user_id, dialog_history_1, "vocab_project")
    print_result(True, "首次对话已写入")
    
    # 验证 1：memory_log.md 文件存在
    memory_exists = os.path.exists(memory_path)
    print_result(memory_exists, f"memory_log.md 文件存在: {memory_path}")
    
    # 验证 2：内容包含首次对话
    with open(memory_path, 'r', encoding='utf-8') as f:
        content_1 = f.read()
    
    has_first_dialog = "你好，我想学英语" in content_1 and "你好！很高兴能帮助你学习英语" in content_1
    print_result(has_first_dialog, "首次对话内容正确写入")
    
    # 步骤 2：追加第二次对话
    dialog_history_2 = [
        {"role": "user", "text": "今天我想背单词"},
        {"role": "assistant", "text": "好的，让我们开始今天的单词学习吧！"}
    ]
    
    await bridge.analyze_and_save_memory(test_user_id, dialog_history_2, "vocab_project")
    print_result(True, "第二次对话已追加")
    
    # 验证 3：内容包含两次对话
    with open(memory_path, 'r', encoding='utf-8') as f:
        content_2 = f.read()
    
    has_both_dialogs = "你好，我想学英语" in content_2 and "今天我想背单词" in content_2
    print_result(has_both_dialogs, "两次对话内容均存在（追加正常）")
    
    # 验证 4：格式正确（包含 Markdown 标题）
    has_session_headers = content_2.count("## 会话记录") >= 2
    print_result(has_session_headers, "Markdown 格式正确（包含会话记录标题）")
    
    all_passed = memory_exists and has_first_dialog and has_both_dialogs and has_session_headers
    
    print(f"\n  📊 测试 3 结果: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")
    return all_passed


async def test_4_generate_doubao_config(temp_dir: str) -> bool:
    """
    测试 4：调用 bridge.generate_doubao_config()，验证能否正确返回配置和项目快照
    """
    print_test_header("测试 4：generate_doubao_config() 返回值验证")
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir=temp_dir
    )
    
    test_user_id = "test_user_003"
    
    # 确保用户沙盒存在
    bridge.sandbox.ensure_user_sandbox(test_user_id)
    
    # 步骤 1：调用 generate_doubao_config
    result = await bridge.generate_doubao_config(test_user_id)
    
    # 验证 1：返回值是元组
    is_tuple = isinstance(result, tuple) and len(result) == 2
    print_result(is_tuple, "返回值是二元组 (config, project_name)")
    
    if is_tuple:
        config, project_name = result
        
        # 验证 2：project_name 是字符串
        is_str = isinstance(project_name, str)
        print_result(is_str, f"project_name 是字符串: '{project_name}'")
        
        # 验证 3：config 是字典
        is_dict = isinstance(config, dict)
        print_result(is_dict, "config 是字典")
        
        # 验证 4：config 包含必要字段
        has_tts = "tts" in config
        has_dialog = "dialog" in config
        print_result(has_tts, "config 包含 'tts' 字段")
        print_result(has_dialog, "config 包含 'dialog' 字段")
        
        # 验证 5：tts.audio_config 完整
        has_audio_config = "audio_config" in config.get("tts", {})
        print_result(has_audio_config, "tts.audio_config 字段完整")
        
        # 验证 6：dialog.extra 完整
        has_extra = "extra" in config.get("dialog", {})
        print_result(has_extra, "dialog.extra 字段完整")
        
        all_passed = is_tuple and is_str and is_dict and has_tts and has_dialog and has_audio_config and has_extra
    else:
        all_passed = False
    
    print(f"\n  📊 测试 4 结果: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")
    return all_passed


async def test_5_concurrent_writes(temp_dir: str) -> bool:
    """
    测试 5：并发写入测试，验证 SandboxManager 的异步锁机制
    
    创建 50 个并发任务同时写入同一个 memory_log.md 文件，
    验证所有写入都被正确序列化，无数据丢失或损坏。
    """
    print_test_header("测试 5：并发写入与异步锁验证")
    
    bridge = OpenClawBridge(
        feishu_app_id="test_app_id",
        feishu_app_secret="test_secret",
        memory_dir=temp_dir
    )
    
    test_user_id = "test_user_concurrent"
    
    # 确保用户沙盒存在
    bridge.sandbox.ensure_user_sandbox(test_user_id)
    print_result(True, f"用户沙盒已初始化: {test_user_id}")
    
    # 定义单个写入任务
    async def write_task(task_id: int) -> None:
        """
        单个并发写入任务
        
        Args:
            task_id: 任务唯一编号（0-49）
        """
        dialog = [{"role": "user", "text": f"并发测试专属文本_编号_{task_id}"}]
        await bridge.analyze_and_save_memory(test_user_id, dialog, "vocab_project")
    
    # 创建 50 个并发任务
    num_tasks = 50
    print(f"  🚀 启动 {num_tasks} 个并发写入任务...")
    
    import time
    start_time = time.time()
    
    # 使用 asyncio.gather 同时启动所有任务
    tasks = [write_task(i) for i in range(num_tasks)]
    await asyncio.gather(*tasks)
    
    elapsed_time = time.time() - start_time
    print_result(True, f"所有任务完成，耗时 {elapsed_time:.2f} 秒")
    
    # 获取 memory_log.md 路径
    memory_path = bridge.sandbox.get_memory_log_path(test_user_id, "vocab_project")
    
    # 验证 1：文件存在
    memory_exists = os.path.exists(memory_path)
    print_result(memory_exists, f"memory_log.md 文件存在")
    
    if not memory_exists:
        return False
    
    # 读取文件内容
    with open(memory_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 验证 2：检查每个编号是否存在
    missing_ids = []
    for i in range(num_tasks):
        marker = f"并发测试专属文本_编号_{i}"
        if marker not in content:
            missing_ids.append(i)
    
    if missing_ids:
        print_result(False, f"缺失编号: {missing_ids}")
        all_present = False
    else:
        print_result(True, f"所有 {num_tasks} 条记录均存在")
        all_present = True
    
    # 验证 3：统计实际记录总数
    actual_count = content.count("并发测试专属文本_编号_")
    count_correct = actual_count == num_tasks
    print_result(count_correct, f"实际记录数: {actual_count}/{num_tasks}")
    
    # 验证 4：检查是否有损坏（如截断、乱序等）
    # 每条记录应该包含完整的 Markdown 格式
    session_count = content.count("## 会话记录")
    format_ok = session_count >= num_tasks
    print_result(format_ok, f"Markdown 格式完整（会话记录数: {session_count}）")
    
    all_passed = memory_exists and all_present and count_correct and format_ok
    
    print(f"\n  📊 测试 5 结果: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")
    return all_passed


async def run_all_tests() -> None:
    """运行所有测试"""
    print("\n" + "="*60)
    print("🚀 OpenClawBridge 第一阶段重构验证测试")
    print("="*60)
    
    # 创建临时目录作为测试隔离环境
    temp_dir = tempfile.mkdtemp(prefix="openclaw_test_")
    print(f"\n📁 临时测试目录: {temp_dir}")
    
    try:
        results = []
        
        # 运行所有测试
        results.append(await test_1_bridge_instantiation(temp_dir))
        results.append(await test_2_switch_project(temp_dir))
        results.append(await test_3_analyze_and_save_memory(temp_dir))
        results.append(await test_4_generate_doubao_config(temp_dir))
        results.append(await test_5_concurrent_writes(temp_dir))
        
        # 汇总结果
        print("\n" + "="*60)
        print("📋 测试汇总")
        print("="*60)
        
        passed_count = sum(results)
        total_count = len(results)
        
        for i, passed in enumerate(results, 1):
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  测试 {i}: {status}")
        
        print(f"\n  🎯 总计: {passed_count}/{total_count} 通过")
        
        if passed_count == total_count:
            print("\n  🎉 所有测试通过！第一阶段重构验证成功！")
        else:
            print("\n  ⚠️ 存在失败的测试，请检查上述输出")
            
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\n🧹 已清理临时目录: {temp_dir}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())