# 实时语音对讲系统：多场景动态路由与沙盒隔离架构 (V2.1 修订版)

## 1. 架构设计理念

本架构采用**控制面（Control Plane）与数据面（Data Plane）分离**的核心思想，并针对并发一致性进行了加固：
* **前端（数据面）**：纯净、无状态的语音透传通道。H5 前端仅负责音频流采集与播放，不感知业务场景切换。
* **Agent（控制面）**：OpenClaw 拥有最高决策权，负责维护用户的"状态灯（`status.json`）"。**新增约束**：OpenClaw 严禁在探测到用户处于活跃通话期间修改状态文件，从源头避免热重载冲突。
* **后端基站（路由层）**：FastAPI 演变为动态组装工厂。引入"**状态快照（State Snapshot）**"机制，确保单次通话的逻辑连贯性。

## 2. 核心目录树状图 (沙盒物理隔离区)

系统在 `memory/` 目录下建立严格的"基于用户的物理沙盒隔离区"，确保不同场景（如英语学习与长辈访谈）的数据互不污染。

```text
/memory/ (系统记忆与沙盒根目录)
├── /templates/                        <-- 静态只读区：新用户初始化模板库
│   ├── /vocab_project/
│   │   └── prompt.json                <-- 默认英语导师人设
│   └── /interview_project/
│       └── prompt.json                <-- 默认访谈助手人设
│
└── /users/                            <-- 动态读写区：飞书用户独立沙盒
    ├── /{user_id}/                    <-- 飞书唯一识别符目录
    │   ├── status.json                <-- 核心状态灯 (例: {"active_project": "vocab"})
    │   ├── status.tmp                 <-- 原子写入时的临时文件
    │   │
    │   ├── /vocab_project/            <-- 场景 A 独立空间
    │   │   ├── prompt.json            
    │   │   └── memory_log.md          
    │   │
    │   └── /interview_project/        <-- 场景 B 独立空间
    │       ├── prompt.json            
    │       └── memory_log.md          
    │
    └── /ou_x9y8z7w6v5u4/              <-- 示例：外婆/其他长辈的专属沙盒
        └── ... (内部结构完全同上，物理隔离)
```

## 3. 核心流转机制 (The Lifecycle)

1.  **静默注册与防呆机制**：当新的飞书 `user_id` 首次连接时，后端侦测到 `/users/{user_id}` 目录不存在，会自动从 `/templates/` 复制全套默认文件为其建立沙盒，并将默认状态指向最安全的备用场景（如 `vocab`）。
2.  **原子写入防碰撞**：OpenClaw 在切换场景或更新 Prompt 时，必须先将内容写入 `status.tmp`，校验无误后瞬间重命名为 `status.json`，防止高并发下 FastAPI 读到残缺的 JSON 导致系统崩溃。
3.  **内存动态组装**：FastAPI 拿到 `user_id` -> 读取该用户的 `status.json` -> 获悉 `active_project` -> 拼接绝对路径读取对应的 `prompt.json` 和 `memory_log.md` -> 在内存中组合发送给豆包 API。

---

## 4. 分步修改与测试指南

为了平稳过渡，请按照以下 4 个阶段进行代码重构与验证。

### 阶段一：建立沙盒引擎基础 (Sandbox Foundation)

**执行目标**：搭建物理隔离目录，移除旧的全局配置。
1.  在项目根目录删除或重命名原来的 `prompt_config.json`。
2.  在 `memory/` 文件夹下手动创建 `/templates/vocab_project/` 和 `/templates/interview_project/`，并在里面分别放入对应的 `prompt.json` 模板。
    * *注意*：由于火山豆包的底层约束，配置 JSON 必须包含 `model` 字段（如 "1.2.1.1" 代表 O2.0），若使用 O/O2.0 版本，配置 `bot_name`、`system_role`；若使用 SC/SC2.0 版本，必须配置 `character_manifest`。
3.  **🆕 V2.1 补充**：在 `memory/users/test_user_123/` 建立测试沙盒，并写入 `status.json` 内容为 `{"active_project": "vocab"}`。确保每个项目目录下都有 `prompt.json` 和 `memory_log.md`。

**验证标准**：通过本地简单的 Python 脚本传入 `test_user_123`，能够利用 `os.path.join` 成功打印出目标 `prompt.json` 的绝对路径且不报错。

### 阶段二：重构桥接层的"动态寻址工厂"

**执行目标**：改造 `openclaw_bridge.py`，让系统学会"看灯拿剧本"。
1.  **新增新用户兜底逻辑**：在获取到飞书 `user_id` 后，检查 `/memory/users/{user_id}` 是否存在。若不存在，执行 `shutil.copytree` 从 `templates` 复制一份初始化沙盒。
2.  **改造配置读取方法**：修改 `_load_prompt_config` 方法。接收 `user_id` 为参数，先读对应目录下的 `status.json` 获取 `project_name`。
3.  **动态路径拼接**：读取 `/memory/users/{user_id}/{project_name}/prompt.json`。如果任何环节失败（如文件损坏），触发 `try-except`，在内存中强行回退到 `vocab` 的默认配置。
4.  **🆕 V2.1 状态快照机制**：
    * `generate_doubao_config` 方法改为返回元组 `(config, project_name)`。
    * `SessionManager.__init__` 新增 `project_snapshot` 参数，在会话创建时锁定项目名称。

**验证标准**：
* 启动服务，H5 发起连接。系统应正常工作。
* **不重启服务**的情况下，手动去服务器里把 `status.json` 中的 `vocab` 改为 `interview`。
* 再次在 H5 发起连接，系统应无缝切换为访谈者的人设和音色。

### 阶段三：改造记忆回写逻辑 (Dynamic Write-back)

**执行目标**：确保挂断电话后，对话日志精准落入对应的场景抽屉。
1.  改造 `openclaw_bridge.py` 中的 `analyze_and_save_memory` 方法。
2.  逻辑链路同步修改：~~读取 `status.json` -> 确定活跃项目~~ -> **🆕 V2.1：使用 `project_snapshot` 参数** -> 打开 `/memory/users/{user_id}/{project_snapshot}/memory_log.md` -> 以 `mode='a'` (追加) 方式异步写入对话。
3.  **验证标准**：通话开始后，手动修改磁盘上的 `status.json`。通话挂断后，检查日志依然精准落入通话开始时确定的项目文件夹中（快照机制生效）。

### 阶段四：交接控制权给 OpenClaw

**执行目标**：确立 OpenClaw 的统治地位，并加入静默约束。
1.  在 OpenClaw 的 System Prompt 或 Tool 函数描述中，增加严格的文件操作约束规则。
2.  **强制规则定义**：明确告诉 OpenClaw，修改状态或 Prompt 必须采用"原子操作"。即：先写入 `.tmp` 后缀的临时文件，再执行系统级的 `os.replace()` 覆盖原文件。
3.  **🆕 V2.1 控制面静默约束**：在 OpenClaw 的系统指令中加入高优先级条款："当监测到用户正在进行语音对话时，严禁修改任何状态文件或重定向场景"。

**验证标准**：
通过 Telegram/飞书向 OpenClaw 下达自然语言指令："准备进入长辈自传访谈模式，调整系统设定"。等待其回复完成后，打开 H5 页面，若听到的直接是访谈助手的开场白，即代表整个控制面与数据面解耦架构彻底重构成功。

---

## 5. 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-04-02 | v2.1 | 引入状态快照机制；修正 Windows 原子重命名陷阱；确立控制面静默约束 |
| 2026-03-31 | v2.0 | 初始多场景动态路由架构设计 |