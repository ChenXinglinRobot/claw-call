# 小爪语音学习助手 (Feishu H5 x Doubao API x OpenClaw)

## 📖 项目简介
本项目是一个基于**飞书网页应用 (Web App)** 构建的单人语音英语学习助手。
通过构建纯 Python 异步中转基站，项目成功解耦了前端（飞书 H5）与大模型语音引擎（火山引擎豆包 API），实现了极低延迟的端到端实时语音对话。同时，系统集成了 OpenClaw 桥接层，用于接管对话上下文记忆和个性化提示词注入。

## 🏗️ 核心架构与数据流

系统采用 **前端直连基站 -> 基站转发大模型** 的架构，保障了飞书容器内音频采集与大模型底层二进制协议的兼容性。

### 1. 通信链路
* **上行 (User -> AI)**: 前端 H5 通过 Web Audio API 唤起麦克风，将默认高频采样率**手动降采样至 16000Hz PCM (16-bit 小端序)**，通过 WebSocket 每 20ms 发送一次二进制帧至 Python 服务端。服务端不作任何处理，直接透传给豆包 API。
* **下行 (AI -> User)**: 豆包 API 生成 24000Hz PCM 音频流，下发至 Python 服务端。服务端将其推入异步队列，由后台任务持续泵发至前端 H5。前端使用 `AudioContext` 队列化播放，实现无缝流式语音合成。
* **信令控制**: 采用 JSON 文本帧进行状态控制（如 `start_session`, `mic_status`, `finish_session`）。

### 2. 核心模块说明

* **`server.py`**: FastAPI 主入口。
  * 负责挂载静态文件、管理 WebSocket 连接。
  * 维护全局的 `active_sessions` 状态机。
  * 实现了极其健壮的 **30秒断线重连容灾机制**，防止因飞书切后台导致大模型直接断连。
* **`doubao_client.py`**: 纯异步的豆包 WebSocket 客户端。
  * 严格实现火山引擎底层二进制协议（Header + Payload 封包/解包）。
  * 剥离所有本地 I/O，只负责网络层的纯粹收发。
* **`session_manager.py`**: 会话生命周期与流式缓冲管理器。
  * 拦截并解析大模型事件（ASR/TTS/Chat）。
  * 拼接流式输出文本，过滤临时碎片（is_interim），确保落盘的聊天记录准确无误。
* **`openclaw_bridge.py`**: 业务逻辑与记忆中间件。
  * 负责飞书免登 Code 换取用户身份 (`user_id`)。
  * 负责生成豆包引擎的初始化配置 (`StartSession`)。
  * 在通话结束时，负责将单次对话的历史记录追加写入 Markdown 记忆文件中。
* **`static/test_h5_xl2026.html`**: 飞书前端测试端。
  * 集成飞书 JSSDK 抓取免登 Code。
  * 实现基于 `ScriptProcessorNode` 的实时录音与降采样。
  * 实现基于 `AudioBufferSourceNode` 的下行音频增益与播放。

---

## 🚀 部署与运行

### 环境依赖
```bash
pip install fastapi uvicorn websockets httpx aiofiles python-dotenv
```

### 启动服务
```bash
# 本地测试启动
uvicorn server:app --host 0.0.0.0 --port 8000
```
*(注：需配合 Cpolar 或 Nginx 实现 HTTPS 内网穿透或公网暴露，并在飞书开发者后台配置对应的 H5 可信域名)*

---

## 🛠️ 下一步开发指南：解耦与云端化重构 (NEXT STEPS)

**给 AI 编程助手的指令**：当前代码为快速跑通全链路的 MVP 版本，存在较多硬编码配置。在正式上云部署及接入 OpenClaw 动态控制前，**请优先完成以下重构任务**：

### 任务 1：提取全局环境变量 (`.env`)
需要将所有敏感的 API Key 和易变的环境配置抽离到 `.env` 文件中，并通过 `python-dotenv` 或 `pydantic-settings` 加载。

* **提取目标 (`server.py`)**:
  * `X-Api-App-ID` (火山引擎 APP ID)
  * `X-Api-Access-Key` (火山引擎 Access Token)
  * `X-Api-Resource-Id` (资源 ID，如 `volc.speech.dialog`)
  * `X-Api-App-Key` (应用 Key)
* **提取目标 (`openclaw_bridge.py`)**:
  * `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` (目前只在 `server.py` 初始化时传了，需确认前后端 App ID 一致)。
  * `redirect_uri` (目前的 `"https://www.baidu.com"` 是测试占位符，需要规范化)。
* **提取目标 (`test_h5_xl2026.html`)**:
  * 飞书 JS SDK 中的 `appId` (`cli_a9415e51f878dcc8`)，最好能通过接口或模板渲染动态传入，避免前端硬编码。

### 任务 2：OpenClaw 桥接层深度改造 (`openclaw_bridge.py`)

当前系统在 `generate_doubao_config` 函数中的提示词 (Prompt) 和机器人设 (`bot_name`, `system_role`, `speaking_style` 等) 是一段静态硬编码。为了让外部 Agent (OpenClaw) 能够接管对话目标设定，我们需要进行“文件驱动”的改造：

* **动态提示词读取与容错兜底**:
  * **修改目标**：在 `generate_doubao_config` 执行时，不要直接使用硬编码的字典。让它去项目根目录尝试读取一个名为 `prompt_config.json` 的文件。
  * **容错机制 (Fallback)**：如果该文件不存在、内容为空、或 JSON 解析失败，代码必须捕获异常，并使用当前代码中默认的“小爪”英语学习助手配置作为兜底返回。
  * **工作流说明**：外部 Agent 会在用户开启通话前修改这个 `prompt_config.json` 文件。这样每次新建通话 Session 时，后端就能注入最新的设定，且不影响正在运行的 FastAPI 服务。
  * 保持 `analyze_and_save_memory` 函数的轻量化。
  * **改造目标**：确保它仅仅是将原始的 User 和 Assistant 对话以纯文本/Markdown 格式准确追加到对应的 `study-vocab-{user_id}.md` 中即可。
  * **工作流**：无需在此处调用任何大模型 API。OpenClaw 会在接收到外部飞书指令时，利用其自身的文件读取能力，自行扫描这些 Markdown 文件并进行“慢思考”总结与计划更新。

### 任务 3：容错与安全机制提升
* 增加对豆包 API 连接断开、Token 过期的自动刷新或重试机制。
* 规范化日志输出（使用 `logging` 替代 `print`），以便在云服务器上使用 Supervisor 或 Docker 查看守护进程日志。



