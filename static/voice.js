/**
 * 语音学习助手 - 核心业务逻辑
 * 包含飞书免登、状态机、计时器、欢迎语动画、震动反馈等功能
 */

// ============ 全局状态管理 ============
const AppState = {
    current: 'idle',  // idle | connecting | active
    authCode: null,   // 飞书授权码
    isMuted: false,   // 静音状态
};

// ============ WebSocket 与音频相关 ============
let ws = null;                    // WebSocket 连接
let audioContext = null;          // 音频上下文
let mediaStream = null;           // 麦克风流
let processor = null;             // 音频处理器
let player = null;                // PCM 播放器

// ============ 下行播放器 (24kHz 连续播放) ============
/**
 * PCM 音频播放器类
 * 用于播放后端返回的 24kHz PCM 音频流
 */
class PCMPlayer {
    constructor(sampleRate = 24000) {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        this.sampleRate = sampleRate;
        this.nextTime = 0;
        this.sources = []; // 追踪所有音频源
    }
    
    /**
     * 播放 PCM 音频缓冲区
     * @param {ArrayBuffer} buffer - 16-bit PCM 数据
     */
    play(buffer) {
        if (this.ctx.state === 'suspended') this.ctx.resume();
        
        // 将 16-bit 整数转为 Float32
        const view = new Int16Array(buffer);
        const floatArray = new Float32Array(view.length);
        for (let i = 0; i < view.length; i++) {
            floatArray[i] = view[i] / 32768;
        }

        const audioBuffer = this.ctx.createBuffer(1, floatArray.length, this.sampleRate);
        audioBuffer.getChannelData(0).set(floatArray);

        const source = this.ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.ctx.destination);

        // 队列式连续播放，防止爆音
        const currentTime = this.ctx.currentTime;
        if (this.nextTime < currentTime) this.nextTime = currentTime + 0.1;
        source.start(this.nextTime);
        this.nextTime += audioBuffer.duration;
        
        // 追踪音频源，播放完毕后移除
        this.sources.push(source);
        source.onended = () => {
            const idx = this.sources.indexOf(source);
            if (idx > -1) this.sources.splice(idx, 1);
        };
    }
    
    /**
     * 清空播放队列（用于打断）
     */
    flush() {
        this.sources.forEach(source => {
            try { source.stop(); } catch (e) {}
        });
        this.sources = [];
        this.nextTime = 0;
    }
    
    /**
     * 关闭播放器
     */
    close() {
        this.ctx.close();
    }
}

// ============ 欢迎语配置 ============
// 中性欢迎语，适合各年龄段用户，尤其适合老人聊天访谈场景
const welcomeTexts = [
    '你好呀，今天心情怎么样？',
    '今天想聊点什么？',
    '欢迎回来，有什么想说的吗？',
    '好久不见，最近还好吗？',
    '今天天气不错，心情如何？',
    '随便聊聊吧，你想说什么都行',
    '我在这里，随时听你说',
    '有些故事值得被记录，想聊聊吗？',
    '今天有什么有趣的事吗？',
    '慢慢说，我在这呢'
];
let welcomeIndex = 0;
let welcomeInterval = null;

// ============ 计时器状态 ============
let timerSeconds = 0;
let timerInterval = null;
let timerRunning = false;

// ============ 初始化入口 ============
document.addEventListener('DOMContentLoaded', () => {
    console.log('[应用] 语音学习助手启动');
    
    // 初始化欢迎语动画
    initWelcomeAnimation();
    
    // 后台静默进行飞书免登
    initFeishuAuth();
    
    // 绑定事件
    bindEvents();
});

// ============ 飞书免登（后台静默） ============
/**
 * 初始化飞书免登认证
 * 静默在后台进行，不影响用户看到欢迎页面
 */
async function initFeishuAuth() {
    // 检查 SDK 是否成功加载
    if (typeof tt === 'undefined') {
        console.warn('[飞书] tt 对象未定义，非飞书环境');
        addLog('⚠️ 非飞书环境，部分功能受限');
        return;
    }

    console.log('[飞书] 开始免登认证...');
    
    try {
        // 从后端获取飞书配置（包含 appId）
        const configResp = await fetch('/api/config');
        const config = await configResp.json();
        console.log('[飞书] 配置获取成功, appId:', config.feishu_app_id);
        
        // 使用 requestAuthCode API（需要 appId 参数）
        tt.requestAuthCode({
            appId: config.feishu_app_id,
            success(res) {
                AppState.authCode = res.code;
                console.log('[飞书] 免登成功，code:', res.code);
                addLog('✅ 飞书免登成功');
                // code 已缓存，实际鉴权在 WebSocket 建立时完成
            },
            fail(err) {
                console.error('[飞书] 免登失败:', err);
                addLog('❌ 飞书免登失败: ' + JSON.stringify(err));
            }
        });
    } catch (err) {
        console.error('[飞书] 配置获取失败:', err);
        addLog('❌ 飞书配置获取失败: ' + err.message);
    }
}

// ============ 欢迎语动画 ============
/**
 * 初始化欢迎语动画
 */
function initWelcomeAnimation() {
    // 立即显示第一条欢迎语
    showWelcome(welcomeTexts[0]);
    
    // 每 5 秒切换一次欢迎语
    welcomeInterval = setInterval(() => {
        if (AppState.current === 'idle') {
            cycleWelcome();
        }
    }, 5000);
}

/**
 * 显示欢迎语（带淡入淡出动画）
 * @param {string} text - 要显示的文字
 */
function showWelcome(text) {
    const welcomeEl = document.getElementById('welcome-text');
    if (!welcomeEl) return;
    
    // 重置动画
    welcomeEl.style.animation = 'none';
    welcomeEl.offsetHeight; // 触发重排
    welcomeEl.textContent = text;
    welcomeEl.style.animation = 'fadeInOut 4s ease-in-out forwards';
}

/**
 * 循环切换欢迎语
 */
function cycleWelcome() {
    welcomeIndex = (welcomeIndex + 1) % welcomeTexts.length;
    showWelcome(welcomeTexts[welcomeIndex]);
}

// ============ 状态机管理 ============
/**
 * 设置应用状态
 * @param {string} state - 目标状态 (idle/connecting/active)
 */
function setState(state) {
    const app = document.getElementById('app');
    if (!app) return;
    
    const previousState = AppState.current;
    AppState.current = state;
    
    // 更新 data-state 属性
    app.setAttribute('data-state', state);
    
    console.log(`[状态机] ${previousState} → ${state}`);
    
    // 状态相关逻辑
    switch (state) {
        case 'idle':
            stopTimer();
            resetTimer();
            // 立即显示正常欢迎语（修复挂断后显示"连接中..."的问题）
            showWelcome(welcomeTexts[0]);
            // 恢复欢迎语动画
            if (!welcomeInterval) {
                welcomeInterval = setInterval(() => {
                    if (AppState.current === 'idle') {
                        cycleWelcome();
                    }
                }, 5000);
            }
            break;
            
        case 'connecting':
            // 停止欢迎语动画
            if (welcomeInterval) {
                clearInterval(welcomeInterval);
                welcomeInterval = null;
            }
            // 显示连接中提示
            showWelcome('连接中...');
            break;
            
        case 'active':
            // 停止欢迎语动画
            if (welcomeInterval) {
                clearInterval(welcomeInterval);
                welcomeInterval = null;
            }
            startTimer();
            triggerVibrate('short');
            addLog('📞 通话已接通');
            break;
    }
}

// ============ 拨号/挂断逻辑 ============
/**
 * 开始通话流程
 * 1. 请求麦克风权限
 * 2. 获取飞书配置
 * 3. 拉取飞书免登 Code
 * 4. 建立 WebSocket 连接
 */
async function handleDial() {
    if (AppState.current !== 'idle') {
        console.warn('[拨号] 当前状态不允许拨号:', AppState.current);
        return;
    }
    
    setState('connecting');
    addLog('📞 正在连接语音模型...');
    
    try {
        // 1. 请求麦克风权限
        addLog('🎤 请求麦克风权限...');
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true }
        });
        addLog('✅ 麦克风已就绪');
        
        // 2. 从后端获取动态配置
        const configResp = await fetch('/api/config');
        const config = await configResp.json();
        
        // 3. 拉取飞书免登 Code
        if (typeof tt === 'undefined') {
            throw new Error('不在飞书环境中');
        }
        
        // 使用已有的 authCode 或重新获取
        let token = AppState.authCode;
        if (!token) {
            token = await new Promise((resolve, reject) => {
                tt.requestAuthCode({
                    appId: config.feishu_app_id,
                    success(res) { resolve(res.code); },
                    fail(err) { reject(err); }
                });
            });
            AppState.authCode = token;
        }
        
        // 4. 建立 WebSocket 连接
        connectWebSocket(token);
        
    } catch (err) {
        console.error('[拨号] 连接失败:', err);
        addLog('❌ 连接失败: ' + err.message);
        setState('idle');
        cleanup();
    }
}

/**
 * 建立 WebSocket 连接
 * @param {string} token - 飞书授权码
 */
function connectWebSocket(token) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/session`;
    
    ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    player = new PCMPlayer(24000);
    
    ws.onopen = () => {
        addLog('✅ WebSocket 已连接');
        
        // 优先从缓存获取 session_id，支持断线重连
        let sessionId = sessionStorage.getItem('doubao_session_id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now();
            sessionStorage.setItem('doubao_session_id', sessionId);
        }
        
        // 发送启动配置
        ws.send(JSON.stringify({
            type: 'start_session',
            session_id: sessionId,
            token: token
        }));
        
        setState('active');
        startRecordingAndSending();
    };
    
    ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
            const data = JSON.parse(event.data);
            
            // 拦截打断信号
            if (data.type === 'interrupt') {
                if (player) player.flush();
                addLog('🛑 已打断');
            }
            // AI 主动结束会话
            else if (data.message === 'session_ended_by_ai') {
                addLog('🤖 通话已结束');
                sessionStorage.removeItem('doubao_session_id');
                cleanup();
                setState('idle');
            } else {
                addLog(`📥 ${data.message || JSON.stringify(data)}`);
            }
        } else {
            // 收到二进制音频流，直接播放
            player.play(event.data);
        }
    };
    
    ws.onclose = () => {
        addLog('❌ 连接已断开');
        cleanup();
        setState('idle');
    };
    
    ws.onerror = (err) => {
        console.error('[WebSocket] 错误:', err);
        addLog('❌ 连接错误');
    };
}

/**
 * 启动音频采集与发送（16kHz 上行）
 */
function startRecordingAndSending() {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(mediaStream);
    
    // 使用 ScriptProcessorNode 捕获音频流
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    source.connect(processor);
    processor.connect(audioContext.destination);
    
    const sampleRate = audioContext.sampleRate;
    const targetSampleRate = 16000;
    
    processor.onaudioprocess = (e) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        if (AppState.isMuted) return;  // 静音时不发送
        
        const inputData = e.inputBuffer.getChannelData(0);
        
        // 线性降采样到 16kHz
        const ratio = sampleRate / targetSampleRate;
        const newLength = Math.round(inputData.length / ratio);
        const result = new Int16Array(newLength);
        
        for (let i = 0; i < newLength; i++) {
            const index = Math.floor(i * ratio);
            // Float32 (-1 to 1) 转换为 16-bit PCM
            const s = Math.max(-1, Math.min(1, inputData[index]));
            result[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // 发送给后端
        ws.send(result.buffer);
    };
    
    addLog('🎙️ 开始发送音频流...');
}

/**
 * 挂断通话
 */
function handleHangup() {
    if (AppState.current !== 'active') {
        console.warn('[挂断] 当前状态不允许挂断:', AppState.current);
        return;
    }
    
    addLog('📴 结束通话，时长: ' + formatTime(timerSeconds));
    sessionStorage.removeItem('doubao_session_id');
    
    // 发送优雅结束指令
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'finish_session' }));
        setTimeout(() => { if (ws) ws.close(); }, 500);
    }
    
    triggerVibrate('long');
    cleanup();
    setState('idle');
}

/**
 * 清理资源
 */
function cleanup() {
    // 重置静音状态
    AppState.isMuted = false;
    const muteBtn = document.getElementById('btn-mute');
    if (muteBtn) {
        const icon = muteBtn.querySelector('span');
        if (icon) icon.textContent = '🎤';
    }
    
    if (processor) { processor.disconnect(); processor = null; }
    if (audioContext) { audioContext.close(); audioContext = null; }
    if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
    if (player) { player.close(); player = null; }
    if (ws) { ws = null; }
}

// ============ 计时器管理 ============
/**
 * 格式化时间显示
 * @param {number} seconds - 秒数
 * @returns {string} 格式化的时间字符串
 */
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 更新计时器显示
 */
function updateTimerDisplay() {
    const timerEl = document.getElementById('call-timer');
    if (timerEl) {
        timerEl.textContent = formatTime(timerSeconds);
    }
}

/**
 * 启动计时器
 */
function startTimer() {
    if (timerRunning) return;
    timerRunning = true;
    
    timerInterval = setInterval(() => {
        timerSeconds++;
        updateTimerDisplay();
    }, 1000);
    
    console.log('[计时器] 已启动');
}

/**
 * 停止计时器
 */
function stopTimer() {
    if (!timerRunning) return;
    timerRunning = false;
    
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    
    console.log('[计时器] 已停止');
}

/**
 * 重置计时器
 */
function resetTimer() {
    timerSeconds = 0;
    updateTimerDisplay();
    console.log('[计时器] 已重置');
}

// ============ 静音控制 ============
/**
 * 切换静音状态（硬件级隐私控制）
 */
function toggleMute() {
    AppState.isMuted = !AppState.isMuted;
    
    // 🔒 硬件级隐私控制：同步切换麦克风轨道启用状态
    if (mediaStream) {
        const audioTrack = mediaStream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.enabled = !AppState.isMuted;
        }
    }
    
    // 更新按钮 UI
    const muteBtn = document.getElementById('btn-mute');
    if (muteBtn) {
        const icon = muteBtn.querySelector('span');
        if (icon) {
            icon.textContent = AppState.isMuted ? '🔇' : '🎤';
        }
    }
    
    // WebSocket 状态安全检查后再发送
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "mic_status", muted: AppState.isMuted }));
    }
    
    triggerVibrate('short');
    addLog(AppState.isMuted ? '🔇 已静音' : '🎤 已取消静音');
    console.log('[静音]', AppState.isMuted ? '开启' : '关闭');
}

// ============ 震动反馈 ============
/**
 * 触发震动反馈
 * @param {string} type - 震动类型 (short/long)
 */
function triggerVibrate(type) {
    // 尝试飞书 API
    if (typeof tt !== 'undefined') {
        if (type === 'long' && tt.vibrateLong) {
            tt.vibrateLong();
            console.log('[震动] 飞书 vibrateLong');
            return;
        } else if (tt.vibrateShort) {
            tt.vibrateShort();
            console.log('[震动] 飞书 vibrateShort');
            return;
        }
    }
    
    // 尝试原生 Vibration API
    if ('vibrate' in navigator) {
        const duration = type === 'long' ? 400 : 100;
        navigator.vibrate(duration);
        console.log('[震动] 原生 API:', duration, 'ms');
    }
}

// ============ 日志抽屉 ============
/**
 * 切换日志抽屉显示
 */
function toggleDrawer() {
    const drawer = document.getElementById('log-drawer');
    if (drawer) {
        drawer.classList.toggle('show');
    }
}

/**
 * 隐藏日志抽屉
 */
function hideDrawer() {
    const drawer = document.getElementById('log-drawer');
    if (drawer) {
        drawer.classList.remove('show');
    }
}

/**
 * 添加日志记录
 * @param {string} message - 日志消息
 */
function addLog(message) {
    const logContent = document.getElementById('log-content');
    if (!logContent) return;
    
    // 清除初始占位文本
    if (logContent.querySelector('p:only-child') && logContent.textContent === '暂无对话记录...') {
        logContent.innerHTML = '';
    }
    
    const time = new Date().toLocaleTimeString();
    const logEntry = document.createElement('p');
    logEntry.textContent = `[${time}] ${message}`;
    logEntry.style.marginBottom = '8px';
    logContent.appendChild(logEntry);
    
    // 滚动到底部
    logContent.scrollTop = logContent.scrollHeight;
}

// ============ 事件绑定 ============
/**
 * 绑定所有 UI 事件
 */
function bindEvents() {
    // 拨号按钮
    const dialBtn = document.getElementById('btn-dial');
    if (dialBtn) {
        dialBtn.addEventListener('click', handleDial);
    }
    
    // 挂断按钮
    const hangupBtn = document.getElementById('btn-hangup');
    if (hangupBtn) {
        hangupBtn.addEventListener('click', handleHangup);
    }
    
    // 静音按钮
    const muteBtn = document.getElementById('btn-mute');
    if (muteBtn) {
        muteBtn.addEventListener('click', toggleMute);
    }
    
    // 日志抽屉开关
    const toggleLogBtn = document.getElementById('btn-toggle-log');
    if (toggleLogBtn) {
        toggleLogBtn.addEventListener('click', toggleDrawer);
    }
    
    const closeLogBtn = document.getElementById('btn-close-log');
    if (closeLogBtn) {
        closeLogBtn.addEventListener('click', hideDrawer);
    }
    
    console.log('[事件] 所有事件已绑定');
}

// ============ 暴露全局方法（供调试） ============
window.AppState = AppState;
window.setState = setState;
window.handleDial = handleDial;
window.handleHangup = handleHangup;
window.addLog = addLog;