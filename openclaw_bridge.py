import os
import re
import json
import copy
import shutil
import httpx
import aiofiles
import asyncio
from typing import List, Dict, Any
from datetime import datetime


class FeishuAuthException(Exception):
    """飞书授权相关异常"""
    pass


class OpenClawBridge:
    """
    OpenClaw 桥接层 - 多场景动态路由与沙盒隔离架构
    
    核心职责：
    1. 飞书免登鉴权，获取用户身份标识
    2. 基于用户身份的动态配置加载（从用户沙盒读取）
    3. 新用户自动初始化沙盒（从 templates 复制）
    4. 对话日志按项目隔离回写
    """
    
    # ============ 默认配置兜底（当用户配置文件损坏时使用）============
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
    
    # 默认激活项目
    DEFAULT_ACTIVE_PROJECT = "vocab"
    
    # 归档水位线（字符数阈值）
    ARCHIVE_THRESHOLD_CHARS = 35000
     # OpenClaw Gateway URL AGENT_ID配置（从环境变量读取，避免硬编码泄露）

    def __init__(self, feishu_app_id: str, feishu_app_secret: str, memory_dir: str = "memory"):
        """
        初始化 OpenClaw 桥接层
        
        Args:
            feishu_app_id: 飞书应用 ID
            feishu_app_secret: 飞书应用密钥
            memory_dir: 记忆文件存储根目录（默认为 memory/）
        """
        self.app_id = feishu_app_id
        self.app_secret = feishu_app_secret
        self.memory_dir = memory_dir
        
        # 沙盒关键路径常量
        self.templates_dir = os.path.join(self.memory_dir, "templates")
        self.users_dir = os.path.join(self.memory_dir, "users")
        
        # 从环境变量读取 OpenClaw 配置（避免硬编码泄露）
        self.openclaw_token = os.getenv("OPENCLAW_TOKEN", "")
        self.gateway_url = os.getenv("OPENCLAW_GATEWAY_URL", "http://127.0.0.1:12392/v1/chat/completions")
        self.agent_id = os.getenv("OPENCLAW_AGENT_ID", "main")
        
        # 懒加载：不在初始化时创建 client，避免 Event Loop 未启动的报错
        self._http_client = None
        # 强引用集合：防止后台任务被 Python 垃圾回收机制静默杀掉
        self.background_tasks = set()
        
        # 确保核心目录存在
        self._ensure_core_directories()

    @property
    def http_client(self):
        """安全获取异步 HTTP 客户端（懒加载）"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

    def _ensure_core_directories(self):
        """
        确保核心目录结构存在
        """
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.users_dir, exist_ok=True)
        # templates 目录也确保存在（但不强制创建，因为应该由部署时提供）
        if not os.path.exists(self.templates_dir):
            print(f"[OpenClawBridge] 警告：模板目录 {self.templates_dir} 不存在，新用户初始化将失败！")

    def _normalize_project_name(self, project_name: str) -> str:
        """
        规范化项目名称：安全校验 + 自动补全后缀
        
        1. 安全校验：检查去除后缀的项目名是否仅包含字母、数字、下划线、连字符
        2. 防御路径穿越攻击（如 "../../../etc/passwd"）
        3. 自动补全 "_project" 后缀
        
        Args:
            project_name: 原始项目名称
            
        Returns:
            规范化后的项目名称（带 _project 后缀）
        """
        # 去除可能存在的后缀
        base_name = project_name.replace("_project", "")
        
        # 安全校验：仅允许字母、数字、下划线、连字符
        if not re.match(r'^[\w\-]+$', base_name):
            print(f"[OpenClawBridge] 警告：项目名 '{base_name}' 包含非法字符，回退为默认项目")
            base_name = self.DEFAULT_ACTIVE_PROJECT
        
        # 统一补全后缀
        return f"{base_name}_project"

    def _get_user_sandbox_path(self, user_id: str) -> str:
        """
        获取用户沙盒根路径
        
        Args:
            user_id: 飞书用户身份标识
            
        Returns:
            用户沙盒的绝对路径
        """
        return os.path.join(self.users_dir, user_id)

    def _get_user_status_path(self, user_id: str) -> str:
        """
        获取用户状态文件路径（status.json）
        
        Args:
            user_id: 飞书用户身份标识
            
        Returns:
            status.json 的绝对路径
        """
        return os.path.join(self._get_user_sandbox_path(user_id), "status.json")

    def _get_project_path(self, user_id: str, project_name: str) -> str:
        """
        获取用户特定项目目录路径
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 项目名称（如 vocab_project, interview_project）
            
        Returns:
            项目目录的绝对路径
        """
        return os.path.join(self._get_user_sandbox_path(user_id), project_name)

    def _get_prompt_path(self, user_id: str, project_name: str) -> str:
        """
        获取用户特定项目的 prompt.json 路径
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 项目名称
            
        Returns:
            prompt.json 的绝对路径
        """
        return os.path.join(self._get_project_path(user_id, project_name), "prompt.json")

    def _get_memory_log_path(self, user_id: str, project_name: str) -> str:
        """
        获取用户特定项目的记忆日志路径
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 项目名称
            
        Returns:
            memory_log.md 的绝对路径
        """
        return os.path.join(self._get_project_path(user_id, project_name), "memory_log.md")

    def _ensure_user_sandbox(self, user_id: str) -> bool:
        """
        确保用户沙盒存在，若不存在则从模板初始化
        
        这是核心的"静默注册与防呆机制"
        
        V2.2 升级：自动补全新增目录结构（raw_archives/, episodes/, master_profile.md）
        
        Args:
            user_id: 飞书用户身份标识
            
        Returns:
            True 表示沙盒已就绪，False 表示初始化失败
        """
        user_sandbox_path = self._get_user_sandbox_path(user_id)
        
        if os.path.exists(user_sandbox_path):
            # 沙盒已存在，检查状态文件完整性
            status_path = self._get_user_status_path(user_id)
            if os.path.exists(status_path):
                # 🆕 V2.2: 检查并补全所有项目的新目录结构
                self._ensure_project_structure_upgraded(user_id)
                return True
            else:
                print(f"[OpenClawBridge] 用户沙盒存在但状态文件缺失，尝试重建...")
        
        # 沙盒不存在，执行初始化
        print(f"[OpenClawBridge] 检测到新用户 {user_id}，开始初始化沙盒...")
        
        if not os.path.exists(self.templates_dir):
            print(f"[OpenClawBridge] 错误：模板目录不存在，无法初始化用户沙盒！")
            return False
        
        try:
            # 从 templates 复制完整的目录结构
            shutil.copytree(self.templates_dir, user_sandbox_path)
            
            # 创建默认状态文件
            status_path = self._get_user_status_path(user_id)
            default_status = {"active_project": self.DEFAULT_ACTIVE_PROJECT}
            with open(status_path, 'w', encoding='utf-8') as f:
                json.dump(default_status, f, ensure_ascii=False, indent=4)
            
            # 🆕 V2.2: 确保新目录结构完整
            self._ensure_project_structure_upgraded(user_id)
            
            print(f"[OpenClawBridge] 用户 {user_id} 沙盒初始化完成，默认项目: {self.DEFAULT_ACTIVE_PROJECT}")
            return True
            
        except Exception as e:
            print(f"[OpenClawBridge] 沙盒初始化失败: {e}")
            return False
    
    def _ensure_project_structure_upgraded(self, user_id: str) -> None:
        """
        V2.2 新增：确保用户所有项目的目录结构已升级到最新版本
        
        检查并创建：raw_archives/, episodes/, master_profile.md
        
        Args:
            user_id: 飞书用户身份标识
        """
        user_sandbox_path = self._get_user_sandbox_path(user_id)
        
        # 遍历用户沙盒下的所有项目目录
        for item in os.listdir(user_sandbox_path):
            project_path = os.path.join(user_sandbox_path, item)
            
            # 跳过非目录文件（如 status.json）
            if not os.path.isdir(project_path):
                continue
            
            # 跳过非项目目录（不以 _project 结尾的目录）
            if not item.endswith("_project"):
                continue
            
            # 创建 raw_archives 目录
            raw_archives_dir = os.path.join(project_path, "raw_archives")
            if not os.path.exists(raw_archives_dir):
                os.makedirs(raw_archives_dir, exist_ok=True)
                print(f"[OpenClawBridge] 已创建 raw_archives 目录: {raw_archives_dir}")
            
            # 创建 episodes 目录
            episodes_dir = os.path.join(project_path, "episodes")
            if not os.path.exists(episodes_dir):
                os.makedirs(episodes_dir, exist_ok=True)
                print(f"[OpenClawBridge] 已创建 episodes 目录: {episodes_dir}")
            
            # 创建 master_profile.md 文件
            master_profile_path = os.path.join(project_path, "master_profile.md")
            if not os.path.exists(master_profile_path):
                # 写入初始模板内容
                default_content = f"# {item.replace('_project', '')} 全局大纲\n\n> 本文件由系统自动生成，用于存储二级记忆（L2）。\n\n## 核心要点\n\n- \n\n## 待办事项\n\n- \n"
                with open(master_profile_path, 'w', encoding='utf-8') as f:
                    f.write(default_content)
                print(f"[OpenClawBridge] 已创建 master_profile.md: {master_profile_path}")

    async def authenticate_feishu_user(self, code: str) -> str:
        """
        核心方法一：鉴权换取身份标识
        将前端 H5 传来的免登 code 置换为 user_id 或 union_id。
        
        Args:
            code: 飞书免登授权码
            
        Returns:
            用户身份标识（user_id 或 union_id）
            
        Raises:
            FeishuAuthException: 鉴权失败时抛出
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
            
            access_token = token_data.get("access_token")
            
            if not access_token:
                raise FeishuAuthException(f"获取 Token 失败，返回内容: {token_data}")
            
            # 2. 获取用户信息
            user_info_url = "https://open.feishu.cn/open-apis/authen/v1/user_info"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_resp = await self.http_client.get(user_info_url, headers=headers)
            user_resp.raise_for_status()
            user_data = user_resp.json()
            
            if user_data.get("code") != 0:
                raise FeishuAuthException(f"获取用户信息失败: {user_data.get('msg')}")
                
            user_info = user_data.get("data", user_data)
            user_identifier = user_info.get("user_id") or user_info.get("union_id")
            
            if not user_identifier:
                raise FeishuAuthException("无法从飞书接口提取到有效的 user_id 或 union_id")
            
            # 3. 确保用户沙盒存在（新用户自动初始化）
            self._ensure_user_sandbox(user_identifier)
                
            return user_identifier
            
        except httpx.HTTPError as e:
            raise FeishuAuthException(f"飞书 API 网络请求异常: {str(e)}")

    async def _read_user_status(self, user_id: str) -> Dict[str, Any]:
        """
        读取用户状态文件（status.json）
        
        采用原子读取策略：优先读取 status.json，若损坏则尝试从 status.tmp 恢复
        
        Args:
            user_id: 飞书用户身份标识
            
        Returns:
            状态字典，至少包含 active_project 字段
        """
        status_path = self._get_user_status_path(user_id)
        default_status = {"active_project": self.DEFAULT_ACTIVE_PROJECT}
        
        try:
            if os.path.exists(status_path):
                async with aiofiles.open(status_path, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                status = json.loads(content)
                
                # 验证必要字段
                if "active_project" in status:
                    return status
                else:
                    print(f"[OpenClawBridge] 状态文件缺少 active_project 字段，使用默认值")
                    return default_status
            else:
                return default_status
                
        except json.JSONDecodeError as e:
            print(f"[OpenClawBridge] 状态文件 JSON 解析失败: {e}，使用默认状态")
            return default_status
        except Exception as e:
            print(f"[OpenClawBridge] 读取状态文件异常: {e}，使用默认状态")
            return default_status

    async def _load_prompt_config(self, user_id: str) -> Dict[str, Any]:
        """
        私有方法：根据用户身份动态加载 prompt.json 配置文件
        
        工作流：
        1. 读取用户的 status.json 获取 active_project
        2. 拼接路径读取对应的 prompt.json
        3. 若任何环节失败，回退到默认配置
        
        Args:
            user_id: 飞书用户身份标识
            
        Returns:
            完整的豆包配置字典
        """
        # 1. 读取用户状态获取活跃项目
        status = await self._read_user_status(user_id)
        project_name = status.get("active_project", self.DEFAULT_ACTIVE_PROJECT)
        
        # 规范化项目名称（安全校验 + 自动补全后缀）
        project_name = self._normalize_project_name(project_name)
        
        # 2. 拼接 prompt.json 路径
        prompt_path = self._get_prompt_path(user_id, project_name)
        
        try:
            if not os.path.exists(prompt_path):
                print(f"[OpenClawBridge] 配置文件 {prompt_path} 不存在，尝试从模板加载")
                # 尝试从模板加载
                template_prompt_path = os.path.join(self.templates_dir, project_name, "prompt.json")
                if os.path.exists(template_prompt_path):
                    async with aiofiles.open(template_prompt_path, mode='r', encoding='utf-8') as f:
                        content = await f.read()
                    config = json.loads(content)
                    print(f"[OpenClawBridge] 成功从模板加载配置: {project_name}")
                    return config
                else:
                    print(f"[OpenClawBridge] 模板配置也不存在，使用默认配置")
                    return self.DEFAULT_CONFIG.copy()
            
            async with aiofiles.open(prompt_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
            
            if not content.strip():
                print(f"[OpenClawBridge] 配置文件 {prompt_path} 为空，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
            
            config = json.loads(content)
            
            # 验证必要字段是否存在
            if "tts" not in config or "dialog" not in config:
                print(f"[OpenClawBridge] 配置文件缺少必要字段，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
            
            print(f"[OpenClawBridge] 成功加载用户 {user_id} 的配置，当前项目: {project_name}")
            return config
            
        except json.JSONDecodeError as e:
            print(f"[OpenClawBridge] 配置文件 JSON 解析失败: {e}，使用默认配置")
            return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"[OpenClawBridge] 读取配置文件异常: {e}，使用默认配置")
            return self.DEFAULT_CONFIG.copy()

    async def _read_user_memory(self, user_id: str, project_name: str = None) -> str:
        """
        私有方法：读取用户特定项目的记忆文件
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 项目名称（可选，若不提供则从状态文件读取）
            
        Returns:
            记忆文件内容（Markdown 格式）
        """
        # 若未指定项目，从状态文件读取当前活跃项目
        if not project_name:
            status = await self._read_user_status(user_id)
            project_name = status.get("active_project", self.DEFAULT_ACTIVE_PROJECT)
        
        # 规范化项目名称（安全校验 + 自动补全后缀）
        project_name = self._normalize_project_name(project_name)
        
        memory_path = self._get_memory_log_path(user_id, project_name)
        
        if os.path.exists(memory_path):
            async with aiofiles.open(memory_path, mode='r', encoding='utf-8') as f:
                return await f.read()
        else:
            # 记忆文件不存在，返回空内容（将在后续写入时创建）
            return ""

    async def generate_doubao_config(self, user_identifier: str) -> tuple:
        """
        核心方法二：生成豆包会话配置（V2.2 架构升级版）
        动态读取用户沙盒中的 prompt.json 配置文件，组装符合豆包底层 WebSocket 协议的 StartSession 配置。
        
        V2.2 关键变更：彻底解耦控制面与数据面
        - 不再读取笨重的 memory_log.md（那是给 OpenClaw 后台用的）
        - 只读取 prompt.json（由 OpenClaw 维护，已包含浓缩后的核心记忆）
        - 豆包只需要"接起电话、扮演人设、执行追问策略"，无需知道过去所有对话
        
        V2.1 关键变更：返回值改为元组 (config, project_name)
        - project_name 作为状态快照，由调用方存入 SessionManager
        - 确保记忆回写时使用相同的 project_name，避免并发错位
        
        工作流：
        1. 读取用户状态文件，获取 active_project
        2. 动态加载 prompt.json（由 OpenClaw 维护，已包含浓缩后的核心记忆）
        3. 组装完整配置并返回（含 project_name 快照）
        
        Args:
            user_identifier: 飞书用户身份标识
            
        Returns:
            元组 (config, project_name):
            - config: 完整的豆包会话配置字典
            - project_name: 当前激活的项目名称（用于状态快照）
        """
        # 1. 读取用户状态获取活跃项目（用于快照）
        status = await self._read_user_status(user_identifier)
        project_name = status.get("active_project", self.DEFAULT_ACTIVE_PROJECT)
        
        # 规范化项目名称（安全校验 + 自动补全后缀）
        project_name = self._normalize_project_name(project_name)
        
        # 2. 动态加载 prompt.json（由 OpenClaw 维护，已包含浓缩后的核心记忆）
        config = await self._load_prompt_config(user_identifier)
        
        # 3. 深拷贝配置，避免修改原始对象
        config = copy.deepcopy(config)
        
        # 4. 确保 tts.audio_config 完整
        if "audio_config" not in config.get("tts", {}):
            config.setdefault("tts", {})["audio_config"] = self.DEFAULT_CONFIG["tts"]["audio_config"]
        
        # 5. 直接使用 prompt.json 中的 system_role，严禁追加超长日志
        # (因为 OpenClaw 已经在后台把前情提要浓缩进 prompt.json 里了)
        config.setdefault("dialog", {})["dialog_context"] = []
        
        # 6. 确保 extra 字段完整
        if "extra" not in config.get("dialog", {}):
            config.setdefault("dialog", {})["extra"] = self.DEFAULT_CONFIG["dialog"]["extra"]
        else:
            default_extra = self.DEFAULT_CONFIG["dialog"]["extra"]
            config["dialog"]["extra"].setdefault("input_mod", default_extra["input_mod"])
            config["dialog"]["extra"].setdefault("model", default_extra["model"])
        
        # 返回元组 (配置, 项目名快照)
        return config, project_name

    async def analyze_and_save_memory(self, user_identifier: str, dialog_history: List[Dict], project_snapshot: str = None) -> None:
        """
        核心方法三：对话日志回写与记忆更新（V2.2 升级版）
        通话结束后，接管完整日志，并追加到对应项目的记忆文件中。
        
        V2.1 关键变更：接收 project_snapshot 参数
        - 使用通话开始时捕获的项目快照，而非实时读取状态文件
        - 彻底消除并发错位风险：即使通话期间状态被外部修改，回写依然精准
        
        V2.2 关键变更：新增弹性水位检测与异步通知 OpenClaw
        - 挂断时检测 memory_log.md 字符数
        - 若 >= 35000 字符，触发分卷归档
        - 异步通知 OpenClaw 执行记忆结算（Fire-and-Forget）
        
        Args:
            user_identifier: 飞书用户身份标识
            dialog_history: 对话历史列表，每项包含 role 和 text 字段
            project_snapshot: 🆕 项目快照（从 SessionManager 获取，通话开始时锁定）
        """
        if not dialog_history:
            return

        # 🆕 V2.1: 优先使用快照，避免实时读取状态文件
        if project_snapshot:
            project_name = project_snapshot
            print(f"[OpenClawBridge] 使用状态快照回写记忆: {project_name}")
        else:
            # 兜底逻辑：若无快照（向后兼容），则实时读取状态
            status = await self._read_user_status(user_identifier)
            project_name = status.get("active_project", self.DEFAULT_ACTIVE_PROJECT)
            print(f"[OpenClawBridge] 无快照，实时读取状态回写记忆: {project_name}")
        
        # 规范化项目名称（安全校验 + 自动补全后缀）
        project_name = self._normalize_project_name(project_name)
        
        # 获取记忆文件路径
        file_path = self._get_memory_log_path(user_identifier, project_name)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 格式化本次对话日志
        log_content = f"\n\n## 会话记录 ({current_time})\n"
        for turn in dialog_history:
            role = "🧑 User" if turn.get("role") == "user" else "🤖 AI"
            text = turn.get("text", "")
            log_content += f"**{role}**: {text}\n"

        # 确保项目目录存在
        project_dir = self._get_project_path(user_identifier, project_name)
        os.makedirs(project_dir, exist_ok=True)

        # 异步追加写入 Markdown 文件
        async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
            await f.write(log_content)
            
        print(f"[OpenClawBridge] 用户 {user_identifier} 的记忆文件已更新完毕 (项目: {project_name})")
        
        # ============ V2.2 新增：弹性水位检测与归档 ============
        archive_info = await self.check_and_archive_memory(user_identifier, project_name)
        
        # ============ V2.2 新增：异步通知 OpenClaw（Fire-and-Forget）============
        task = asyncio.create_task(self._notify_openclaw(user_identifier, project_name, archive_info))
        
        # 将任务添加到强引用集合，防止被 GC 意外回收
        self.background_tasks.add(task)
        # 任务执行完毕后，自动从集合中移除，避免内存泄漏
        task.add_done_callback(self.background_tasks.discard)

    async def switch_project(self, user_id: str, project_name: str) -> bool:
        """
        切换用户的活跃项目
        
        采用原子写入策略：先写入临时文件，再重命名覆盖
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 目标项目名称（可带或不带 _project 后缀）
            
        Returns:
            True 表示切换成功，False 表示失败
        """
        # 规范化项目名称（安全校验 + 自动补全后缀）
        project_name = self._normalize_project_name(project_name)
        
        # 验证目标项目是否存在
        project_path = self._get_project_path(user_id, project_name)
        if not os.path.exists(project_path):
            print(f"[OpenClawBridge] 目标项目 {project_name} 不存在，切换失败")
            return False
        
        status_path = self._get_user_status_path(user_id)
        tmp_path = status_path + ".tmp"
        
        try:
            # 构建新状态
            new_status = {"active_project": project_name.replace("_project", "")}
            
            # 原子写入：先写临时文件
            async with aiofiles.open(tmp_path, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(new_status, ensure_ascii=False, indent=4))
            
            # 重命名覆盖（原子操作）
            os.replace(tmp_path, status_path)
            
            print(f"[OpenClawBridge] 用户 {user_id} 已切换到项目: {project_name}")
            return True
            
        except Exception as e:
            print(f"[OpenClawBridge] 切换项目失败: {e}")
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False

    async def check_and_archive_memory(self, user_id: str, project_name: str) -> dict:
        """
        V2.2 新增：弹性水位检测与归档动作
        
        在挂断时检测 memory_log.md 的字符数：
        - 若 >= 50000 字符，触发分卷归档
        - 若 < 50000 字符，安全水位，不执行切分
        
        Args:
            user_id: 飞书用户身份标识
            project_name: 项目名称（需带 _project 后缀）
            
        Returns:
            归档信息字典：
            - {"triggered": False} 未触发归档
            - {"triggered": True, "archived_file": "raw_vol_001.md", "char_count": 52000} 触发归档
        """
        project_path = self._get_project_path(user_id, project_name)
        memory_path = self._get_memory_log_path(user_id, project_name)
        raw_archives_dir = os.path.join(project_path, "raw_archives")
        
        # 确保 raw_archives 目录存在
        os.makedirs(raw_archives_dir, exist_ok=True)
        
        # 获取当前 memory_log.md 的内容
        if not os.path.exists(memory_path):
            return {"triggered": False, "reason": "memory_log_not_found"}
        
        try:
            # 异步读取文件内容
            async with aiofiles.open(memory_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            char_count = len(content)
            
            print(f"[OpenClawBridge] 水位检测: 当前 memory_log.md 字符数: {char_count}")
            
            if char_count >= self.ARCHIVE_THRESHOLD_CHARS:
                # 触发分卷归档
                # 扫描 raw_archives 目录，找到下一个卷号
                existing_vols = [f for f in os.listdir(raw_archives_dir) if f.startswith("raw_vol_") and f.endswith(".md")]
                
                # 解析现有卷号，找到最大值
                max_vol = 0
                for vol_file in existing_vols:
                    try:
                        # 文件名格式: raw_vol_001.md
                        vol_num = int(vol_file.replace("raw_vol_", "").replace(".md", ""))
                        max_vol = max(max_vol, vol_num)
                    except ValueError:
                        continue
                
                next_index = max_vol + 1
                new_filename = f"raw_vol_{next_index:03d}.md"
                new_filepath = os.path.join(raw_archives_dir, new_filename)
                
                # 移动文件（使用 os.replace 进行系统级原子操作，极快且不阻塞 Event Loop）
                os.replace(memory_path, new_filepath)
                
                # 创建新的空 memory_log.md
                open(memory_path, 'w', encoding='utf-8').close()
                
                print(f"[OpenClawBridge] 触发弹性分卷，当前字数: {char_count}，已归档为 {new_filename}")
                
                return {
                    "triggered": True,
                    "archived_file": new_filename,
                    "char_count": char_count
                }
            
            # 安全水位，不执行切分
            return {"triggered": False, "char_count": char_count}
            
        except FileNotFoundError:
            return {"triggered": False, "reason": "memory_log_not_found"}
        except Exception as e:
            print(f"[OpenClawBridge] 归档检测异常: {e}")
            return {"triggered": False, "error": str(e)}
    
    async def _notify_openclaw(self, user_id: str, project_name: str, archive_info: dict) -> None:
        """
        V2.2 新增：异步通知 OpenClaw 执行记忆结算
        使用 Fire-and-Forget 模式，非阻塞发送 HTTP POST 请求
        """
        # ============ 新增：项目与专属 Skill 的硬绑定字典 ============
        PROJECT_SKILL_MAP = {
            "vocab_project": "vocab-learning-planner",
            "interview_project": "elder-interview-planner"
        }
        # 获取目标技能，默认兜底为 elder_interview_planner
        target_skill = PROJECT_SKILL_MAP.get(project_name, "elder-interview-planner")

        # ============ 新增：获取项目绝对路径 GPS ============
        project_path = self._get_project_path(user_id, project_name)
        abs_project_path = os.path.abspath(project_path)

        # 根据是否触发归档，动态生成指令
        if archive_info and archive_info.get("triggered"):
            archived_file = archive_info.get("archived_file")
            char_count = archive_info.get("char_count", 0)
            content = (
                f"[系统通知] 用户 {user_id} 的 {project_name} 语音通话结束。\n"
                f"【项目绝对路径】: {abs_project_path}\n"
                f"⚠️ 【强制指令】：请立即调用并执行你的『{target_skill}』技能来完成本次任务！\n"
                f"本次通话触发了强制分卷，原始日志（{char_count} 字符）已移至 raw_archives/{archived_file}。"
                f"请立即进入该绝对路径，执行长文本提炼，生成摘要到 episodes/ 中，并更新 master_profile.md 和 prompt.json。"
            )
        else:
            char_count = archive_info.get("char_count", 0)
            content = (
                f"[系统通知] 用户 {user_id} 的 {project_name} 语音通话结束。\n"
                f"【项目绝对路径】: {abs_project_path}\n"
                f"⚠️ 【强制指令】：请立即调用并执行你的『{target_skill}』技能来完成本次任务！\n"
                f"当前 memory_log.md 累计 {char_count} 字符。"
                f"请立即进入该绝对路径读取 memory_log.md，更新 master_profile.md 和 prompt.json。"
            )

        payload = {
            "model": "openclaw",
            "messages": [{"role": "user", "content": content}],
            "user": "phonecall-system"  # 关键：使用系统身份，避免污染用户聊天界面
        }

        headers = {
            "Authorization": f"Bearer {self.openclaw_token}",
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self.agent_id,
        }

        try:
            # 使用类内部复用的 http_client 性能更好
            resp = await self.http_client.post(self.gateway_url, headers=headers, json=payload)
            resp.raise_for_status()
            print(f"[OpenClawBridge] 门铃已按响，异步通知发送成功。状态码: {resp.status_code}，触发技能: {target_skill}")
        except httpx.HTTPStatusError as e:
            print(f"[OpenClawBridge] 通知 OpenClaw 失败 (HTTP {e.response.status_code}): {e.response.text}")
        except Exception as e:
            print(f"[OpenClawBridge] 通知 OpenClaw 失败: {e}")

    async def close(self):
        """
        优雅关闭 HTTP 客户端连接池
        """
        await self.http_client.aclose()
