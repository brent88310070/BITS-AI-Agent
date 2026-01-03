# ============================================================
# 🎨 CSS 樣式表
# ============================================================

CUSTOM_CSS = """
/* --- 基礎重置與排版 --- */
footer { display: none !important; }
.gradio-container { max-width: 100% !important; padding: 0 20px !important; }

/* 隱藏捲動條但保留功能 */
.mode-box, .chatbot-container { overflow: visible !important; }
.mode-box::-webkit-scrollbar { display: none; width: 0px; background: transparent; }
.mode-box { -ms-overflow-style: none; scrollbar-width: none; }

/* 修正頂部對齊：強制移除多餘邊距 */
.sidebar-container, .chatbot-column {
    padding-top: 0 !important; 
}
/* 確保左側第一張卡片與右側聊天窗頂部切齊 */
.first-card {
    margin-top: 0 !important;
}
.chatbot-container {
    margin-top: 0 !important;
}

/* ========================================= */
/* 🌞 白天模式 (預設) */
/* ========================================= */

body {
    background-color: #e5e7eb !important; /* 背景：稍深灰 */
}

/* 左側邊欄容器 */
.sidebar-container {
    background-color: transparent !important;
    padding: 0 15px 15px 15px !important; /* 上方 padding 設為 0 */
    height: 100% !important;
}

/* 卡片通用樣式 */
.sidebar-card {
    background-color: #f3f4f6 !important; /* 卡片：淺灰白 */
    border-radius: 12px !important;
    padding: 16px 20px !important;
    margin-bottom: 16px !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1) !important;
    border: 1px solid #d1d5db !important;
}

.sidebar-card span, .sidebar-card p, .sidebar-card label, .gradio-input-label {
    color: #374151 !important;
}
.sidebar-card h3 {
    color: #111827 !important;
    font-weight: 600 !important;
    margin-bottom: 0 !important;
}

/* ★★★ 聊天視窗樣式 (白晝) ★★★ */
.chatbot-container {
    background-color: #ffffff !important; /* 純白背景 */
    border: 1px solid #d1d5db !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    padding: 10px !important;
}

/* ★★★ 輸入框樣式 (白晝) ★★★ */
.input-container textarea {
    background-color: #ffffff !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important; /* 陰影 */
    border: 1px solid #d1d5db !important;
    border-radius: 10px !important;
}
.input-container textarea:focus {
    border-color: #6366f1 !important; /* 聚焦時變色 */
    box-shadow: 0 4px 10px -1px rgba(99, 102, 241, 0.2) !important;
}

/* 標題區塊 */
.header-container {
    text-align: center;
    padding: 10px 0 20px 0 !important;
    color: #1f2937;
}
.header-title { font-size: 2em !important; font-weight: 700; color: #111827 !important; }
.header-subtitle { font-size: 1em !important; color: #4b5563 !important; }

/* ========================================= */
/* 🌙 夜晚模式 (.dark) */
/* ========================================= */

body.dark {
    background-color: #0f172a !important; /* 背景：深藍黑 */
}

.dark .sidebar-card {
    background-color: #1e293b !important; /* 卡片：深藍灰 */
    border: 1px solid #334155 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5) !important;
}

.dark .sidebar-card span, .dark .sidebar-card p, .dark .sidebar-card label, .dark .gradio-input-label {
    color: #cbd5e1 !important;
}
.dark .sidebar-card h3 {
    color: #f1f5f9 !important;
}

/* ★★★ 聊天視窗樣式 (黑夜) ★★★ */
.dark .chatbot-container {
    background-color: #1e293b !important;
    border: 1px solid #334155 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5) !important;
}

/* ★★★ 輸入框樣式 (黑夜) ★★★ */
.dark .input-container textarea {
    background-color: #1e293b !important;
    color: #f3f4f6 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
    border: 1px solid #334155 !important;
}
.dark .input-container textarea:focus {
    border-color: #818cf8 !important;
}

.dark .header-title { color: #f1f5f9 !important; }
.dark .header-subtitle { color: #94a3b8 !important; }

/* ========================================= */
/* 🔘 Switch 按鈕樣式 */
/* ========================================= */

.header-row {
    align-items: center !important;
    margin-bottom: 12px !important;
    display: flex !important;
}

.theme-switch-btn {
    position: relative !important;
    width: 50px !important;
    height: 26px !important;
    border-radius: 13px !important;
    background-color: #d1d5db !important;
    border: none !important;
    padding: 0 !important;
    cursor: pointer;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.1) !important;
    display: block !important;
    min-width: auto !important;
}

/* 滑塊 */
.theme-switch-btn::after {
    content: '🌞';
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 2px;
    left: 2px;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background-color: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
}

/* 夜晚模式狀態 */
.dark .theme-switch-btn {
    background-color: #6366f1 !important;
}
.dark .theme-switch-btn::after {
    transform: translateX(24px);
    content: '🌜';
    background-color: #1e293b;
    color: #fbbf24;
}
"""

# JavaScript 切換邏輯
JS_TOGGLE_THEME = """
function() {
    const body = document.querySelector('body');
    body.classList.toggle('dark');
}
"""