import asyncio
import json
import websockets

# 测试配置
WS_SERVER_URL = "ws://127.0.0.1:8000/ws/session" # 你的 FastAPI 本地运行地址
TEST_PCM_FILE = "test_16k.pcm" # 请准备一个 16kHz, 16-bit, 单声道的 PCM 文件

async def send_audio_stream(websocket):
    """模拟前端 H5 采集麦克风，每 20ms 发送一次二进制音频包"""
    print("[TestClient] 开始模拟发送音频流...")
    try:
        with open(TEST_PCM_FILE, "rb") as f:
            while True:
                # 采样率 16k、位深 int16 的单声道音频，20ms 的数据大小正是 640 字节
                chunk = f.read(640) 
                if not chunk:
                    break
                await websocket.send(chunk)
                await asyncio.sleep(0.02)  # 严格模拟真实的流式时间流逝
        print("[TestClient] 音频文件发送完毕！")
    except FileNotFoundError:
        print(f"❌ 找不到测试音频文件: {TEST_PCM_FILE}")

async def receive_messages(websocket):
    """后台任务：接收服务端下发的 TTS 音频流和状态日志"""
    print("[TestClient] 开启下行接收通道...")
    try:
        while True:
            message = await websocket.recv()
            if isinstance(message, bytes):
                # 这里收到的是豆包返回的 24000Hz 的 TTS 回复
                print(f"[TestClient] 收到 TTS 二进制音频流，大小: {len(message)} bytes")
                # 在真实业务中，H5 会把这些 bytes 喂给 Web Audio API 播放
            else:
                print(f"[TestClient] 收到服务端 JSON 消息: {message}")
    except websockets.exceptions.ConnectionClosed:
        print("[TestClient] 服务端连接已断开。")

async def main():
    print("正在连接到中转基站...")
    async with websockets.connect(WS_SERVER_URL) as websocket:
        
        # 1. 模拟 H5 发起通话请求 (携带鉴权 token)
        start_req = {
            "type": "start_session",
            "session_id": "test_session_001",
            "token": "fake_auth_token_from_feishu"
        }
        await websocket.send(json.dumps(start_req))
        
        # 2. 等待服务端就绪信号
        msg = await websocket.recv()
        print(f"[TestClient] 握手结果: {msg}")
        
        # 3. 启动并行的接收任务和发送任务
        recv_task = asyncio.create_task(receive_messages(websocket))
        
        # 模拟用户说话：发送音频流
        await send_audio_stream(websocket)
        
        # 模拟等待大模型思考和回复 (这里等待 5 秒收听豆包的 TTS 回复)
        print("[TestClient] 等待豆包回复...")
        await asyncio.sleep(5)
        
        # 4. 模拟 H5 用户主动挂断电话
        print("[TestClient] 发送挂断指令...")
        finish_req = {
            "type": "finish_session"
        }
        await websocket.send(json.dumps(finish_req))
        
        # 给一点时间让服务端执行优雅断连逻辑
        await asyncio.sleep(1) 
        recv_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())