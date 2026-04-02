document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("app");
    const textEl = document.getElementById("welcome-text");
    const timerEl = document.getElementById("call-timer");
    const logDrawer = document.getElementById("log-drawer");
    
    let timerInterval = null;
    let secondsElapsed = 0;
    
    // 问候语轮播库 (专为长辈设计的温和语料)
    const greetings = [
        "外婆，今天想聊点什么？",
        "最近身体感觉怎么样？",
        "今天天气不错，出去走走没？",
        "有没有什么开心的事和我分享？",
        "肚子饿不饿，记得按时吃饭哦。"
    ];
    let greetingIdx = 0;

    /**
     * 轮播并触发文字呼吸动画 (配合 CSS 的 9s 周期)
     */
    function rotateWelcomeText() {
        if (app.getAttribute("data-state") !== "idle") return;
        
        textEl.textContent = greetings[greetingIdx];
        greetingIdx = (greetingIdx + 1) % greetings.length;
        
        // 强制触发重绘以重启 CSS 动画
        textEl.style.animation = 'none';
        void textEl.offsetWidth; 
        textEl.style.animation = 'fadeInOut 9s forwards';
    }
    
    // 初始化并启动轮播 (每9秒切换一次)
    rotateWelcomeText();
    const textTimer = setInterval(rotateWelcomeText, 9000);

    /**
     * 适老化精准震动反馈封装 (优先调用飞书底层 API)
     * @param {'short'|'long'|'double'} type 
     */
    function triggerHaptics(type = 'short') {
        try {
            // 优先飞书环境
            if (typeof tt !== 'undefined' && tt.vibrateShort) {
                if (type === 'long' && tt.vibrateLong) {
                    tt.vibrateLong();
                } else if (type === 'double') {
                    tt.vibrateShort();
                    setTimeout(() => tt.vibrateShort(), 200);
                } else {
                    tt.vibrateShort();
                }
            } 
            // 降级使用浏览器标准 H5 API
            else if (navigator.vibrate) {
                if (type === 'long') navigator.vibrate(400);
                else if (type === 'double') navigator.vibrate([100, 100, 100]);
                else navigator.vibrate(100);
            }
        } catch (e) {
            console.warn("Haptics not supported on this device.");
        }
    }

    /**
     * 通话计时器控制
     */
    function handleTimer(action) {
        if (action === 'start') {
            secondsElapsed = 0;
            timerEl.textContent = "00:00";
            timerInterval = setInterval(() => {
                secondsElapsed++;
                const m = String(Math.floor(secondsElapsed / 60)).padStart(2, '0');
                const s = String(secondsElapsed % 60).padStart(2, '0');
                timerEl.textContent = `${m}:${s}`;
            }, 1000);
        } else if (action === 'stop') {
            if (timerInterval) clearInterval(timerInterval);
            timerEl.textContent = "00:00";
        }
    }

    /**
     * 核心 UI 状态机映射函数
     * 仅操作顶层 data-state，由 CSS 完成视觉转换
     */
    function setAppState(state) {
        app.setAttribute("data-state", state);
        
        if (state === "idle") {
            handleTimer('stop');
            rotateWelcomeText(); // 恢复问候语
        } else if (state === "active") {
            handleTimer('start');
        }
    }

    // --- 事件绑定区 ---

    // 拨打大按钮
    document.getElementById("btn-dial").addEventListener("click", () => {
        triggerHaptics('long');
        setAppState("connecting");
        
        // 模拟 1.5 秒后接通，执行两次短震并进入活跃态
        setTimeout(() => {
            triggerHaptics('double');
            setAppState("active");
        }, 1500);
    });

    // 挂断按钮
    document.getElementById("btn-hangup").addEventListener("click", () => {
        triggerHaptics('short');
        setAppState("idle");
    });

    // 静音按钮 (仅作 UI 视觉反馈示例)
    document.getElementById("btn-mute").addEventListener("click", (e) => {
        triggerHaptics('short');
        const isMuted = e.currentTarget.classList.toggle("muted");
        e.currentTarget.style.backgroundColor = isMuted ? "var(--btn-red)" : "var(--btn-glass)";
        e.currentTarget.style.color = isMuted ? "white" : "var(--text-primary)";
    });

    // 日志抽屉呼出与收起
    document.getElementById("btn-toggle-log").addEventListener("click", () => {
        triggerHaptics('short');
        logDrawer.classList.add("show");
    });
    
    document.getElementById("btn-close-log").addEventListener("click", () => {
        triggerHaptics('short');
        logDrawer.classList.remove("show");
    });
});