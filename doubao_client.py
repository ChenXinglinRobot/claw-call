import gzip
import json
import asyncio
import websockets
from typing import Dict, Any, Optional

# 依赖您提供的底层协议解析文件
import protocol

class DoubaoClient:
    """
    豆包端到端实时语音 API 纯异步客户端 (Phase 2.1)
    纯粹的网络层基座，剥离所有本地 I/O (麦克风/文件)，严格遵循豆包二进制协议。
    """
    def __init__(self, ws_url: str, headers: Dict[str, str], session_id: str, start_session_req: Dict[str, Any]):
        self.ws_url = ws_url
        self.headers = headers
        self.session_id = session_id
        self.start_session_req = start_session_req
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.logid = ""

    async def connect(self) -> None:
        """建立 WebSocket 连接并完成 StartConnection 与 StartSession 握手"""
        print(f"[DoubaoClient] 正在连接豆包 WSS 节点...")
        self.ws = await websockets.connect(
            self.ws_url,
            extra_headers=self.headers,
            ping_interval=None # 避免自带的 ping 干扰豆包心跳
        )
        self.logid = self.ws.response_headers.get("X-Tt-Logid", "Unknown")
        print(f"[DoubaoClient] 底层建联成功，LogID: {self.logid}")

        # 1. 发送 StartConnection (1)
        await self._send_start_connection()
        
        # 2. 发送 StartSession (100)
        await self._send_start_session()

    async def _send_start_connection(self) -> None:
        """发送 StartConnection (Event 1)"""
        req = bytearray(protocol.generate_header(
            message_type=protocol.CLIENT_FULL_REQUEST,
            message_type_specific_flags=protocol.MSG_WITH_EVENT,
            serial_method=protocol.JSON,
            compression_type=protocol.GZIP
        ))
        req.extend(int(1).to_bytes(4, 'big')) # event id
        
        payload_bytes = gzip.compress(b"{}")
        req.extend(len(payload_bytes).to_bytes(4, 'big'))
        req.extend(payload_bytes)
        await self.ws.send(req)

    async def _send_start_session(self) -> None:
        """发送 StartSession (Event 100) 注入提示词与配置"""
        req = bytearray(protocol.generate_header(
            message_type=protocol.CLIENT_FULL_REQUEST,
            message_type_specific_flags=protocol.MSG_WITH_EVENT,
            serial_method=protocol.JSON,
            compression_type=protocol.GZIP
        ))
        req.extend(int(100).to_bytes(4, 'big'))
        
        session_id_bytes = self.session_id.encode('utf-8')
        req.extend(len(session_id_bytes).to_bytes(4, 'big'))
        req.extend(session_id_bytes)

        payload_bytes = gzip.compress(json.dumps(self.start_session_req).encode('utf-8'))
        req.extend(len(payload_bytes).to_bytes(4, 'big'))
        req.extend(payload_bytes)
        
        await self.ws.send(req)
        print(f"[DoubaoClient] StartSession 配置已发送，SessionID: {self.session_id}")

    async def send_audio(self, pcm_data: bytes) -> None:
        """
        发送音频流 (TaskRequest - 200)
        ⚠️ 核心优化：遵照官方文档推荐，音频纯二进制数据不进行 GZIP 压缩，降低 CPU 开销与延迟。
        """
        if not self.ws or self.ws.closed:
            return

        req = bytearray(protocol.generate_header(
            message_type=protocol.CLIENT_AUDIO_ONLY_REQUEST,
            message_type_specific_flags=protocol.MSG_WITH_EVENT,
            serial_method=protocol.NO_SERIALIZATION,
            compression_type=protocol.NO_COMPRESSION # 官方推荐：无压缩
        ))
        req.extend(int(200).to_bytes(4, 'big'))
        
        session_id_bytes = self.session_id.encode('utf-8')
        req.extend(len(session_id_bytes).to_bytes(4, 'big'))
        req.extend(session_id_bytes)

        req.extend(len(pcm_data).to_bytes(4, 'big'))
        req.extend(pcm_data)
        
        await self.ws.send(req)

    async def send_client_interrupt(self) -> None:
        """发送打断指令 (ClientInterrupt - 515) - 应对 H5 前端的主动麦克风介入"""
        if not self.ws or self.ws.closed:
            return
            
        req = bytearray(protocol.generate_header(
            message_type=protocol.CLIENT_FULL_REQUEST,
            message_type_specific_flags=protocol.MSG_WITH_EVENT,
            serial_method=protocol.JSON,
            compression_type=protocol.GZIP
        ))
        req.extend(int(515).to_bytes(4, 'big'))
        
        session_id_bytes = self.session_id.encode('utf-8')
        req.extend(len(session_id_bytes).to_bytes(4, 'big'))
        req.extend(session_id_bytes)

        payload_bytes = gzip.compress(b"{}")
        req.extend(len(payload_bytes).to_bytes(4, 'big'))
        req.extend(payload_bytes)
        
        await self.ws.send(req)

    async def recv_message(self) -> Dict[str, Any]:
        """
        接收并解析服务端的单次响应包。
        外部（SessionManager）将通过一个 while True 循环不断调用此方法，进行事件路由分发。
        """
        try:
            response = await self.ws.recv()
            data = protocol.parse_response(response)
            return data
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[DoubaoClient] WebSocket 连接已关闭: {e}")
            return {"event": "CONNECTION_CLOSED"}
        except Exception as e:
            print(f"[DoubaoClient] 接收消息异常: {e}")
            raise

    async def finish_session(self) -> None:
        """优雅断连第一步：发送 FinishSession (102)"""
        if not self.ws or self.ws.closed:
            return
            
        print(f"[DoubaoClient] 正在发送 FinishSession...")
        req = bytearray(protocol.generate_header(
            message_type=protocol.CLIENT_FULL_REQUEST,
            message_type_specific_flags=protocol.MSG_WITH_EVENT,
            serial_method=protocol.JSON,
            compression_type=protocol.GZIP
        ))
        req.extend(int(102).to_bytes(4, 'big'))
        
        session_id_bytes = self.session_id.encode('utf-8')
        req.extend(len(session_id_bytes).to_bytes(4, 'big'))
        req.extend(session_id_bytes)

        payload_bytes = gzip.compress(b"{}")
        req.extend(len(payload_bytes).to_bytes(4, 'big'))
        req.extend(payload_bytes)
        
        await self.ws.send(req)

    async def close_connection(self) -> None:
        """优雅断连第二步：发送 FinishConnection (2) 并彻底关闭 Socket"""
        if not self.ws or self.ws.closed:
            return
            
        print(f"[DoubaoClient] 正在发送 FinishConnection 并关闭 Socket...")
        req = bytearray(protocol.generate_header(
            message_type=protocol.CLIENT_FULL_REQUEST,
            message_type_specific_flags=protocol.MSG_WITH_EVENT,
            serial_method=protocol.JSON,
            compression_type=protocol.GZIP
        ))
        req.extend(int(2).to_bytes(4, 'big'))
        
        payload_bytes = gzip.compress(b"{}")
        req.extend(len(payload_bytes).to_bytes(4, 'big'))
        req.extend(payload_bytes)
        
        try:
            await self.ws.send(req)
        except Exception:
            pass # 可能已经被远端关闭
            
        await self.ws.close()
        print("[DoubaoClient] 连接已彻底释放。")