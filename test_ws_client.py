# test_ws_client.py
import asyncio
import websockets
import json

async def test_session():
    uri = "ws://localhost:8000/ws/session"
    
    # 1. 抓取一个新鲜的 code 填在这里
    fresh_code = "3zNnw8eLFL7cA8DFEJCxLCC8b87d7G9D" 
    session_id = "test_session_123"

    try:
        async with websockets.connect(uri) as websocket:
            print(f"--- 1. 发送 Start Session ---")
            start_msg = {
                "type": "start_session",
                "session_id": session_id,
                "token": fresh_code
            }
            await websocket.send(json.dumps(start_msg))

            # 等待服务端 ready
            while True:
                resp = await websocket.recv()
                data = json.loads(resp)
                print(f"收到服务器响应: {data}")
                if data.get("message") == "ready":
                    break

            print(f"\n--- 2. 模拟发送一小段二进制音频 (静音帧) ---")
            # 发送 10 次伪造的音频切片
            for _ in range(10):
                await websocket.send(bytes([0]*640)) 
                await asyncio.sleep(0.02)
            print("音频切片发送完毕。")

            print(f"\n--- 3. 模拟意外断开 (直接关闭连接) ---")
            # 这里我们不发送 finish_session，而是直接退出 Context Manager
            # 观察 server.py 终端是否显示“进入挂起状态，倒计时 30 秒”
            
    except Exception as e:
        print(f"异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_session())


# #步骤 3.3：观察与验证
# 执行动作：

# 获取新 code 并填入脚本。

# 运行 python test_ws_client.py。

# 重点观察 server.py 的控制台日志：

# 看启动：是否出现了 [DoubaoClient] StartSession 配置已发送？

# 看断开：当测试脚本运行结束（连接断开）时，服务端是否打印了：
# [Server] 飞书 H5 容器发生意外断连...
# [Server] 会话 test_session_123 进入挂起状态，倒计时 30 秒...？

# 看销毁：等待 30 秒后，服务端是否打印了：
# [Server] 会话 test_session_123 挂起超时，执行彻底销毁！
# [Server] 会话 test_session_123 记忆回写任务已提交？

# 这一步如果通过，意味着你的后端已经具备了生产级别的健壮性！ 请告诉我你观察到的日志输出情况。   