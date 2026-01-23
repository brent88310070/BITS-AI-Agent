import gradio as gr
import os
import shutil
import bitsAI_core as core
import time
from bitsAI_css import CUSTOM_CSS, JS_TOGGLE_THEME

# ============================================================
# ⚙️ 上傳限制與路徑設定
# ============================================================
MAX_FILE_SIZE_MB = 100       # 單一檔案最大 100MB
MAX_FILE_COUNT = 100         # 一次上傳最大 100 個檔案
STORAGE_DIR = "data_storage" # VisiData 專用資料夾

# 確保資料夾存在
os.makedirs(STORAGE_DIR, exist_ok=True)

# ============================================================
# 🧠 UI 狀態管理
# ============================================================
current_mode = core.Mode.NORMAL

LABELS = {
    core.Mode.NORMAL: ("🔴 開啟工具模式", "🔴 開啟 RAG 模式"),
    core.Mode.TOOLS:  ("🟢 工具模式已啟用", "🔴 開啟 RAG 模式"),
    core.Mode.RAG:    ("🔴 開啟工具模式", "🟢 RAG 模式已啟用"),
}

def update_ui_state():
    t_label, r_label = LABELS[current_mode]
    t_variant = "primary" if current_mode == core.Mode.TOOLS else "secondary"
    r_variant = "primary" if current_mode == core.Mode.RAG else "secondary"
    return gr.update(value=t_label, variant=t_variant), gr.update(value=r_label, variant=r_variant)

def set_mode(new_mode):
    global current_mode
    current_mode = core.Mode.NORMAL if current_mode == new_mode else new_mode
    return update_ui_state()

# ============================================================
# 📂 檔案處理邏輯
# ============================================================

def validate_files(files):
    """共用的檔案檢查邏輯"""
    if not files:
        return False, "⚠️ 請先選擇檔案。"
    
    if len(files) > MAX_FILE_COUNT:
        return False, f"❌ 上傳失敗：一次最多只能上傳 {MAX_FILE_COUNT} 個檔案。"

    limit_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    for file in files:
        file_path = file.name 
        if os.path.getsize(file_path) > limit_bytes:
            return False, f"❌ 上傳失敗：檔案 '{os.path.basename(file_path)}' 超過 {MAX_FILE_SIZE_MB}MB。"
            
    return True, ""

def rag_upload_handler(title, doc_type, files, use_marker):
    """處理 RAG 知識庫上傳 (透過 Core 處理)"""
    is_valid, msg = validate_files(files)
    if not is_valid:
        return msg

    try:
        # 呼叫 Core 進行向量化
        result = core.process_upload_files(title=title, doc_type=doc_type, files=files, use_marker=use_marker)
        return result
    except Exception as e:
        return f"❌ RAG 處理失敗: {str(e)}"

def storage_upload_handler(files):
    """處理數據中心上傳 (僅儲存到 data_storage)"""
    is_valid, msg = validate_files(files)
    if not is_valid:
        return msg

    saved_count = 0
    logs = []
    
    try:
        for file in files:
            filename = os.path.basename(file.name)
            # 處理檔名重複或直接覆蓋 (這邊選擇直接覆蓋)
            dest_path = os.path.join(STORAGE_DIR, filename)
            
            # 從 Gradio Temp 複製到 data_storage
            shutil.copy(file.name, dest_path)
            saved_count += 1
            logs.append(f"📄 {filename}")
            
        return f"✅ 已儲存 {saved_count} 個檔案至 '{STORAGE_DIR}'：\n" + "\n".join(logs)
    except Exception as e:
        return f"❌ 儲存失敗: {str(e)}"

# ============================================================
# 💬 對話包裝函式
# ============================================================
def respond_wrapper(message, chat_history):
    if not message.strip():
        return "", chat_history
    
    response_text = core.generate_response(message, current_mode)
    chat_history.append((message, response_text))
    return "", chat_history

# ============================================================
# 🎨 Gradio Layout
# ============================================================

theme = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="slate",
    font=[gr.themes.GoogleFont("Noto Sans TC"), "ui-sans-serif", "system-ui"]
)

with gr.Blocks(theme=theme, css=CUSTOM_CSS, fill_width=True) as demo:
    
    gr.HTML(f"""
    <div class="header-container">
        <div class="header-title">BITS-AI Agent</div>
        <div class="header-subtitle">核心模型：<b>{core.LLM_NAME}</b> | 知識庫：<b>Qdrant</b></div>
    </div>
    """)

    with gr.Row(equal_height=False, elem_classes=["main-row"]):
        
        # --- 左側控制欄 ---
        with gr.Column(scale=1, min_width=300, elem_classes="sidebar-container"):
            
            # 卡片 1: 模式切換 (保持在最上方)
            with gr.Column(elem_classes=["sidebar-card", "first-card"]):
                with gr.Row(elem_classes=["header-row"]):
                    with gr.Column(scale=1, min_width=0): 
                        gr.Markdown("### 模式切換")
                    with gr.Column(scale=0, min_width=60):
                        theme_btn = gr.Button(value="", elem_classes=["theme-switch-btn"])

                with gr.Group():
                    toggle_tool_btn = gr.Button(LABELS[current_mode][0], variant="secondary")
                    toggle_rag_btn = gr.Button(LABELS[current_mode][1], variant="secondary")
            
            # 卡片 2: 檔案管理 (使用 Tabs 解決空間問題)
            with gr.Column(elem_classes="sidebar-card"):
                
                # 使用 Tabs 分流不同上傳目的
                with gr.Tabs():
                    
                    # --- Tab 1: RAG 知識庫 ---
                    with gr.TabItem("建立知識庫"):
                        with gr.Group():
                            title_file = gr.Textbox(label="文檔標題", placeholder="例如：2025 研究結果")
                            file_type = gr.Dropdown(label="內容類型", choices=["people", "paper", "other"], value="other")
                            rag_file_input = gr.Files(label="選擇文件 (PDF/MD/TXT)")
                            use_marker_chk = gr.Checkbox(label="啟用 Marker (PDF 高精度)", value=False)
                            
                            rag_upload_btn = gr.Button("轉換並建立知識庫", variant="primary")
                            rag_upload_out = gr.Markdown()

                    # --- Tab 2: 數據中心 (VisiData) ---
                    with gr.TabItem("表格資料中心"):
                        with gr.Group():
                            data_file_input = gr.Files(label="選擇資料")
                            
                            data_upload_btn = gr.Button("上傳至表格資料中心", variant="primary")
                            data_upload_out = gr.Markdown()

            # --- 事件綁定 ---
            theme_btn.click(None, None, None, js=JS_TOGGLE_THEME)
            toggle_tool_btn.click(lambda: set_mode(core.Mode.TOOLS), None, [toggle_tool_btn, toggle_rag_btn])
            toggle_rag_btn.click(lambda: set_mode(core.Mode.RAG), None, [toggle_tool_btn, toggle_rag_btn])

            # RAG 上傳事件
            rag_upload_btn.click(
                fn=lambda: (gr.update(interactive=False, value="⏳ 轉換中..."), "⏳ 轉換中..."),
                outputs=[rag_upload_btn, rag_upload_out]
            ).then(
                fn=rag_upload_handler,
                inputs=[title_file, file_type, rag_file_input, use_marker_chk], 
                outputs=rag_upload_out
            ).then(
                fn=lambda: gr.update(interactive=True, value="轉換並建立知識庫"),
                outputs=[rag_upload_btn]
            )

            # Data Storage 上傳事件
            data_upload_btn.click(
                fn=lambda: (gr.update(interactive=False, value="⏳ 上傳中..."), "⏳ 上傳中..."),
                outputs=[data_upload_btn, data_upload_out]
            ).then(
                fn=storage_upload_handler,
                inputs=[data_file_input],
                outputs=data_upload_out
            ).then(
                fn=lambda: gr.update(interactive=True, value="上傳至數據中心"),
                outputs=[data_upload_btn]
            )

        # --- 右側聊天欄 ---
        with gr.Column(scale=4, elem_classes="chatbot-column"):
            chatbot = gr.Chatbot(
                label="對話互動視窗", 
                height=670,
                show_label=False,
                bubble_full_width=False,
                elem_classes="chatbot-container",
                avatar_images=(None, "lab_agent_icon.png") 
            )
            
            with gr.Row():
                msg = gr.Textbox(
                    label="輸入訊息", 
                    placeholder="在此輸入您的問題...", 
                    show_label=False, 
                    scale=9, 
                    container=False,
                    elem_classes="input-container" 
                )
                submit_btn = gr.Button("發送", variant="primary", scale=1)
            
            with gr.Row():
                clear_btn = gr.Button("清空歷史紀錄", variant="stop")

            msg.submit(respond_wrapper, [msg, chatbot], [msg, chatbot])
            submit_btn.click(respond_wrapper, [msg, chatbot], [msg, chatbot])
            clear_btn.click(lambda: None, None, chatbot, queue=False).then(lambda: core.memory.clear(), None, None)

if __name__ == "__main__":
    demo.queue(max_size=10).launch(server_name="0.0.0.0", server_port=7860, show_api=False)