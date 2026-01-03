import gradio as gr
import os
import bitsAI_core as core
import time
from bitsAI_css import CUSTOM_CSS, JS_TOGGLE_THEME

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
# 💬 對話包裝函式
# ============================================================
def respond_wrapper(message, chat_history):
    if not message.strip():
        return "", chat_history
    
    response_text = core.generate_response(message, current_mode)
    chat_history.append((message, response_text))
    return "", chat_history

def upload_files_handler(title, doc_type, files, use_marker):
    try:
        result = core.process_upload_files(title=title, doc_type=doc_type, files=files, use_marker=use_marker)
        return result
    except Exception as e:
        return f"❌ 處理失敗: {str(e)}"

# ============================================================
# 🎨 Gradio Layout (App Structure)
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

    # 這裡的 equal_height=False 很重要，讓內容自然堆疊
    with gr.Row(equal_height=False, elem_classes=["main-row"]):
        
        # --- 左側控制欄 ---
        with gr.Column(scale=1, min_width=300, elem_classes="sidebar-container"):
            
            # [修改點] 這裡加上了 "first-card" class，配合 CSS 強制頂部對齊
            with gr.Column(elem_classes=["sidebar-card", "first-card"]):
                with gr.Row(elem_classes=["header-row"]):
                    with gr.Column(scale=1, min_width=0): 
                        gr.Markdown("### 模式切換")
                    
                    with gr.Column(scale=0, min_width=60):
                        theme_btn = gr.Button(value="", elem_classes=["theme-switch-btn"])

                with gr.Group():
                    toggle_tool_btn = gr.Button(LABELS[current_mode][0], variant="secondary")
                    toggle_rag_btn = gr.Button(LABELS[current_mode][1], variant="secondary")
            
            # --- 事件綁定 ---
            theme_btn.click(None, None, None, js=JS_TOGGLE_THEME)
            toggle_tool_btn.click(lambda: set_mode(core.Mode.TOOLS), None, [toggle_tool_btn, toggle_rag_btn])
            toggle_rag_btn.click(lambda: set_mode(core.Mode.RAG), None, [toggle_tool_btn, toggle_rag_btn])

            # --- 知識庫 ---
            with gr.Column(elem_classes="sidebar-card"):
                gr.Markdown("### 知識庫管理")
                with gr.Group():
                    title_file = gr.Textbox(label="文檔標題", placeholder="例如：2025 研究結果")
                    file_type = gr.Dropdown(label="內容類型", choices=["people", "paper", "other"], value="other")
                    file_input = gr.Files(label="選擇檔案")
                    use_marker_chk = gr.Checkbox(label="啟用 Marker (PDF 高精度轉換)", value=False, info="轉換速度較慢，但能更精準處理複雜 PDF 排版")
                    upload_btn = gr.Button("轉換並建立知識庫", variant="primary")
                    upload_out = gr.Markdown()

                    upload_btn.click(
                        fn=lambda: (gr.update(interactive=False, value="⏳ 轉換中，請稍候..."), "⏳ 轉換中，請稍候..."),
                        outputs=[upload_btn, upload_out]
                    ).then(
                        fn=upload_files_handler,
                        inputs=[title_file, file_type, file_input, use_marker_chk], 
                        outputs=upload_out
                    ).then(
                        fn=lambda: gr.update(interactive=True, value="儲存至知識庫"),
                        outputs=[upload_btn]
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