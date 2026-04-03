# 小爪语音学习助手 (Feishu H5 x Doubao API x OpenClaw)

## 📖 项目简介

本项目是一个基于**飞书网页应用 (Web App)** 构建的多场景语音对话系统。通过构建纯 Python 异步中转基站，项目成功解耦了前端（飞书 H5）与大模型语音引擎（火山引擎豆包 API），实现了极低延迟的端到端实时语音对话。

> **架构亮点**：采用**控制面与数据面分离**设计，支持多场景动态路由与沙盒隔离，实现前端"皮"与后端"魂"的彻底解耦。

> **当前状态**：✅ Windows 本地环境测试全部通过，已升级为多场景动态路由架构。

---

## 🏗️ 系统架构

### 核心架构理念

本架构采用**控制面（Control Plane）与数据面（Data Plane）分离**的核心思想：

- **前端（数据面）**：纯净、无状态的语音透传通道。无论应用场景如何变化，H5 前端代码 0 修改，仅负责采集麦克风流、传递飞书免登 Code 并播放音频。
- **Agent（控制面）**：OpenClaw 拥有最高决策权。通过自然语言交互，OpenClaw 负责在后台修改用户的"状态指示灯（`status.json`）"和"情境提示词（`prompt.json`）"。
- **后端基站（路由层）**：FastAPI 失去全局配置文件，转而成为一个"唯 `user_id` 是从"的动态组装工厂。

### 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           飞书 H5 前端                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │ 麦克风采集   │    │ 降采样 16kHz│    │ WebSocket   │                  │
│  │ (Web Audio) │ -> │ PCM 16-bit  │ -> │ 发送音频流  │                  │
│  └─────────────┘    └─────────────┘    └──────┬──────┘                  │
│                                                │ WSS                     │
│  ┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐                  │
│  │ 音频播放    │ <- │ PCM Player  │ <- │ 接收音频流  │                  │
│  │ (24kHz PCM) │    │ (队列式播放) │    │ (二进制帧)  │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket (WSS)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Python 中转基站 (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      server.py (主入口)                          │    │
│  │  • WebSocket 路由 (/ws/session)                                  │    │
│  │  • 会话状态管理 (active_sessions)                                 │    │
│  │  • 30秒断线重连容灾机制                                           │    │
│  │  • 静音状态同步 (mic_status)                                      │    │
│  └───────────────────────────┬─────────────────────────────────────┘    │
│                              │                                           │
│  ┌───────────────────┐  ┌────▼────────────┐  ┌───────────────────┐      │
│  │ session_manager.py│  │ doubao_client.py│  │ openclaw_bridge.py│      │
│  │ • 事件路由分发     │  │ • 二进制协议封包│  │ • 飞书免登鉴权    │      │
│  │ • ASR/Chat 流式   │  │ • 音频流收发    │  │ • 🆕 动态沙盒路由 │      │
│  │   文本拼接        │  │ • 优雅断连      │  │ • 🆕 多场景切换   │      │
│  │ • 打断信号处理    │  │ • 打断指令发送  │  │ • 🆕 记忆隔离回写 │      │
│  └───────────────────┘  └─────────────────┘  └───────────────────┘      │
│                                                         │                │
│                         ┌───────────────────────────────┘                │
│                         ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    🆕 沙盒隔离区 (memory/)                         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ templates/ (静态只读模板库)                                   │ │   │
│  │  │   ├── vocab_project/prompt.json     (英语学习场景)           │ │   │
│  │  │   └── interview_project/prompt.json (长辈访谈场景)           │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ users/{user_id}/ (用户独立沙盒)                               │ │   │
│  │  │   ├── status.json                    (当前激活项目状态灯)     │ │   │
│  │  │   ├── vocab_project/                                         │ │   │
│  │  │   │   ├── prompt.json                (词汇专属设定)           │ │   │
│  │  │   │   └── memory_log.md              (单词对话历史)           │ │   │
│  │  │   └── interview_project/                                    │ │   │
│  │  │       ├── prompt.json                (访谈专属设定)           │ │   │
│  │  │       └── memory_log.md              (长辈口述历史)           │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket (WSS)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     火山引擎豆包实时语音 API                              │
│  • 实时语音识别 (ASR)                                                    │
│  • 大语言模型对话 (Chat)                                                 │
│  • 流式语音合成 (TTS, 24kHz PCM)                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 核心数据流

| 方向 | 数据格式 | 说明 |
|------|---------|------|
| **上行 (User -> AI)** | 16kHz PCM (16-bit 小端序) | 前端 Web Audio API 采集并降采样，每 20ms 发送一帧 |
| **下行 (AI -> User)** | 24kHz PCM (16-bit 小端序) | 豆包 TTS 输出，前端队列式流式播放 |
| **信令控制** | JSON 文本帧 | `start_session`, `mic_status`, `finish_session` 等 |

---

## 📁 项目文件结构

```
phonecall/
├── server.py                 # FastAPI 主入口，WebSocket 路由
├── doubao_client.py          # 豆包 WebSocket 客户端
├── session_manager.py        # 会话生命周期管理器
├── openclaw_bridge.py        # 🆕 飞书鉴权与动态沙盒路由桥接层
├── protocol.py               # 豆包底层二进制协议常量
├── .env.example              # 环境变量模板
├── prompt_config.example.json # 提示词配置模板（已废弃，保留参考）
├── memory/                   # 🆕 系统记忆与沙盒根目录
│   ├── templates/            # 静态只读区：新用户初始化模板库
│   │   ├── vocab_project/
│   │   │   └── prompt.json   # 默认的英语词汇导师人设配置
│   │   └── interview_project/
│   │       └── prompt.json   # 默认的长辈自传访谈设定
│   └── users/                # 动态读写区：飞书用户独立沙盒
│       └── {user_id}/        # 用户专属沙盒（自动创建）
│           ├── status.json   # 核心状态灯 (active_project)
│           ├── vocab_project/
│           │   ├── prompt.json
│           │   └── memory_log.md
│           └── interview_project/
│               ├── prompt.json
│               └── memory_log.md
├── static/
│   └── test_h5_xl2026.html   # 飞书 H5 前端测试端
├── docs_by_lark_fangzhou/    # 参考文档目录
├── Architecture_V2.md        # 🆕 架构设计文档
├── test_sandbox_architecture.py  # 🆕 架构验证测试脚本
├── Readme.md                 # 原 README 文档
└── readme_new_win.md         # 本文档
```

---

## 🔧 核心模块说明

### 后端模块

| 文件 | 核心职责 |
|------|---------|
| `server.py` | FastAPI 主入口，挂载静态文件，管理 WebSocket 连接，实现 30 秒断线重连容灾机制 |
| `doubao_client.py` | 纯异步的豆包 WebSocket 客户端，严格实现火山引擎底层二进制协议（Header + Payload 封包/解包） |
| `session_manager.py` | 会话生命周期管理，拦截并解析大模型事件（ASR/TTS/Chat），流式文本拼接 |
| `openclaw_bridge.py` | **🆕 核心重构**：飞书免登鉴权，动态沙盒路由，多场景切换，记忆隔离回写 |
| `protocol.py` | 豆包二进制协议常量定义（消息类型、序列化方式、压缩方式等） |

### 前端模块

| 文件 | 核心职责 |
|------|---------|
| `static/test_h5_xl2026.html` | 飞书 H5 前端测试端，集成飞书 JSSDK，实现麦克风采集、降采样、流式播放、静音控制 |

---

## 🆕 多场景动态路由机制

### 核心流转机制 (The Lifecycle)

1. **静默注册与防呆机制**：当新的飞书 `user_id` 首次连接时，后端侦测到 `/users/{user_id}` 目录不存在，会自动从 `/templates/` 复制全套默认文件为其建立沙盒，并将默认状态指向最安全的备用场景（如 `vocab`）。

2. **原子写入防碰撞**：OpenClaw 在切换场景或更新 Prompt 时，必须先将内容写入 `status.tmp`，校验无误后瞬间重命名为 `status.json`，防止高并发下 FastAPI 读到残缺的 JSON 导致系统崩溃。

3. **内存动态组装**：FastAPI 拿到 `user_id` -> 读取该用户的 `status.json` -> 获悉 `active_project` -> 拼接绝对路径读取对应的 `prompt.json` 和 `memory_log.md` -> 在内存中组合发送给豆包 API。

### 支持的场景

| 场景 | 项目名 | 描述 | 音色 |
|------|--------|------|------|
| 英语词汇学习 | `vocab` | 耐心专业的英语学习助手，引导背单词 | zh_female_xiaohe_jupiter_bigtts |
| 长辈自传访谈 | `interview` | 温暖倾听的访谈助手，记录人生故事 | zh_male_chunhoudahui_moon_bigtts |

---

## 🚀 Windows 本地测试指南

### 1. 环境依赖

```bash
# 安装 Python 依赖
pip install fastapi uvicorn websockets httpx aiofiles python-dotenv
```

### 2. 配置环境变量

```bash
# 复制模板文件
copy .env.example .env

# 编辑 .env 文件，填入真实的 API Key
```

**`.env` 配置项说明：**

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `DOUBAO_APP_ID` | 火山引擎应用 ID | `your_app_id` |
| `DOUBAO_ACCESS_KEY` | 火山引擎 Access Key | `your_access_key` |
| `DOUBAO_RESOURCE_ID` | 资源 ID | `volc.speech.dialog` |
| `DOUBAO_APP_KEY` | 应用 Key | `your_app_key` |
| `DOUBAO_WSS_URL` | 豆包 WebSocket 地址 | `wss://openspeech.bytedance.com/api/v3/realtime/dialogue` |
| `FEISHU_APP_ID` | 飞书应用 ID | `cli_xxx` |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | `xxx` |
| `MEMORY_DIR` | 记忆文件存储目录 | `memory` |

### 3. 启动服务

```bash
# 本地测试启动
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 验证新架构

```bash
# 运行架构验证测试脚本
python test_sandbox_architecture.py
```

### 5. 测试验证

#### 5.1 本地快速验证（后端逻辑调试）

```bash
# 浏览器访问
http://localhost:8000/app/test_h5_xl2026.html
```

> 此方式仅用于调试后端逻辑，飞书免登等功能无法使用。

#### 5.2 飞书环境完整测试（推荐）

使用 **Cpolar** 内网穿透工具，一键生成 HTTPS 公网地址：

```bash
# 1. 安装并启动 Cpolar（Windows 版）
# 访问 https://www.cpolar.com/ 下载安装

# 2. 启动隧道映射本地 8000 端口
cpolar http 8000

# 3. Cpolar 会生成类似以下的 HTTPS 地址
# https://xxxxxxxx.cpolar.cn
```

**飞书开放平台配置步骤：**

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入应用 → 网页应用 → 配置可信域名
3. 添加 Cpolar 生成的域名（如 `xxxxxxxx.cpolar.cn`）
4. 在飞书工作台测试 H5 应用，访问地址：
   ```
   https://xxxxxxxx.cpolar.cn/app/test_h5_xl2026.html
   ```

---

## ✅ 已完成功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 飞书免登鉴权 | ✅ 已完成 | 通过 `tt.requestAuthCode` 获取 code，后端换取 `user_id` |
| 实时语音通话 | ✅ 已完成 | 16kHz 上行 / 24kHz 下行，极低延迟 |
| 麦克风静音/取消静音 | ✅ 已完成 | 硬件级隐私控制 + WebSocket 状态同步 |
| 断线重连 (30秒宽限期) | ✅ 已完成 | 会话挂起保活，支持无缝恢复 |
| 流式 ASR 文本组装 | ✅ 已完成 | 过滤 interim 碎片，仅落盘稳态文本 |
| 流式 Chat 文本组装 | ✅ 已完成 | 在 ChatEnded 事件时拼接完整回复 |
| 首字打断功能 | ✅ 已完成 | 450 事件触发前端清空播放缓存 |
| AI 主动结束会话检测 | ✅ 已完成 | TTSEnded 事件 status_code=20000002 |
| 🆕 多场景沙盒隔离 | ✅ 已完成 | 每个用户独立沙盒，项目间物理隔离 |
| 🆕 动态配置路由 | ✅ 已完成 | 根据 status.json 动态加载 prompt.json |
| 🆕 记忆文件隔离回写 | ✅ 已完成 | 对话日志精准写入对应项目目录 |
| 🆕 项目无缝切换 | ✅ 已完成 | 无需重启服务，修改状态即可切换场景 |
| CORS 跨域安全策略 | ✅ 已完成 | 仅允许 cpolar 和飞书域名访问 |

---

## 🔐 环境变量说明

完整的环境变量配置如下：

```env
# ============ 火山引擎豆包 API 配置 ============
DOUBAO_APP_ID=your_app_id
DOUBAO_ACCESS_KEY=your_access_key
DOUBAO_RESOURCE_ID=volc.speech.dialog
DOUBAO_APP_KEY=your_app_key
DOUBAO_WSS_URL=wss://openspeech.bytedance.com/api/v3/realtime/dialogue

# ============ 飞书应用配置 ============
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# ============ 记忆文件存储 ============
MEMORY_DIR=memory
```

---

## 📝 架构变更说明

### 从 V1 到 V2 的重大变更

| 维度 | V1 (旧架构) | V2 (新架构) |
|------|-------------|-------------|
| 配置管理 | 全局 `prompt_config.json` | 用户沙盒 `memory/users/{user_id}/` |
| 场景支持 | 单一场景 | 多场景动态切换 |
| 记忆存储 | 单文件 `study-vocab-{user_id}.md` | 按项目隔离 `memory_log.md` |
| 新用户处理 | 手动配置 | 自动初始化沙盒 |
| 场景切换 | 需重启服务 | 无需重启，实时生效 |

### 迁移指南

1. **无需修改前端代码**：H5 前端完全透明，无需任何改动
2. **确保 templates 目录存在**：新用户初始化依赖模板库
3. **可选删除旧配置**：`prompt_config.json` 已废弃，可删除或保留作参考

---

## ☁️ 上云部署规划 (TODO)

当前 Windows 本地测试已全部通过，后续计划：

### 1. Docker 容器化
- [ ] 编写 `Dockerfile`
- [ ] 编写 `docker-compose.yml`
- [ ] 配置健康检查与自动重启

### 2. HTTPS/WSS 证书配置
- [ ] 申请 SSL 证书
- [ ] 配置 Nginx 反向代理
- [ ] 强制 HTTPS 跳转

### 3. 飞书可信域名配置
- [ ] 在飞书开发者后台配置生产环境域名
- [ ] 配置 H5 可信域名白名单

### 4. 进程守护与日志规范
- [ ] 使用 `logging` 模块替代 `print`
- [ ] 配置 Supervisor 或 systemd 守护进程
- [ ] 日志轮转与归档策略

### 5. 高可用与扩展
- [ ] 负载均衡配置
- [ ] Redis 会话共享
- [ ] 监控告警接入

---

## 📚 相关文档

项目参考文档位于 `docs_by_lark_fangzhou/` 目录：

- [豆包通话.md](docs_by_lark_fangzhou/豆包通话.md) - 豆包实时语音 API 官方文档
- [keepalive.md](docs_by_lark_fangzhou/keepalive.md) - 静音保活配置说明
- [飞书网页应用开发文档.md](docs_by_lark_fangzhou/飞书网页应用开发文档.md) - 飞书 H5 开发指南
- [获取授权码.md](docs_by_lark_fangzhou/获取授权码.md) - 飞书免登授权流程

架构设计文档：
- [Architecture_V2.md](Architecture_V2.md) - 多场景动态路由与沙盒隔离架构说明

---

## 📝 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-04-02 | v2.0 | 🆕 重构为多场景动态路由与沙盒隔离架构，支持 vocab/interview 双场景 |
| 2026-04-02 | v1.0 | Windows 本地环境测试全部通过，完成所有核心功能开发 |