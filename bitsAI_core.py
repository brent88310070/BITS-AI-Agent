import os
import subprocess
import uuid
import time
from datetime import datetime
import json
from enum import Enum

from langchain_ollama import ChatOllama
from qdrant_client import QdrantClient
from qdrant_client import models

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.documents import Document

from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from langchain_community.document_loaders import TextLoader

from markitdown import MarkItDown

from bitsAI_tools import TOOLS, create_tool_agent

# ============================================================
# ⚙️ 全域設定與 Enum
# ============================================================
LLM_NAME = "qwen3:1.7b"
SUMMARIZER_LLM_NAME = LLM_NAME 
QDRANT_PATH = "qdrant_db"
COLLECTION_NAME = "lab_knowledge"

# 設定保留最近幾輪對話 (1輪 = User + AI)
MEMORY_WINDOW_ROUNDS = 3

class Mode(Enum):
    NORMAL = 0
    TOOLS = 1
    RAG = 2

# ============================================================
# 🤖 Agent 初始化
# ============================================================
# General Agent
agent_general = ChatOllama(model=LLM_NAME, temperature=0.1)

# 工具 Agent
agent_tools = create_tool_agent(LLM_NAME, TOOLS)

# RAG 專用 LLM
rag_llm = ChatOllama(model=LLM_NAME, temperature=0.1)

# 摘要專用 LLM
summarizer_llm = ChatOllama(model=SUMMARIZER_LLM_NAME, temperature=0.1)

# ============================================================
# 🧠 Summarized Short-Term Memory 實作
# ============================================================

class ChatMemory:
    def __init__(self, llm, keep_rounds=5):
        self.llm = llm
        self.keep_rounds = keep_rounds
        self.summary = "" 
        self.buffer = []  

    def get_messages(self, system_instruction: str = "") -> list[BaseMessage]:
        full_system_text = system_instruction
        if self.summary:
            full_system_text += f"\n\n[Previous Conversation Summary]:\n{self.summary}"
        
        messages = [SystemMessage(content=full_system_text)]
        messages.extend(self.buffer)
        return messages

    def add_message(self, role: str, content: str):
        if role == "user":
            self.buffer.append(HumanMessage(content=content))
        elif role == "ai":
            self.buffer.append(AIMessage(content=content))
        self._prune_memory()

    def _prune_memory(self):
        max_msgs = self.keep_rounds * 2
        if len(self.buffer) > max_msgs:
            prune_count = 2 
            messages_to_summarize = self.buffer[:prune_count]
            self.buffer = self.buffer[prune_count:]
            self._update_summary(messages_to_summarize)

    def _update_summary(self, old_messages: list[BaseMessage]):
        conversation_text = ""
        for msg in old_messages:
            role = "User" if isinstance(msg, HumanMessage) else "AI"
            conversation_text += f"{role}: {msg.content}\n"

        prompt = (
            "You are a helpful assistant encapsulating conversation history.\n"
            "Current summary:\n{summary}\n\n"
            "New lines of conversation:\n{new_lines}\n\n"
            "Update the summary to include the new interaction, keeping it concise but informative."
        )
        
        prompt_template = PromptTemplate.from_template(prompt)
        chain = prompt_template | self.llm | StrOutputParser()
        
        try:
            new_summary = chain.invoke({
                "summary": self.summary or "No previous summary.",
                "new_lines": conversation_text
            })
            self.summary = new_summary.strip()
            print(f"🔄 Memory Summarized. New Summary Length: {len(self.summary)}")
        except Exception as e:
            print(f"⚠️ Summary update failed: {e}")

    def clear(self):
        self.summary = ""
        self.buffer = []

# 初始化全域記憶體
memory = ChatMemory(llm=summarizer_llm, keep_rounds=MEMORY_WINDOW_ROUNDS)


# ============================================================
# 📚 Qdrant 資料庫初始化
# ============================================================
client = QdrantClient(path=QDRANT_PATH)

print("⏳ Loading embedding models...")
client.set_model("sentence-transformers/all-MiniLM-L6-v2")
client.set_sparse_model("prithivida/Splade_PP_en_v1")
print(f"📂 Qdrant 資料庫路徑: {os.path.abspath(QDRANT_PATH)}")

# ============================================================
# 📥 檔案處理與 chunk 設定 (Markdown 增強版)
# ============================================================
def convert_to_markdown(file_path: str, use_marker_for_pdf: bool = False) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf" and use_marker_for_pdf:
        try:
            print(f"🚀 [Marker CLI] Starting conversion for: {os.path.basename(file_path)}")
            
            output_dir = os.path.join(os.path.dirname(file_path), "marker_output")
            os.makedirs(output_dir, exist_ok=True)
            
            # 使用 subprocess.run 簡化執行邏輯 (不再抓即時進度)
            cmd = [
                "marker_single",
                file_path,
                "--output_dir", output_dir
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)

            fname_stem = os.path.splitext(os.path.basename(file_path))[0]
            md_file_path = os.path.join(output_dir, fname_stem, f"{fname_stem}.md")

            if not os.path.exists(md_file_path):
                md_file_path = os.path.join(output_dir, f"{fname_stem}.md")

            if os.path.exists(md_file_path):
                with open(md_file_path, "r", encoding="utf-8") as f:
                    full_text = f.read()
                print(f"✅ [Marker CLI] Successfully converted {os.path.basename(file_path)}")
                return full_text
            else:
                raise FileNotFoundError(f"Markdown file not found in output directory.")

        except Exception as e:
            print(f"❌ [Marker CLI] failed: {e}. Falling back to MarkItDown.")
            # 失敗時繼續往下走，使用 fallback

    # 2. 預設使用 MarkItDown
    try:
        md = MarkItDown()
        result = md.convert(file_path)
        
        content = result.text_content
        if not content.strip() and ext == ".pdf":
            return "⚠️ [Warning] File content is empty after conversion (Scanned PDF?)."
            
        print(f"✅ [MarkItDown] Converted {os.path.basename(file_path)}")
        return content

    except Exception as e:
        return f"❌ Conversion Error: {str(e)}"

# 改用 Markdown 專用的 Splitter，能更好保留結構
text_splitter = MarkdownTextSplitter(
    chunk_size=500,
    chunk_overlap=100
)

def compute_hash(text: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, text))

def normalize_file(file):
    return file.name if hasattr(file, "name") else file

def load_file_to_docs(file_path, title="", doc_type="other", subtype=None, use_marker=False):
    base_name = os.path.basename(file_path)
    
    # 呼叫轉換函式
    markdown_text = convert_to_markdown(file_path, use_marker_for_pdf=use_marker)
    
    raw_doc = Document(
        page_content=markdown_text,
        metadata={"source": base_name}
    )
    
    docs = text_splitter.split_documents([raw_doc])

    default_subtype = os.path.splitext(base_name)[0]
    resolved_subtype = subtype.strip() if subtype and subtype.strip() else default_subtype

    processed = []
    for i, d in enumerate(docs):
        if not d.page_content.strip():
            continue

        chunk_hash = compute_hash(d.page_content)
        current_timestamp = time.time()
        readable_time = datetime.fromtimestamp(current_timestamp).strftime('%Y-%m-%d %H:%M:%S')

        new_metadata = {
            "title": title or base_name,
            "source": base_name,
            "type": doc_type or "other",
            "subtype": resolved_subtype,
            "chunk_id": i,
            "hash": chunk_hash,
            "timestamp": readable_time,
        }

        # 保留轉換工具可能留下的 metadata (如有)
        if "page" in d.metadata:
            new_metadata["page"] = d.metadata["page"]
        
        d.metadata = new_metadata
        processed.append(d)
        
    return processed

def add_docs_to_qdrant(docs):
    if not docs:
        return 0

    documents_content = [d.page_content for d in docs]
    metadatas = [d.metadata for d in docs]
    ids = [d.metadata["hash"] for d in docs]

    client.add(
        collection_name=COLLECTION_NAME,
        documents=documents_content,
        metadata=metadatas,
        ids=ids,
        batch_size=32
    )
    return len(docs)

def process_upload_files(title, doc_type, files, use_marker=False):
    if not files:
        return "⚠️ 請先上傳檔案。"

    total_add = 0
    logs = []
    
    for file in files:
        path = normalize_file(file)
        file_name = os.path.basename(path)

        try:
            docs = load_file_to_docs(path, title, doc_type, subtype=None, use_marker=use_marker)
            n_added = add_docs_to_qdrant(docs)
            
            print(f"📄 {file_name} → 轉換為 Markdown 並儲存 {n_added} chunks")
            total_add += n_added
        except Exception as e:
            logs.append(f"❌ {path} 發生錯誤：{e}")

    logs.append(f"\n**總計成功處理 {total_add} 個 chunks**")
    return "\n".join(logs)

# ============================================================
# 🧩 Metadata Filter
# ============================================================
meta_filter_prompt = PromptTemplate.from_template(
"""
You are a classifier deciding filters.
Output **only one JSON object**.

Fields:
- "type": "people" / "paper" / "other"
- "subtype": string or ""

Question:
{question}

JSON:
"""
)

meta_filter_chain = meta_filter_prompt | agent_general | StrOutputParser()

def decide_metadata_filter(question: str):
    raw = ""
    try:
        raw = meta_filter_chain.invoke({"question": question})
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw_json = raw[start:end + 1]
        else:
            raw_json = raw
        data = json.loads(raw_json)
    except Exception as e:
        print(f"[MetaFilter] 解析失敗: {e}")
        return None, {"type": "", "subtype": ""}

    type_ = (data.get("type") or "").strip().lower()
    subtype = (data.get("subtype") or "").strip()

    must_conditions = []
    if type_ and type_ not in ["any", ""]:
        if type_ not in ["people", "paper", "other"]:
            type_ = "other"
        must_conditions.append(models.FieldCondition(key="type", match=models.MatchValue(value=type_)))

    if not must_conditions:
        return None, {"type": type_, "subtype": subtype}

    qdrant_filter = models.Filter(must=must_conditions)
    return qdrant_filter, {"type": type_, "subtype": subtype}


def _run_qdrant_query(question: str, qdrant_filter):
    if not client.collection_exists(COLLECTION_NAME):
        return []
    
    all_points = []
    seen_hashes = set()

    search_result = client.query(
        collection_name=COLLECTION_NAME,
        query_text=question,
        limit=3,
        query_filter=qdrant_filter
    )

    for point in search_result:
        doc_hash = point.metadata.get("hash")
        if doc_hash not in seen_hashes:
            all_points.append(point)
            seen_hashes.add(doc_hash)

    all_points.sort(key=lambda x: x.score, reverse=True)
    return all_points[:8]


def qdrant_hybrid_search_with_meta(question: str):
    qdrant_filter, debug_meta = decide_metadata_filter(question)
    subtype_hint = debug_meta.get("subtype", "")

    results = _run_qdrant_query(question, qdrant_filter) if qdrant_filter else _run_qdrant_query(question, None)

    if qdrant_filter and not results:
        results = _run_qdrant_query(question, None)

    context_list = []
    for idx, point in enumerate(results, start=1):
        content = point.metadata.get("document", "")
        source = point.metadata.get("source", "unknown")
        if not content and hasattr(point, 'document'): 
             content = point.document
        
        block = (
            f"### Document {idx} (Source: {source})\n"
            f"\n"
            f"{content}"
        )
        context_list.append(block)

    context_text = "\n\n".join(context_list)
    return {"context": context_text, "subtype": subtype_hint}


# ============================================================
# 💬 核心回應生成邏輯 (整合 Memory)
# ============================================================

def generate_response(message: str, current_mode: Mode) -> str:
    final_response = ""

    try:
        # 1. 處理 RAG Mode
        if current_mode == Mode.RAG:
            print("🔍 Mode: RAG")
            rag_data = qdrant_hybrid_search_with_meta(message)
            context = rag_data["context"]
            
            if not context:
                system_prompt = "No relevant documents found. Answer based on your knowledge, but mention you couldn't find specific docs."
            else:
                system_prompt = (
                    "Below is some context information from the knowledge base (in Markdown format).\n"
                    "Instructions:\n"
                    "1. Answer the question using ONLY the context if possible.\n"
                    "2. If the answer is not in the context, say 'I don't know' or answer generally.\n\n"
                    f"Context:\n{context}"
                )
            
            messages = memory.get_messages(system_instruction=system_prompt)
            messages.append(HumanMessage(content=message))
            
            res = agent_general.invoke(messages)
            final_response = res.content

        # 2. 處理 Tools Mode
        elif current_mode == Mode.TOOLS:
            print("🛠️ Mode: TOOLS")
            tool_input_msg = message
            if memory.summary:
                tool_input_msg = f"Context: {memory.summary}\nUser Request: {message}"

            res = agent_tools.invoke([{"role": "user", "content": tool_input_msg}])
            
            calls = getattr(res, "tool_calls", [])
            if calls:
                call = calls[0]
                name = call["name"]
                args = call.get("args", call.get("arguments", {}))
                
                tool = next((t for t in TOOLS if t.name == name), None)
                if not tool:
                    final_response = f"⚠️ Tool not found: {name}"
                else:
                    tool_result = tool.invoke(args)
                    followup = f"Tool '{name}' output: {tool_result}. Now answer the user: {message}"
                    
                    msgs = memory.get_messages(system_instruction="You are a helpful assistant with tool access.")
                    msgs.append(HumanMessage(content=followup))
                    
                    final = agent_general.invoke(msgs)
                    final_response = final.content
            else:
                final_response = getattr(res, "content", "") or "(Tool Agent 無回應)"

        # 3. 處理 Normal Mode
        else: # Mode.NORMAL
            print("💬 Mode: NORMAL")
            system_prompt = "You are a helpful AI assistant."
            messages = memory.get_messages(system_instruction=system_prompt)
            messages.append(HumanMessage(content=message))
            
            res = agent_general.invoke(messages)
            final_response = res.content

        final_response = final_response.strip()
        memory.add_message(role="user", content=message)
        memory.add_message(role="ai", content=final_response)

        return final_response

    except Exception as e:
        error_msg = f"❌ Error: {e}"
        print(error_msg)
        return error_msg