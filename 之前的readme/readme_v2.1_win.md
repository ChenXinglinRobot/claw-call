# 小爪语音学习助手 V2.1 (Feishu H5 x Doubao API x OpenClaw)

## 📖 项目简介

本项目是一个基于**飞书网页应用 (Web App)** 构建的多场景语音对话系统。通过构建纯 Python 异步中转基站，项目成功解耦了前端（飞书 H5）与大模型语音引擎（火山引擎豆包 API），实现了极低延迟的端到端实时语音对话。

> **架构亮点**：采用**控制面与数据面分离**设计，支持多场景动态路由与沙盒隔离，实现前端"皮"与后端"魂"的彻底解耦。

> **当前状态**：✅ Windows 本地环境测试全部通过，V2.1 版本引入状态快照机制与错误日志增强。

---

## 🆕 V2.1 更新亮点

### 1. 状态快照机制
- 会话创建时锁定 `project_snapshot`，确保记忆回写不因并发修改而错位
- 解决通话期间切换场景导致的记忆文件交叉污染问题

### 2. Speaker ID 修复
- 修复 `interview_project` 使用无效 speaker ID (`zh_male_chunhoudahui_moon_bigtts`) 导致无声音的问题
- 更新为官方支持的男性音色 `zh_male_yunzhou_jupiter_bigtts`（清爽沉稳的男声）

### 3. 错误日志拦截增强
- 新增三层错误拦截机制，精准捕获豆包 API 返回的各类错误
- 避免控制台刷屏，仅打印真正的错误和异常事件

---

## 🏗️ 系统架构

### 核心架构理念

本架构采用**控制面（Control Plane）与数据面（Data Plane）分离**的核心思想：

- **前端（数据面）**：纯净、无状态的语音透传通道。无论应用场景如何变化，H5 前端代码 0 修改。
- **Agent（控制面）**：OpenClaw 拥有最高决策权。负责维护用户的"状态灯（`status.json`）"。
- **后端基站（路由层）**：FastAPI 演变为动态组装工厂，引入"状态快照"机制确保单次通话的逻辑连贯性。

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
│  │  • 🆕 V2.1: 状态快照传递                                         │    │
│  └───────────────────────────┬─────────────────────────────────────┘    │
│                              │                                           │
│  ┌───────────────────┐  ┌────▼────────────┐  ┌───────────────────┐      │
│  │ session_manager.py│  │ doubao_client.py│  │ openclaw_bridge.py│      │
│  │ • 事件路由分发     │  │ • 二进制协议封包│  │ • 飞书免登鉴权    │      │
│  │ • ASR/Chat 流式   │  │ • 音频流收发    │  │ • 动态沙盒路由    │      │
│  │ • 🆕 三层错误拦截 │  │ • 优雅断连      │  │ • 🆕 状态快照返回 │      │
│  └───────────────────┘  └─────────────────┘  └───────────────────┘      │
│                                                         │                │
│                         ┌───────────────────────────────┘                │
│                         ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    沙盒隔离区 (memory/)                            │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ templates/ (静态只读模板库)                                   │ │   │
│  │  │   ├── vocab_project/prompt.json     (英语学习场景)           │ │   │
│  │  │   └── interview_project/prompt.json (长辈访谈场景) ✅已修复  │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ users/{user_id}/ (用户独立沙盒)                               │ │   │
│  │  │   ├── status.json                    (当前激活项目状态灯)     │ │   │
│  │  │   ├── vocab_project/                                         │ │   │
│  │  │   │   ├── prompt.json                (词汇专属设定)           │ │   │
│  │  │   │   └── memory_log.md              (单词对话历史)           │ │   │
│  │  │   └── interview_project/                                    │ │   │
│  │  │       ├── prompt.json                (访谈专属设定) ✅已修复  │ │   │
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

---

## 📁 项目文件结构

```
phonecall/
├── server.py                 # FastAPI 主入口，WebSocket 路由
├── doubao_client.py          # 豆包 WebSocket 客户端
├── session_manager.py        # 会话生命周期管理器 (🆕 V2.1: 三层错误拦截)
├── openclaw_bridge.py        # 飞书鉴权与动态沙盒路由桥接层 (🆕 V2.1: 状态快照)
├── protocol.py               # 豆包底层二进制协议常量
├── .env.example              # 环境变量模板
├── memory/                   # 系统记忆与沙盒根目录
│   ├── templates/            # 静态只读区：新用户初始化模板库
│   │   ├── vocab_project/
│   │   │   └── prompt.json   # ✅ 英语词汇导师配置 (female speaker)
│   │   └── interview_project/
│   │       └── prompt.json   # ✅ V2.1 修复: 男性音色 speaker ID
│   └── users/                # 动态读写区：飞书用户独立沙盒
│       └── {user_id}/
│           ├── status.json
│           ├── vocab_project/
│           └── interview_project/
├── static/
│   └── test_h5_xl2026.html   # 飞书 H5 前端测试端
├── docs_by_lark_fangzhou/    # 参考文档目录
├── Architecture_V2.md        # 多场景动态路由架构说明
├── Architecture_V2.1.md      # 🆕 V2.1 架构修订版
├── Readme.md                 # 原 README 文档
├── readme_new_win.md         # V2.0 README 文档
└── readme_v2.1_win.md        # 本文档 (V2.1)
```

---

## 🎤 官方支持的 Speaker ID

根据火山引擎豆包官方文档，**O版本/O2.0版本**支持的精品音色：

| 音色 ID | 描述 | 适用场景 |
|---------|------|----------|
| `zh_female_vv_jupiter_bigtts` | vv音色，活泼灵动的女声，有很强的分享欲 | 日常对话 |
| `zh_female_xiaohe_jupiter_bigtts` | xiaohe音色，甜美活泼的女声，台湾口音 | 英语学习 ✅ |
| `zh_male_yunzhou_jupiter_bigtts` | yunzhou音色，清爽沉稳的男声 | 访谈场景 ✅ |
| `zh_male_xiaotian_jupiter_bigtts` | xiaotian音色，清爽磁性的男声 | 日常对话 |

> ⚠️ **重要提示**：使用无效的 speaker ID 会导致 TTS 静默失败，用户听不到任何回复。

---

## 🚨 错误日志拦截机制 (V2.1 新增)

### 三层错误拦截

`session_manager.py` 中的 `_route_event` 方法实现了三层错误拦截：

#### 第一层：应用层错误事件（JSON 格式）
```python
if event in [51, 153, 599] or message_type == "CONNECTION_CLOSED":
```
- **event 51**：`ConnectionFailed` - 连接建立失败
- **event 153**：`SessionFailed` - 会话启动失败
- **event 599**：`DialogCommonError` - 实时通话错误

#### 第二层：payload 中的 error 字段
```python
elif isinstance(payload, dict) and "error" in payload:
```
某些错误事件的 payload 包含 `{"error": "具体错误信息"}`。

#### 第三层：二进制协议级错误帧
```python
elif "code" in response and message_type is None:
```
当豆包返回二进制错误帧（Message Type = `0b1111`）时，`protocol.parse_response()` 会设置 `code` 字段但不设置 `message_type`。

### 错误日志示例

```
[SessionManager] ❌ 发生错误或异常中断: message_type=SERVER_FULL_RESPONSE, event=153, payload={'error': 'InvalidSpeaker'}
[SessionManager] ❌ 二进制协议错误帧: code=55000001, payload={'error': 'ServerError'}
```

---

## 🚀 Windows 本地测试指南

### 1. 环境依赖

```bash
pip install fastapi uvicorn websockets httpx aiofiles python-dotenv
```

### 2. 配置环境变量

```bash
copy .env.example .env
# 编辑 .env 文件，填入真实的 API Key
```

### 3. 启动服务

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 4. 测试验证

#### 本地快速验证
```
http://localhost:8000/app/test_h5_xl2026.html
```

#### 飞书环境完整测试（使用 Cpolar 内网穿透）
```bash
cpolar http 8000
# 将生成的 HTTPS 域名配置到飞书开放平台的可信域名
```

---

## ✅ 功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 飞书免登鉴权 | ✅ 已完成 | 通过 `tt.requestAuthCode` 获取 code，后端换取 `user_id` |
| 实时语音通话 | ✅ 已完成 | 16kHz 上行 / 24kHz 下行，极低延迟 |
| 麦克风静音/取消静音 | ✅ 已完成 | 硬件级隐私控制 + WebSocket 状态同步 |
| 断线重连 (30秒宽限期) | ✅ 已完成 | 会话挂起保活，支持无缝恢复 |
| 多场景沙盒隔离 | ✅ 已完成 | 每个用户独立沙盒，项目间物理隔离 |
| 动态配置路由 | ✅ 已完成 | 根据 status.json 动态加载 prompt.json |
| 🆕 状态快照机制 | ✅ 已完成 | 会话创建时锁定项目，确保记忆回写一致 |
| 🆕 错误日志拦截 | ✅ 已完成 | 三层拦截机制，精准捕获各类错误 |
| 🆕 Speaker ID 修复 | ✅ 已完成 | interview 项目使用正确的男性音色 |

---

## 📝 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-04-02 | v2.1 | 引入状态快照机制；修复 interview speaker ID；新增三层错误日志拦截 |
| 2026-04-02 | v2.0 | 重构为多场景动态路由与沙盒隔离架构，支持 vocab/interview 双场景 |
| 2026-04-02 | v1.0 | Windows 本地环境测试全部通过，完成所有核心功能开发 |

---

## 📚 相关文档

- [Architecture_V2.md](Architecture_V2.md) - 多场景动态路由架构说明
- [Architecture_V2.1.md](Architecture_V2.1.md) - V2.1 架构修订版
- [docs_by_lark_fangzhou/豆包通话.md](docs_by_lark_fangzhou/豆包通话.md) - 豆包实时语音 API 官方文档

---

## ⚠️ 已知问题与解决方案

### 问题：interview 项目无声音

**根因**：使用了 AI 幻觉生成的无效 speaker ID `zh_male_chunhoudahui_moon_bigtts`

**解决方案**：V2.1 已修复，使用官方支持的 `zh_male_yunzhou_jupiter_bigtts`

### 问题：错误难以追踪

**根因**：之前未拦截豆包返回的错误事件，控制台无错误日志

**解决方案**：V2.1 新增三层错误拦截机制，精准打印错误信息

---

## ☁️ 上云部署规划 (TODO)

- [ ] Docker 容器化
- [ ] HTTPS/WSS 证书配置
- [ ] 飞书可信域名配置
- [ ] 进程守护与日志规范
- [ ] 高可用与扩展