# test_bridge.py# #  ✅ 已完成 
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
    test_code = "fwOvFe0JxH3bAeGGGDCzx0cceH2y29f0"
    
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


# (phonecall) D:\Python_work\realtime_dialog\phonecall>python test_bridge.py
# === 1. 测试飞书鉴权 (Authenticate) ===
# DEBUG: 飞书 Token 接口返回: {'token_type': 'Bearer', 'access_token': 'eyJhbGciOiJFUzI1NiIsImZlYXR1cmVfY29kZSI6IkZlYXR1cmVPQXV0aEpXVFNpZ25fQ04iLCJraWQiOiI3NjIyMDg5ODk1NDc4NjI3NTUwIiwidHlwIjoiSldUIn0.eyJqdGkiOiI3NjIzNDU4Njc3NDU3OTQ3ODQwIiwiaWF0IjoxNzc0OTc0NzkwLCJleHAiOjE3NzQ5ODE5OTAsInZlciI6InYxIiwidHlwIjoiYWNjZXNzX3Rva2VuIiwiY2xpZW50X2lkIjoiY2xpX2E5NDE1ZTUxZjg3OGRjYzgiLCJzY29wZSI6ImF1dGg6dXNlci5pZDpyZWFkIiwiYXV0aF9pZCI6Ijc2MjM0NTg1MzA5OTcwNDYyMTIiLCJhdXRoX3RpbWUiOjE3NzQ5NzQ3NTYsImF1dGhfZXhwIjoxODA2NTEwNzU2LCJ1bml0IjoiZXVfbmMiLCJ0ZW5hbnRfdW5pdCI6ImV1X25jIiwib3BhcXVlIjp0cnVlLCJlbmMiOiJBaVFrQVFFQ0FNSURBQUVCQXdBQ0FRMEFBd3NMQUFBQUF3QUFBQWRHWldGMGRYSmxBQUFBRUc5aGRYUm9YMjl3WVhGMVpWOXFkM1FBQUFBSVZHVnVZVzUwU1dRQUFBQUJNQUFBQUFSVWFXMWxBQUFBQ2pFM056UTRNamc0TURBUEFBUU1BQUFBQVFvQUFXTEZJbG12Z0FBaUN3QUNBQUFBREZjRCs1dlRWUmdUTWRxcEdnc0FBd0FBQUREZnlFNE5ROGhoeTBOeWN5ZW55SlFTbUpaVThyUFVsbmlMamdSNjZtWHQ5YitoSmh1V0h4dXNiaUlSQ0NTbllKMEFDd0FGQUFBQUJXVjFYMjVqQUhEMjBpY0tXbXAzazdEamltaWt0aUVoTTFVT3k2YnpsREN3UzByVWpmT1pGZlJiRjBxaURpb1M2c09JcjlvTDN0dXNhZ3pGTzJwOHA4MVFtVGdkTGNhdEUzT3pQQVZuU2R3eXlTYnZtZzIwbEZnUjM0L1FZYVR1VDQrYTZjWlBzWkVjeEZOeDhHZlMwMVp6clorSVZocDRSYjc1VlY0Z0FLYzY3L1ZQM1I4RVdPeWtwRVBDcTFFelh2YUNONGU4by8rdDZBPT0iLCJlbmNfdmVyIjoidjEifQ.qTyzBq9mW35Ol1nI7tJRReHjDDXlImGbCYiXIHv6ZwpZU2YEi4HUndfO8itSgnKJWIeBEesCiCqTtKMHeB4zTA', 'expires_in': 7200, 'scope': 'auth:user.id:read', 'code': 0}
# ✅ 鉴权成功！获取到 User ID: on_99133714f7cbe8241488ccedee51fb37

# === 2. 测试生成豆包配置 (Generate Config) ===
# ✅ 配置生成成功，检查 prompt 中是否包含记忆：
# 你是小爪，一个耐心且专业的英语学习助手。请根据以下用户的专属学习计划和历史记忆引导其背单词：

# # 英语学习计划
# 今日待背单词：abandon, benevolent, cognitive, resi...

# === 3. 测试对话记忆回写 (Save Memory) ===
# [OpenClawBridge] 用户 on_99133714f7cbe8241488ccedee51fb37 的记忆文件已更新完毕。
# ✅ 记忆回写方法执行完成！

# === 测试结束，连接池已关闭 ===  