import gradio as gr 
import pandas as pd
import json
from qdrant_client import QdrantClient
from qdrant_client.http import models

# ================= 設定區 =================
QDRANT_PATH = "qdrant_db" 
client = QdrantClient(path=QDRANT_PATH) 
# =========================================

def get_collections():
    try:
        collections = client.get_collections().collections
        return [c.name for c in collections]
    except Exception as e:
        print(f"Error fetching collections: {e}")
        return []

def truncate_text(text, max_len=50):
    if not isinstance(text, str):
        return text
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text

def load_data(collection_name, limit=20, search_query=""):
    """
    讀取資料
    回傳: DataFrame, Full_Data, Editor區塊顯示狀態, Table區塊顯示狀態
    """
    # 預設隱藏狀態
    hide_ui = gr.update(visible=False)
    show_ui = gr.update(visible=True)
    empty_df = pd.DataFrame()

    if not collection_name:
        return empty_df, [], hide_ui, hide_ui
    
    try:
        # --- 建構搜尋過濾器 ---
        query_filter = None
        if search_query.strip():
            search_text = search_query.strip()
            query_filter = models.Filter(
                should=[
                    models.FieldCondition(key="page_content", match=models.MatchText(text=search_text)),
                    models.FieldCondition(key="text", match=models.MatchText(text=search_text)),
                    models.FieldCondition(key="title", match=models.MatchText(text=search_text)),
                    models.FieldCondition(key="filename", match=models.MatchText(text=search_text)),
                ]
            )

        # --- 使用 Scroll API ---
        records, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=query_filter, 
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        full_data = [] 
        display_data = [] 

        for r in records:
            item = r.payload if r.payload else {}
            item_id = str(r.id)
            
            full_item = {"id": item_id}
            full_item.update(item)
            full_data.append(full_item)

            display_item = {"id": item_id}
            for k, v in item.items():
                display_item[k] = truncate_text(v, max_len=60)
            display_data.append(display_item)
            
        # 如果沒資料，回傳空並隱藏區塊
        if not full_data:
            print("🔍 找不到符合條件的資料")
            return empty_df, [], hide_ui, hide_ui
            
        df_display = pd.DataFrame(display_data)
        
        # 處理顯示欄位 (Select + ID + 其他)
        cols = ['id'] + [c for c in df_display.columns if c != 'id']
        df_display = df_display[cols]
        df_display.insert(0, "Select", False) 

        print(f"✅ 成功讀取 {len(full_data)} 筆資料")
        
        # 資料存在，回傳 show_ui 將區塊打開
        return df_display, full_data, show_ui, show_ui

    except Exception as e:
        print(f"❌ 讀取錯誤: {str(e)}")
        return empty_df, [], hide_ui, hide_ui

def batch_delete_data(collection_name, df_data):
    if not collection_name: return "⚠️ 請先選擇 Collection"
    if df_data is None or df_data.empty: return "⚠️ 無資料可刪除"
    
    selected_rows = df_data[df_data["Select"] == True]
    if selected_rows.empty: return "⚠️ 未勾選任何資料"

    ids_to_delete = selected_rows["id"].tolist()
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=ids_to_delete)
        )
        return f"🗑️ 成功刪除 {len(ids_to_delete)} 筆資料: {ids_to_delete}"
    except Exception as e:
        return f"❌ 刪除失敗: {str(e)}"

def save_payload(collection_name, target_id, new_payload_str):
    if not collection_name or not target_id: return "⚠️ 請先選擇資料"
    try:
        new_payload = json.loads(new_payload_str)
        client.overwrite_payload(
            collection_name=collection_name,
            payload=new_payload,
            points=[target_id]
        )
        return f"💾 成功更新 ID: {target_id}"
    except Exception as e:
        return f"❌ 更新失敗: {str(e)}"

# ================= UI 介面 =================

custom_css = """
.delete-btn {
    background-color: #dc2626 !important; 
    color: white !important;
    border: 1px solid #b91c1c !important;
}
.delete-btn:hover {
    background-color: #ef4444 !important;
}
"""

with gr.Blocks(title="Qdrant 資料庫管理", theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown("# BitsAI - Qdrant DB Manager")
    
    # === State ===
    full_data_state = gr.State([]) 
    selected_id_state = gr.State(None)
    
    # --- 1. 頂部操作區 (永遠顯示) ---
    with gr.Row():
        with gr.Column(scale=2):
            col_selector = gr.Dropdown(choices=get_collections(), label="選擇 Collection", interactive=True)
        with gr.Column(scale=4): 
            with gr.Group():
                with gr.Row():
                    search_box = gr.Textbox(label="🔍 搜尋", placeholder="關鍵字...", scale=2)
                    limit_slider = gr.Slider(5, 200, 20, step=5, label="筆數", scale=2)
        with gr.Column(scale=1, min_width=150):
            load_btn = gr.Button("🚀 讀取資料", variant="primary")
            refresh_btn = gr.Button("🔄 列表重整")

    gr.Markdown("---") 

    # --- 2. 編輯器區塊 (預設隱藏 visible=False) ---
    # [修改點 1] 包在 Group 裡並設為 hidden，等有資料才 show
    with gr.Column(visible=False) as editor_layout:
        with gr.Accordion("📝 單筆詳細資料編輯器 (點擊下方表格帶入)", open=True):

            json_editor = gr.Code(label="JSON 內容", language="json", interactive=True, lines=8)

            with gr.Row():
                id_display = gr.Textbox(show_label=False, placeholder="目前選取 ID", interactive=False, 
                                        scale=4,container=False)
                save_btn = gr.Button("💾 儲存修改", variant="secondary", scale=1)

    # --- 3. 資料列表與批次操作 (預設隱藏 visible=False) ---
    # [修改點 1] 包在 Group 裡並設為 hidden
    with gr.Group(visible=False) as table_layout:
        gr.Markdown("### 📋 資料列表")
        
        data_table = gr.Dataframe(
            interactive=True, 
            wrap=False,
            datatype=["bool"] + ["str"] * 10,
            col_count=(1, "fixed"),
            type="pandas"
        )
        
        with gr.Row():
            batch_delete_btn = gr.Button(
                "🗑️ 刪除勾選資料", 
                variant="stop", 
                elem_classes=["delete-btn"], 
                scale=1
            )

        # with gr.Row():
        #     # 1. 第一層：初始刪除按鈕
        #     btn_step1_delete = gr.Button(
        #         "🗑️ 刪除勾選資料", 
        #         variant="stop", 
        #         scale=1
        #     )
            
        #     # 2. 第二層：確認區塊 (預設隱藏 visible=False)
        #     with gr.Row(visible=False) as confirm_box:
        #         gr.Markdown("⚠️ **確定刪除選取資料？無法復原！**", show_label=False)
        #         # 真正的刪除按鈕 (紅色)
        #         batch_delete_btn = gr.Button(
        #             "✅ 確定刪除", 
        #             variant="stop", 
        #             elem_classes=["delete-btn"], # 套用原本的強制紅色 CSS
        #             scale=1
        #         )
        #         # 取消按鈕 (灰色)
        #         btn_step2_cancel = gr.Button(
        #             "❌ 取消", 
        #             variant="secondary", 
        #             scale=1
        #         )
        
    # ================= 事件綁定 =================
    
    refresh_btn.click(lambda: gr.update(choices=get_collections()), outputs=col_selector)
    
    # [關鍵修改] load_data 增加了兩個 output 來控制 layout 的 visibility
    load_btn.click(
        fn=load_data, 
        inputs=[col_selector, limit_slider, search_box], 
        outputs=[data_table, full_data_state, editor_layout, table_layout]
    )
    
    # 表格選取事件
    def on_select(evt: gr.SelectData, full_data):
        if not full_data: return None, None, "{}"
        row_index = evt.index[0]
        if row_index < len(full_data):
            item = full_data[row_index]
            target_id = item.get("id", "")
            payload = {k: v for k, v in item.items() if k != 'id'}
            return target_id, target_id, json.dumps(payload, indent=4, ensure_ascii=False)
        return None, None, "{}"

    data_table.select(
        on_select, 
        inputs=[full_data_state],
        outputs=[selected_id_state, id_display, json_editor]
    )

    # 儲存事件
    def run_save(col, tid, json_txt, current_search, current_limit):
        msg = save_payload(col, tid, json_txt)
        print(f"[Save] {msg}")
        # 儲存後重新載入，並保持介面顯示 (True, True)
        new_df, new_full, _, _ = load_data(col, current_limit, current_search) 
        return new_df, new_full

    save_btn.click(
        fn=run_save,
        inputs=[col_selector, selected_id_state, json_editor, search_box, limit_slider],
        outputs=[data_table, full_data_state]
    )

    # 刪除事件
    def run_batch_delete(col, df, current_search, current_limit):
        msg = batch_delete_data(col, df)
        print(f"[Batch Delete] {msg}") 
        
        # 刪除後重新載入，load_data 會自動判斷是否還有資料來決定是否隱藏
        new_df, new_full, show_editor, show_table = load_data(col, current_limit, current_search)
        
        return new_df, new_full, show_editor, show_table, None, "", "{}"

    batch_delete_btn.click(
        fn=run_batch_delete,
        inputs=[col_selector, data_table, search_box, limit_slider],
        outputs=[data_table, full_data_state, editor_layout, table_layout, selected_id_state, id_display, json_editor]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)