import os
import sys
import json
import psutil
import GPUtil
import pynvml
from datetime import datetime
from langchain_core.tools import tool, StructuredTool
import asyncio
from contextlib import AsyncExitStack

# === MCP Imports ===
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

STORAGE_DIR = os.path.abspath("data_storage").replace("\\", "/")
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

# ============================================================
# 🧩 本地工具定義 (保持不變)
# ============================================================

@tool("system_info")
def system_info() -> str:
    """CPU and RAM usage"""
    mem = psutil.virtual_memory()
    return (f"🖥️ CPU: {psutil.cpu_count()} cores, Usage: {psutil.cpu_percent()}%\n"
            f"💾 RAM: {mem.used / 1e9:.2f}/{mem.total / 1e9:.2f} GB")

@tool("get_time")
def get_time() -> str:
    """Current time"""
    time = datetime.now().strftime("🕑 %Y-%m-%d (%A) %H:%M:%S")
    print(time)
    return time

@tool("gpu_info")
def gpu_info() -> str:
    """Get NVIDIA GPU status (Load, Memory, Temperature)"""
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return "❌ No NVIDIA GPU detected."
        
        info = []
        for gpu in gpus:
            used_gb = gpu.memoryUsed / 1024
            total_gb = gpu.memoryTotal / 1024
            gpu_status = (f"🎮 GPU: {gpu.name} | Load: {gpu.load*100:.1f}% | "
                          f"Temp: {gpu.temperature}°C | "
                          f"Mem: {used_gb:.2f}/{total_gb:.2f} GB")
            info.append(gpu_status)
        return "\n".join(info)
    except Exception as e:
        return f"⚠️ Could not retrieve GPU info: {str(e)}"

@tool("disk_info")
def disk_info() -> str:
    """Get Disk/Storage usage for the root directory"""
    usage = psutil.disk_usage('/')
    return (f"💽 Disk: {usage.used / 1e9:.2f}/{usage.total / 1e9:.2f} GB "
            f"({usage.percent}% used)")

@tool("resource_monitor")
def resource_monitor() -> str:
    """Identify top CPU, RAM, and GPU consuming processes and their scripts."""
    processes = []
    
    # 1. 取得 CPU 與 RAM 的行程資訊
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'cmdline']):
        try:
            info = proc.info
            cmdline = " ".join(info['cmdline']) if info['cmdline'] else ""
            is_script = any(ext in cmdline.lower() for ext in ['.py', '.sh', '.r', '.pl', '.ipynb', 'python', 'node'])
            
            processes.append({
                'pid': info['pid'],
                'user': info['username'],
                'name': info['name'],
                'cpu': info['cpu_percent'],
                'mem': info['memory_info'].rss / 1e9,
                'script': cmdline if is_script else None,
                'gpu_mem': 0,
                'gpu_id': None
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # 2. 取得 GPU 行程資訊 (使用 NVML)
    gpu_processes = []
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            for p in procs:
                gpu_processes.append({
                    'pid': p.pid,
                    'gpu_id': i,
                    'gpu_mem': p.usedGpuMemory / 1e9 
                })
        pynvml.nvmlShutdown()
    except Exception:
        pass 

    # 3. 將 GPU 數據合併回主列表
    for gp in gpu_processes:
        for p in processes:
            if p['pid'] == gp['pid']:
                p['gpu_mem'] = gp['gpu_mem']
                p['gpu_id'] = gp['gpu_id']

    # 4. 排序並產出結果
    top_cpu = sorted(processes, key=lambda x: x['cpu'], reverse=True)[:3]
    top_mem = sorted(processes, key=lambda x: x['mem'], reverse=True)[:3]
    top_gpu = sorted([p for p in processes if p['gpu_mem'] > 0], key=lambda x: x['gpu_mem'], reverse=True)[:3]

    result = ["📊 **Resource Consumption Leaderboard**"]
    
    result.append("\n🔥 Top 3 CPU Usage:")
    for p in top_cpu:
        s = f" (📜 {p['script'][:40]}...)" if p['script'] else ""
        result.append(f"- User: {p['user']} | CPU: {p['cpu']}% | Proc: {p['name']}{s}")

    result.append("\n🧠 Top 3 RAM Usage:")
    for p in top_mem:
        s = f" (📜 {p['script'][:40]}...)" if p['script'] else ""
        result.append(f"- User: {p['user']} | Mem: {p['mem']:.2f} GB | Proc: {p['name']}{s}")

    if top_gpu:
        result.append("\n🎮 Top 3 GPU Usage:")
        for p in top_gpu:
            s = f" (📜 {p['script'][:40]}...)" if p['script'] else ""
            result.append(f"- User: {p['user']} | GPU[{p['gpu_id']}] VRAM: {p['gpu_mem']:.2f} GB | Proc: {p['name']}{s}")
    else:
        result.append("\n🎮 GPU Usage: No active GPU compute processes found.")

    return "\n".join(result)

@tool("list_storage_files")
def list_storage_files() -> str:
    """
    List filenames in the data_storage directory.
    IMPORTANT RESTRICTION:
    - Use this tool ONLY when the user asks "what files are there?" or "show the file list".
    - If the user specifies a filename (e.g., "read test.csv", "get column from data.csv"), DO NOT USE THIS TOOL.
    - Instead, use the SQL tool directly to query the file.
    """
    if not os.path.exists(STORAGE_DIR): return "📂 Directory empty."
    files = os.listdir(STORAGE_DIR)
    info = []
    for f in files:
        path = os.path.join(STORAGE_DIR, f)
        size = os.path.getsize(path) / (1024*1024)
        info.append(f"- {f} ({size:.4f} MB)")
    return f"📂 **Files in {STORAGE_DIR}:**\n" + "\n".join(info)

# ============================================================
# 🌉 Tool Loader
# ============================================================
_mcp_exit_stack = AsyncExitStack()

async def connect_to_mcp_server(command: str, args: list[str], env: dict = None):
    """連線到指定的 MCP Server 並回傳 tools"""
    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env
    )
    
    try:
        read_stream, write_stream = await _mcp_exit_stack.enter_async_context(stdio_client(server_params))
        session = await _mcp_exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        
        mcp_list_tools = await session.list_tools()
        langchain_tools = []

        for mcp_tool in mcp_list_tools.tools:
            # === 💡 FIX 1: 動態注入路徑指引 ===
            # 我們修改工具描述，強制 LLM 知道檔案都在 data_storage 資料夾下
            # 並要求它在 SQL 查詢時使用絕對路徑或正確的相對路徑
            enhanced_description = mcp_tool.description
            if "sql" in mcp_tool.name.lower() or "query" in mcp_tool.name.lower():
                enhanced_description += (
                    f"\n\n IMPORTANT PATH INSTRUCTION \n"
                    f"All CSV/Parquet files are located in: '{STORAGE_DIR}'\n"
                    f"When writing SQL, you MUST prepend the path to the filename.\n"
                    f"Example: SELECT * FROM read_csv('{STORAGE_DIR}/your_file.csv');"
                )

            # 使用閉包捕獲當前 tool 的資訊
            def make_wrapper(tool_name, tool_session):
                async def _tool_wrapper(**kwargs):
                    try:
                        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
                            actual_args = kwargs["kwargs"]
                        else:
                            actual_args = kwargs
                        
                        # === [DEBUG] 1. 印出送出的指令 ===
                        print(f"\n📝 [MCP DEBUG] Sending to {tool_name}:")
                        if "query" in actual_args:
                            print(f"   👉 SQL: {actual_args['query']}")
                        else:
                            print(f"   👉 Args: {json.dumps(actual_args, ensure_ascii=False)}")
                        print("-" * 50)
                        
                        # 執行工具
                        result = await tool_session.call_tool(tool_name, arguments=actual_args)
                        
                        # === [DEBUG] 2. 印出收到的結果 (💡 新增這裡) ===
                        print(f"📥 [MCP DEBUG] Received from {tool_name}:")
                        if result.content:
                            for content in result.content:
                                if content.type == "text":
                                    # 避免結果太長洗版，超過 500 字元就截斷顯示
                                    display_text = content.text
                                    if len(display_text) > 500:
                                        display_text = display_text[:500] + "\n... [truncated] ..."
                                    print(f"   📄 Data:\n{display_text}")
                                else:
                                    print(f"   📦 Object ({content.type}): {content}")
                        else:
                            print("   ⚠️ No content returned (Empty).")
                        print("=" * 50 + "\n")
                        # ==============================================
                        
                        output_text = []
                        if result.content:
                            for content in result.content:
                                if content.type == "text":
                                    output_text.append(content.text)
                        
                        # === 💡 FIX 2: 錯誤攔截與提示 (針對問題2的輔助) ===
                        final_output = "\n".join(output_text) if output_text else "No output."
                        
                        # 如果 DuckDB 回傳找不到檔案的錯誤，我們在工具輸出中偷偷加一句提示
                        # 這會刺激 LLM 自動修正，而不是只有報錯
                        if "No such file or directory" in final_output:
                            final_output += f"\n\n⚠️ SYSTEM HINT: The file was not found. Did you forget to add the path '{STORAGE_DIR}/'?"

                        if "validation error" in final_output.lower() or "required property" in final_output.lower():
                            final_output += (
                                f"\n\n⚠️ SYSTEM HINT: Argument Error. "
                                f"You MUST use the 'query' argument with a valid SQL string.\n"
                                f"Do NOT pass 'file' or 'head' directly.\n"
                                f"Correct Example: {{'query': \"SELECT * FROM read_csv('{STORAGE_DIR}/filename.csv') LIMIT 5\"}}"
                            )
                            
                        return final_output

                    except Exception as tool_err:
                        return f"❌ Tool execution failed: {tool_err}"
                return _tool_wrapper

            lc_tool = StructuredTool.from_function(
                func=None,
                coroutine=make_wrapper(mcp_tool.name, session),
                name=mcp_tool.name,
                description=enhanced_description, # 使用修改後的描述
            )
            langchain_tools.append(lc_tool)
            print(f"🔗 Loaded MCP Tool: {mcp_tool.name} (with path injection)")
            
        return langchain_tools

    except Exception as e:
        print(f"❌ Failed to connect to MCP server ({command}): {e}")
        import traceback
        traceback.print_exc()
        return []

async def get_all_tools_async():
    """非同步:載入本地工具與 DuckDB MCP 工具"""
    
    # 1. 基本本地工具
    tools = [system_info, get_time, gpu_info, disk_info, resource_monitor, list_storage_files]
    
    # 2. MCP Server: DuckDB (MotherDuck 官方版本)
    print("⏳ Connecting to MCP: DuckDB (MotherDuck official server)...")
    print(f"📂 Working Directory: {STORAGE_DIR}")
    
    # 建立一個本地 DuckDB 資料庫路徑
    mcp_env = os.environ.copy()
    mcp_env["CSV_DIR"] = STORAGE_DIR  # 設定 CSV 目錄環境變數
    
    # MotherDuck 的 DuckDB MCP Server
    # 功能:
    # - 執行 SQL 查詢分析 CSV/Parquet/JSON
    # - 使用 DuckDB 的 read_csv() 函數直接讀取檔案
    # - 支援複雜的 SQL 分析 (JOIN, GROUP BY, 聚合函數等)
    # - 可查詢本地檔案或 S3 遠端資料
    mcp_tools = await connect_to_mcp_server(
        command="uvx",
        args=[
            "mcp-server-motherduck",  # MotherDuck 官方 DuckDB MCP Server
            "--db-path", ":memory:",  # 使用記憶體模式，不建立實體檔案
        ],
        env=mcp_env
    )
    
    tools.extend(mcp_tools)
    
    print(f"✅ Total tools loaded: {len(tools)}")
    print(f"💡 Tip: You can query CSV files using SQL like:")
    print(f"   SELECT * FROM read_csv('{STORAGE_DIR}/your_file.csv') LIMIT 10;")
    
    return tools