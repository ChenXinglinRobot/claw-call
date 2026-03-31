# test_bridge.py
import asyncio
import os
from openclaw_bridge import OpenClawBridge

async def run_test():
    # 1. 初始化 Bridge
    bridge = OpenClawBridge(
        feishu_app_id=os.getenv("FEISHU_APP_ID", "cli_a9415e51f878dcc8"),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", "lo49jyG8JmVNR9zUOyA9TckwYlKkM4tN"),
        memory_dir="memory"
    )
    
    # 将刚刚从飞书开发者工具获取的 code 填入这里
    test_code = "cHXiL19IJy66AaHLHLEK5xdH84359c8J"
    
    try:
        print("=== 1. 测试飞书鉴权 (Authenticate) ===")
        user_id = await bridge.authenticate_feishu_user(test_code)
        print(f"✅ 鉴权成功！获取到 User ID: {user_id}\n")

        print("=== 2. 测试生成豆包配置 (Generate Config) ===")
        config = await bridge.generate_doubao_config(user_id)
        print("✅ 配置生成成功，检查 prompt 中是否包含记忆：")
        print(config["dialog"]["system_role"][:100] + "...\n") # 仅打印前100个字符验证

        print("=== 3. 测试对话记忆回写 (Save Memory) ===")
        # 伪造一段简短的对话历史
        mock_history = [
            {"role": "user", "text": "Hello, this is a test from pure Python."},
            {"role": "assistant", "text": "Hi there! The OpenClaw bridge is working perfectly."}
        ]
        await bridge.analyze_and_save_memory(user_id, mock_history)
        print("✅ 记忆回写方法执行完成！\n")
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
    finally:
        await bridge.close()
        print("=== 测试结束，连接池已关闭 ===")

if __name__ == "__main__":
    asyncio.run(run_test())