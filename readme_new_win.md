# 小爪语音学习助手 (Feishu H5 x Doubao API x OpenClaw)

## 📖 项目简介

本项目是一个基于**飞书网页应用 (Web App)** 构建的单人语音英语学习助手。通过构建纯 Python 异步中转基站，项目成功解耦了前端（飞书 H5）与大模型语音引擎（火山引擎豆包 API），实现了极低延迟的端到端实时语音对话。同时，系统集成了 OpenClaw 桥接层，用于接管对话上下文记忆和个性化提示词注入。

> **当前状态**：✅ Windows 本地环境测试全部通过，后续计划上云部署。

---

## 🏗️ 系统架构

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
│  │ • ASR/Chat 流式   │  │ • 音频流收发    │  │ • 动态配置加载    │      │
│  │   文本拼接        │  │ • 优雅断连      │  │ • 记忆文件回写    │      │
│  │ • 打断信号处理    │  │ • 打断指令发送  │  │ • 提示词注入      │      │
│  └───────────────────┘  └─────────────────┘  └───────────────────┘      │
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
├── openclaw_bridge.py        # 飞书鉴权与记忆桥接层
├── protocol.py               # 豆包底层二进制协议常量
├── .env.example              # 环境变量模板
├── prompt_config.example.json # 提示词配置模板
├── memory/                   # 用户记忆文件存储目录
│   └── study-vocab-{user_id}.md
├── static/
│   └── test_h5_xl2026.html   # 飞书 H5 前端测试端
├── docs_by_lark_fangzhou/    # 参考文档目录
│   ├── 豆包通话.md
│   ├── keepalive.md
│   ├── 飞书网页应用开发文档.md
│   └── ...
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
| `openclaw_bridge.py` | 飞书免登鉴权，动态提示词配置加载，通话结束后记忆文件回写 |
| `protocol.py` | 豆包二进制协议常量定义（消息类型、序列化方式、压缩方式等） |

### 前端模块

| 文件 | 核心职责 |
|------|---------|
| `static/test_h5_xl2026.html` | 飞书 H5 前端测试端，集成飞书 JSSDK，实现麦克风采集、降采样、流式播放、静音控制 |

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

### 3. 配置提示词（可选）

```bash
# 复制模板文件
copy prompt_config.example.json prompt_config.json

# 编辑 prompt_config.json 自定义 AI 人设和学习计划
```

### 4. 启动服务

```bash
# 本地测试启动
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
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

> **提示**：Cpolar 免费版域名会随机变化，每次重启需重新配置飞书可信域名。建议上云后使用固定域名。

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
| 记忆文件回写 | ✅ 已完成 | 追加写入 Markdown 格式对话日志 |
| 动态提示词配置 | ✅ 已完成 | 通过 `prompt_config.json` 外部注入 |
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

---

## 📝 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-04-02 | v1.0 | Windows 本地环境测试全部通过，完成所有核心功能开发 |