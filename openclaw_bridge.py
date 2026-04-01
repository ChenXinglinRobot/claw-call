import os
import json
import copy
import httpx
import aiofiles
import asyncio
from typing import List, Dict, Any
from datetime import datetime


class FeishuAuthException(Exception):
    """飞书授权相关异常"""
    pass

class OpenClawBridge:
    # ============ 默认配置兜底（当 prompt_config.json 不存在或解析失败时使用）============
    DEFAULT_CONFIG = {
        "tts": {
            "audio_config": {
                "channel": 1,
                "format": "pcm_s16le",
                "sample_rate": 24000
            },
            "speaker": "zh_female_xiaohe_jupiter_bigtts"
        },
        "dialog": {
            "bot_name": "小爪",
            "system_role": "你是小爪，一个耐心且专业的英语学习助手。请根据以下用户的专属学习计划和历史记忆引导其背单词：",
            "speaking_style": "温柔耐心，像朋友一样聊天，语速适中",
            "extra": {
                "input_mod": "keep_alive",
                "model": "1.2.1.1"
            }
        }
    }
    
    # prompt_config.json 文件路径（项目根目录）
    PROMPT_CONFIG_FILE = "prompt_config.json"

    def __init__(self, feishu_app_id: str, feishu_app_secret: str, memory_dir: str = "memory"):
        """
        初始化 OpenClaw 桥接层
        """
        self.app_id = feishu_app_id
        self.app_secret = feishu_app_secret
        self.memory_dir = memory_dir
        # 复用异步 HTTP 客户端连接池，显著降低高并发下的建联延迟
        self.http_client = httpx.AsyncClient(timeout=15.0)
        
        # 确保记忆文件目录存在
        if not os.path.exists(self.memory_dir):
            os.makedirs(self.memory_dir, exist_ok=True)

    async def authenticate_feishu_user(self, code: str) -> str:
        """
        核心方法一：鉴权换取身份标识
        将前端 H5 传来的免登 code 置换为 user_id 或 union_id。
        """
        token_url = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
        token_payload = {
            "grant_type": "authorization_code",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "code": code
        }
        
        try:
            # 1. 获取 access_token
            token_resp = await self.http_client.post(token_url, json=token_payload)
            token_resp.raise_for_status()
            token_data = token_resp.json()
            # --- 新增这一行调试日志 ---
            #print(f"DEBUG: 飞书 Token 接口返回: {token_data}") #做一个小标记调试#  ✅ 已完成 成功
            # -----------------------
            
            if token_data.get("code") != 0:
                # 注意：扁平结构下，如果 code 字段不存在或为 0，通常表示成功
                pass 
                
            # ❌ 原代码：access_token = token_data["data"]["access_token"]
            # ✅ 修改为：
            access_token = token_data.get("access_token")
            
            if not access_token:
                 raise FeishuAuthException(f"获取 Token 失败，返回内容: {token_data}")
            
            # 2. 获取用户信息
            user_info_url = "https://open.feishu.cn/open-apis/authen/v1/user_info"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_resp = await self.http_client.get(user_info_url, headers=headers)
            user_resp.raise_for_status()
            user_data = user_resp.json()
            # 兼容处理：有些版本有 data 字段，有些没有
            user_info = user_data.get("data", user_data) 
            user_identifier = user_info.get("user_id") or user_info.get("union_id")
            
            if user_data.get("code") != 0:
                raise FeishuAuthException(f"获取用户信息失败: {user_data.get('msg')}")
                
            # 优先使用 user_id，兜底使用 union_id
            user_info = user_data["data"]
            user_identifier = user_info.get("user_id") or user_info.get("union_id")
            
            if not user_identifier:
                raise FeishuAuthException("无法从飞书接口提取到有效的 user_id 或 union_id")
                
            return user_identifier
            
        except httpx.HTTPError as e:
            raise FeishuAuthException(f"飞书 API 网络请求异常: {str(e)}")

    async def _load_prompt_config(self) -> Dict[str, Any]:
        """
        私有方法：读取 prompt_config.json 配置文件
        如果文件不存在、为空或解析失败，返回默认配置作为兜底
        """
        try:
            if not os.path.exists(self.PROMPT_CONFIG_FILE):
                print(f"[OpenClawBridge] 配置文件 {self.PROMPT_CONFIG_FILE} 不存在，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
            
            async with aiofiles.open(self.PROMPT_CONFIG_FILE, mode='r', encoding='utf-8') as f:
                content = await f.read()
            
            if not content.strip():
                print(f"[OpenClawBridge] 配置文件 {self.PROMPT_CONFIG_FILE} 为空，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
            
            config = json.loads(content)
            
            # 验证必要字段是否存在
            if "tts" not in config or "dialog" not in config:
                print(f"[OpenClawBridge] 配置文件缺少必要字段，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
            
            print(f"[OpenClawBridge] 成功加载配置文件 {self.PROMPT_CONFIG_FILE}")
            return config
            
        except json.JSONDecodeError as e:
            print(f"[OpenClawBridge] 配置文件 JSON 解析失败: {e}，使用默认配置")
            return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"[OpenClawBridge] 读取配置文件异常: {e}，使用默认配置")
            return self.DEFAULT_CONFIG.copy()

    async def _read_user_memory(self, user_identifier: str) -> str:
        """
        私有方法：读取用户记忆文件
        如果不存在则创建默认学习计划
        """
        file_path = os.path.join(self.memory_dir, f"study-vocab-{user_identifier}.md")
        
        if os.path.exists(file_path):
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                return await f.read()
        else:
            # 若无历史记忆，初始化默认学习计划
            default_memory = "# 英语学习计划\n今日待背单词：abandon, benevolent, cognitive, resilient..."
            async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                await f.write(default_memory)
            return default_memory

    async def generate_doubao_config(self, user_identifier: str) -> Dict[str, Any]:
        """
        核心方法二：生成豆包会话配置
        动态读取 prompt_config.json 配置文件，注入用户记忆，组装符合豆包底层 WebSocket 协议的 StartSession 配置。
        工作流：外部 Agent 修改 prompt_config.json -> 新会话时加载最新配置 -> 注入记忆 -> 返回完整配置
        """
        # 1. 读取用户记忆文件
        memory_content = await self._read_user_memory(user_identifier)
        
        # 2. 动态加载 prompt_config.json（失败时使用默认配置兜底）
        config = await self._load_prompt_config()
        
        # 3. 深拷贝配置，避免修改原始对象
        config = copy.deepcopy(config)
        
        # 4. 确保 tts.audio_config 完整（防止配置文件缺失必要字段）
        if "audio_config" not in config.get("tts", {}):
            config.setdefault("tts", {})["audio_config"] = self.DEFAULT_CONFIG["tts"]["audio_config"]
        
        # 5. 将用户记忆追加到 system_role 末尾
        base_system_role = config.get("dialog", {}).get("system_role", "")
        config.setdefault("dialog", {})["system_role"] = f"{base_system_role}\n\n{memory_content}"
        
        # 6. 确保 dialog_context 初始化为空列表
        config.setdefault("dialog", {})["dialog_context"] = []
        
        # 7. 确保 extra 字段完整（关键保活参数）
        if "extra" not in config.get("dialog", {}):
            config.setdefault("dialog", {})["extra"] = self.DEFAULT_CONFIG["dialog"]["extra"]
        else:
            # 确保 input_mod 和 model 存在
            default_extra = self.DEFAULT_CONFIG["dialog"]["extra"]
            config["dialog"]["extra"].setdefault("input_mod", default_extra["input_mod"])
            config["dialog"]["extra"].setdefault("model", default_extra["model"])
        
        return config

    async def analyze_and_save_memory(self, user_identifier: str, dialog_history: List[Dict]) -> None:
        """
        核心方法三：对话日志回写与记忆更新
        通话结束后，接管完整日志，可调用大模型结算状态，并追加到 Markdown 文件。
        """
        if not dialog_history:
            return

        file_path = os.path.join(self.memory_dir, f"study-vocab-{user_identifier}.md")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # -------------------------------------------------------------------
        # [可选增强] 在这里调用 OpenClaw / 大模型 API 进行“慢思考”状态结算
        # 例如：提取发音错误的单词、更新待复习列表等。
        # summary = await self._call_openclaw_for_summary(dialog_history)
        # -------------------------------------------------------------------
        
        # 格式化本次对话日志
        log_content = f"\n\n## 会话记录 ({current_time})\n"
        for turn in dialog_history:
            role = "🧑 User" if turn.get("role") == "user" else "🤖 小爪"
            text = turn.get("text", "")
            log_content += f"**{role}**: {text}\n"

        # 异步追加写入 Markdown 文件
        async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
            await f.write(log_content)
            
        print(f"[OpenClawBridge] 用户 {user_identifier} 的记忆文件已更新完毕。")

    async def close(self):
        """
        优雅关闭 HTTP 客户端连接池
        """
        await self.http_client.aclose()