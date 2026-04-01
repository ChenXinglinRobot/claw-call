import asyncio
import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any

# 加载 .env 环境变量
load_dotenv()

# 导入我们前两步写好的核心类
from doubao_client import DoubaoClient
from session_manager import SessionManager
from openclaw_bridge import OpenClawBridge, FeishuAuthException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware  # <-- 新增导入

# ============ 全局配置常量（从环境变量加载）============
# 火山引擎豆包 API 配置
DOUBAO_APP_ID = os.getenv("DOUBAO_APP_ID", "")
DOUBAO_ACCESS_KEY = os.getenv("DOUBAO_ACCESS_KEY", "")
DOUBAO_RESOURCE_ID = os.getenv("DOUBAO_RESOURCE_ID", "volc.speech.dialog")
DOUBAO_APP_KEY = os.getenv("DOUBAO_APP_KEY", "")
DOUBAO_WSS_URL = os.getenv("DOUBAO_WSS_URL", "wss://openspeech.bytedance.com/api/v3/realtime/dialogue")

# 飞书应用配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# 记忆文件存储目录
MEMORY_DIR = os.getenv("MEMORY_DIR", "memory")

app = FastAPI()

# --- 新增：严格的安全跨域策略 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.cpolar.cn",       # 仅允许你自己的 cpolar 域名访问
        "https://*.feishu.cn",       # 允许飞书官方域名
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
# ------------------------------


# 新增：将 static 文件夹挂载到根目录
app.mount("/app", StaticFiles(directory="static", html=True), name="static")

# ... 下面的 active_sessions 和其他代码保持不变 ...



# 全局字典：用于管理活跃的/挂起的会话，以实现 30 秒断线重连策略 (Phase 2.3)
active_sessions: Dict[str, SessionManager] = {}
suspension_tasks: Dict[str, asyncio.Task] = {}

# 会话 ID 到 user_id 的映射（用于记忆回写时获取用户身份）
session_user_map: Dict[str, str] = {}

# OpenClaw Bridge 全局实例（在 startup 事件中初始化）
bridge: OpenClawBridge = None


@app.on_event("startup")
async def startup_event():
    """
    FastAPI 启动时初始化 OpenClawBridge 连接池
    """
    global bridge
    bridge = OpenClawBridge(
        feishu_app_id=FEISHU_APP_ID,
        feishu_app_secret=FEISHU_APP_SECRET,
        memory_dir=MEMORY_DIR
    )
    print("[Server] OpenClawBridge 初始化完成，HTTP 连接池已就绪。")


@app.get("/api/config")
async def get_frontend_config():
    """
    为前端提供动态配置（如飞书 appId）
    避免前端硬编码敏感配置
    """
    return {
        "feishu_app_id": FEISHU_APP_ID
    }


@app.on_event("shutdown")
async def shutdown_event():
    """
    FastAPI 关闭时优雅释放 Bridge 资源
    """
    global bridge
    if bridge:
        await bridge.close()
        print("[Server] OpenClawBridge 连接池已关闭。")

# --- 核心清理与容灾逻辑 ---
async def delayed_session_destroy(session_id: str, grace_period: int = 30):
    """30秒宽限期倒计时，超时则彻底销毁底层豆包连接"""
    print(f"[Server] 会话 {session_id} 进入挂起状态，倒计时 {grace_period} 秒...")
    await asyncio.sleep(grace_period)
    print(f"[Server] 会话 {session_id} 挂起超时，执行彻底销毁！")
    
    if session_id in active_sessions:
        manager = active_sessions.pop(session_id)
        await manager.stop_session()
        
        # 异步执行记忆回写，防止阻塞主循环
        user_id = session_user_map.get(session_id)
        if user_id and manager.dialog_history:
            asyncio.create_task(
                bridge.analyze_and_save_memory(
                    user_identifier=user_id,
                    dialog_history=manager.dialog_history
                )
            )
            print(f"[Server] 会话 {session_id} 记忆回写任务已提交，用户: {user_id}")
        
        # 清理用户映射
        if session_id in session_user_map:
            del session_user_map[session_id]
        
    if session_id in suspension_tasks:
        del suspension_tasks[session_id]

# --- 异步音频下发泵 ---
async def pump_audio_to_h5(websocket: WebSocket, manager: SessionManager):
    """
    后台任务：不断从 SessionManager 抽水（读取 TTS 音频）并浇给 H5
    支持混合数据：bytes 发送二进制音频，dict 发送 JSON 控制指令
    """
    try:
        while manager.is_active:
            item = await manager.audio_out_queue.get()
            # 混合发送：如果是 bytes 发送二进制，如果是 dict 发送 JSON 文本
            if isinstance(item, bytes):
                await websocket.send_bytes(item)
            elif isinstance(item, dict):
                await websocket.send_text(json.dumps(item))
    except Exception as e:
        print(f"[Server] 音频下发泵退出: {e}")

# --- WebSocket 核心路由 ---
@app.websocket("/ws/session")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    current_session_id = None
    audio_pump_task = None

    try:
        while True:
            message = await websocket.receive()

            # --- 新增：识别底层断开信号，防止死循环导致 RuntimeError ---
            if message.get("type") == "websocket.disconnect":
                print(f"[Server] 收到 WebSocket 底层断开信号 (Code: {message.get('code')})")
                # 触发异常以跳出 while 循环，进入 except WebSocketDisconnect 处理 30 秒逻辑
                raise WebSocketDisconnect(code=message.get("code", 1000))
            # -------------------------------------------------------

            # 1. 高频拦截：处理二进制音频流 (来自前端的 16kHz PCM)
            if "bytes" in message:
                if current_session_id and current_session_id in active_sessions:
                    manager = active_sessions[current_session_id]
                    
                    # 🆕 主动拦截 AI 结束信号
                    if getattr(manager, 'ai_ended_session', False):
                        print(f"[Server] 检测到 AI 主动结束，下发前端通知并销毁会话...")
                        await websocket.send_text(json.dumps({"type": "status", "message": "session_ended_by_ai"}))
                        
                        # 触发正常的销毁和记忆回写流程
                        manager = active_sessions.pop(current_session_id)
                        await manager.stop_session()
                        
                        user_id = session_user_map.get(current_session_id)
                        if user_id and manager.dialog_history:
                            asyncio.create_task(
                                bridge.analyze_and_save_memory(
                                    user_identifier=user_id, 
                                    dialog_history=manager.dialog_history
                                )
                            )
                            print(f"[Server] 会话 {current_session_id} 记忆回写任务已提交，用户: {user_id}")
                        
                        if current_session_id in session_user_map:
                            del session_user_map[current_session_id]
                        
                        break  # 退出 while 循环，主动关闭 WebSocket 连接
                    
                    # 原有的音频转发逻辑
                    try:
                        await manager.send_audio_upstream(message["bytes"])
                    except Exception:
                        # 双保险：静默忽略，豆包可能已主动断开
                        pass
                continue

            # 2. 低频拦截：处理 JSON 控制状态机指令
            if "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "start_session":
                    current_session_id = data.get("session_id")
                    token = data.get("token")

                    # [恢复机制] 若该 ID 在宽限期内，直接复活连接
                    if current_session_id in active_sessions and current_session_id in suspension_tasks:
                        print(f"[Server] 探测到 H5 重连请求，撤销会话 {current_session_id} 的销毁倒计时。")
                        suspension_tasks[current_session_id].cancel()
                        del suspension_tasks[current_session_id]
                        
                        manager = active_sessions[current_session_id]
                        manager.is_suspended = False 
                        audio_pump_task = asyncio.create_task(pump_audio_to_h5(websocket, manager))
                        await websocket.send_text(json.dumps({"type": "status", "message": "reconnected"}))
                        continue

                    # [新建机制] 真实的身份换取与建联流程
                    try:
                        # 通过飞书免登 code 换取用户身份标识
                        user_id = await bridge.authenticate_feishu_user(code=token)
                        # 将 user_id 绑定到当前会话，以便后续记忆回写使用
                        session_user_map[current_session_id] = user_id
                        # 根据用户身份生成豆包会话配置（含历史记忆）
                        config = await bridge.generate_doubao_config(user_identifier=user_id)
                    except FeishuAuthException as e:
                        # 鉴权失败，返回错误并关闭连接
                        print(f"[Server] 飞书鉴权失败: {e}")
                        await websocket.send_text(json.dumps({"type": "error", "message": "auth_failed"}))
                        await websocket.close()
                        continue
                    
                    # 豆包 WebSocket 连接配置（从环境变量加载）
                    HEADERS = {
                        "X-Api-App-ID": DOUBAO_APP_ID,
                        "X-Api-Access-Key": DOUBAO_ACCESS_KEY,
                        "X-Api-Resource-Id": DOUBAO_RESOURCE_ID,
                        "X-Api-App-Key": DOUBAO_APP_KEY
                    }
                    
                    client = DoubaoClient(DOUBAO_WSS_URL, HEADERS, current_session_id, config)
                    manager = SessionManager(client)
                    active_sessions[current_session_id] = manager
                    
                    await manager.start_session()
                    audio_pump_task = asyncio.create_task(pump_audio_to_h5(websocket, manager))
                    await websocket.send_text(json.dumps({"type": "status", "message": "ready"}))

                elif msg_type == "mic_status":
                    # 前端静音按键同步，挂起音频上行输入
                    muted = data.get("muted", False)
                    if current_session_id and current_session_id in active_sessions:
                        active_sessions[current_session_id].is_suspended = muted
                        print(f"[Server] 收到 H5 麦克风状态更新，当前音频流上传: {'暂停' if muted else '恢复'}")

                elif msg_type == "finish_session":
                    # 收到标准结束协议，触发优雅断连并回写记忆
                    print(f"[Server] 收到前端主动结束通话指令。")
                    if current_session_id and current_session_id in active_sessions:
                        manager = active_sessions.pop(current_session_id)
                        await manager.stop_session()
                        
                        # 异步执行记忆回写，防止阻塞 WebSocket 主循环
                        user_id = session_user_map.get(current_session_id)
                        if user_id and manager.dialog_history:
                            asyncio.create_task(
                                bridge.analyze_and_save_memory(
                                    user_identifier=user_id,
                                    dialog_history=manager.dialog_history
                                )
                            )
                            print(f"[Server] 会话 {current_session_id} 记忆回写任务已提交，用户: {user_id}")
                        
                        # 清理用户映射
                        if current_session_id in session_user_map:
                            del session_user_map[current_session_id]
                    break

    except WebSocketDisconnect:
        print(f"[Server] 飞书 H5 容器发生意外断连...")
        # 此时决不立刻断开底层大模型！赋予它 30 秒的复活宽限期
        if current_session_id and current_session_id in active_sessions:
            active_sessions[current_session_id].is_suspended = True
            task = asyncio.create_task(delayed_session_destroy(current_session_id, 30))
            suspension_tasks[current_session_id] = task
    finally:
        if audio_pump_task:
            audio_pump_task.cancel()