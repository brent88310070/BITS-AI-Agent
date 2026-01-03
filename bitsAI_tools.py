import psutil
import GPUtil
import pynvml
from datetime import datetime
from langchain.tools import tool
from langchain_ollama import ChatOllama

# ============================================================
# 🧩 工具定義
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
    time = datetime.now().strftime("🕒 %Y-%m-%d (%A) %H:%M:%S")
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
                'gpu_mem': 0, # 預設為 0
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
                    'gpu_mem': p.usedGpuMemory / 1e9 # 轉為 GB
                })
        pynvml.nvmlShutdown()
    except Exception:
        pass # 若無 GPU 則跳過

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

# ============================================================
# ⚙️ 工具列表與 Agent 建立
# ============================================================

# 將新增的工具加入清單
TOOLS = [system_info, get_time, gpu_info, disk_info, resource_monitor]

def create_tool_agent(llm_name: str, tools: list):
    """建立並回傳一個已綁定工具的 ChatOllama Agent"""
    # temperature 設為 0.1 以提高工具選擇的穩定性
    agent_tools = ChatOllama(model=llm_name, temperature=0.1).bind_tools(tools)
    return agent_tools

# 測試 Agent
# agent = create_tool_agent("llama3.1", TOOLS)