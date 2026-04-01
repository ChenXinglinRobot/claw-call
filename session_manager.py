import asyncio
import time
from typing import Dict, Any, List, Optional
from doubao_client import DoubaoClient

class SessionManager:
    """
    单次通话生命周期与流式状态机 (Phase 2.2)
    负责拦截豆包底层事件，处理流式文本组装，隔离 H5 的音频输入输出。
    """
    def __init__(self, doubao_client: DoubaoClient):
        self.client = doubao_client
        self.is_active = False
        
        # 音频下行队列 (供外层 FastAPI 读取并下发给飞书 H5)
        self.audio_out_queue = asyncio.Queue()
        
        # 核心记忆载体：准备交给 OpenClaw 存储的完整对话日志
        self.dialog_history: List[Dict[str, Any]] = []
        
        # 流式文本拼接缓冲池
        self._current_asr_text = ""
        self._current_chat_text = ""
        
        # 挂起保活宽限期控制 (Phase 2.3 预留接口)
        self.is_suspended = False
        
        # AI 主动结束会话标志位（检测到用户退出意图时设为 True）
        self.ai_ended_session = False

    async def start_session(self) -> None:
        """启动会话，建立连接并开启事件监听循环"""
        self.is_active = True
        # --- 新增：手动插入一条测试记录 ---
        # self._commit_history("assistant", "系统已连接，正在监听静音帧测试...")#标记ws_client.py的测试#  ✅ 已完成 成功
        # ------------------------------
        await self.client.connect()
        
        # 启动后台守护任务，持续拉取豆包下发的数据包
        asyncio.create_task(self._receive_loop())
        print(f"[SessionManager] 会话启动成功，监听循环已开启。")

    async def _receive_loop(self) -> None:
        """核心事件泵：不断接收并路由豆包的消息"""
        try:
            while self.is_active:
                response = await self.client.recv_message()
                await self._route_event(response)
        except Exception as e:
            print(f"[SessionManager] 接收循环发生异常: {e}")
        finally:
            self.is_active = False

    async def _route_event(self, response: Dict[str, Any]) -> None:
        """根据协议事件类型进行精准路由与状态变更"""
        message_type = response.get("message_type")
        event = response.get("event")
        payload = response.get("payload_msg", {})

        # 1. 拦截二进制音频流 (TTS)
        if message_type == "SERVER_ACK" and isinstance(payload, bytes):
            # 将 24000Hz PCM 纯数据推入队列，供 H5 消费
            await self.audio_out_queue.put(payload)
            return

        # 2. 拦截并处理 JSON 事件包
        if message_type == "SERVER_FULL_RESPONSE":
            
            # --- 🆕 新增：首字打断信号 (事件 450) ---
            if event == 450:
                # 向音频泵队列放入打断指令，通知前端清空播放缓存
                try:
                    self.audio_out_queue.put_nowait({"type": "interrupt"})
                    print("[SessionManager] 收到 450 首字信号，已下发前端打断指令")
                except asyncio.QueueFull:
                    pass
            
            # --- 用户语音识别 (ASR) 流式组装 ---
            elif event == 451:  # ASRResponse
                results = payload.get("results", [])
                if results:
                    first_result = results[0]
                    text = first_result.get("text", "")
                    is_interim = first_result.get("is_interim", True)
                    
                    # 严禁缓存 interim 碎片，仅接收稳态文本
                    if not is_interim and text:
                        self._current_asr_text += text
                        
            elif event == 459:  # ASREnded
                if self._current_asr_text:
                    self._commit_history("user", self._current_asr_text)
                    self._current_asr_text = ""

            # --- 模型文本回复 (Chat) 流式组装 ---
            elif event == 550:  # ChatResponse
                content = payload.get("content", "")
                self._current_chat_text += content
                
            elif event == 559:  # ChatEnded
                if self._current_chat_text:
                    self._commit_history("assistant", self._current_chat_text)
                    self._current_chat_text = ""

            # --- TTSEnded 事件：检测用户退出意图 ---
            elif event == 359:  # TTSEnded
                status_code = payload.get("status_code", "")
                # 使用 str() 转换防止类型对比失败（status_code 可能是整数）
                if str(status_code) == "20000002":
                    print("[SessionManager] 检测到用户退出意图，AI 主动结束会话")
                    self.is_active = False
                    self.ai_ended_session = True

            # --- 会话生命周期终结事件 ---
            elif event in [152, 153]:  # SessionFinished 或 SessionFailed
                print(f"[SessionManager] 收到会话结束事件: {event}")
                self.is_active = False

        elif message_type == "CONNECTION_CLOSED" or response.get("event") == "CONNECTION_CLOSED":
             self.is_active = False

    def _commit_history(self, role: str, text: str) -> None:
        """将完整无误的句子落盘到内存的历史记录中"""
        timestamp = int(time.time())
        self.dialog_history.append({
            "role": role,
            "text": text,
            "timestamp": timestamp
        })
        print(f"[{role.upper()}] ({timestamp}): {text}")

    async def send_audio_upstream(self, pcm_chunk: bytes) -> None:
        """
        暴露给外层 WSS：向豆包灌入前端采集的音频切片
        ⚠️ 异常保护：捕获底层连接异常，防止豆包主动断开后 H5 继续发包导致崩溃
        """
        if self.is_active and not self.is_suspended:
            try:
                await self.client.send_audio(pcm_chunk)
            except Exception:
                # 静默处理：豆包可能已主动断开，避免上层崩溃
                pass

    async def stop_session(self) -> None:
        """优雅销毁流程：由 FastAPI 在探测到 H5 彻底失联或主动挂断时调用"""
        print("[SessionManager] 触发会话销毁流程...")
        self.is_active = False
        await self.client.finish_session()
        
        # 等待底层协议跑完收尾事件，再断开 TCP
        await asyncio.sleep(0.5) 
        await self.client.close_connection()
        
        print("[SessionManager] 会话已销毁，最终聊天记录已准备好供 OpenClaw 回写。")
        # 此时外层可安全读取 self.dialog_history 交给 OpenClaw