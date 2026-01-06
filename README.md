<p align="center">
  <img src="LOGO.jpg" width="80%" />
</p>

---------------------------------------
# BITS-AI: A RAG-Integrated AI Agent Platform for Labs

BITS-AI is a private laboratory AI agent integrating LLMs with hybrid RAG to optimize technical search and protocol understanding. It serves as an intelligent research assistant featuring multi-format file support, tool orchestration.

## User Interface
 <img src="UI.jpg" style="align:center" />

## How to start?
To access the BITS-AI agent Interface, run the main execution file:
```Python
python -u bitsAI_app.py
```
Three Modes of Operation:
* **Normal**: Standard chat mode with no additional features enabled.
* **Tools**: Enables the `開啟工具模式` toggle to call specific system utilities (see Available Tools below for details).
* **RAG**: Enables the `開啟 RAG 模式` toggle to perform Retrieval-Augmented Generation based on your stored data.

Note on File Upload:
* **Default**: Uses **MarkItDown** for fast conversion.
* **Enhanced Accuracy**: Toggle the **Marker** button for more precise results (Note: This process is slower).

## Simply manage the Vector database
You can delete the chunks or modify the metadata:
```Python
python -u bitsAI_qdrant_db_admin.py
```

## Available Tools
You can turn on the `開啟工具模式` button to operate the tools:
<details> <summary>System Health Related question</summary>
  
  * "What is the current status of the system?"
  * "How much RAM is currently being used?"
  * "Is the CPU under heavy load right now?"
  * "How much disk space is left on the root drive?"
  * "Give me a quick summary of the system hardware usage."
</details>

<details> 
<summary>System Health Related question</summary>

  * "What is the current status of the system?"
  * "How much RAM is currently being used?"
  * "Is the CPU under heavy load right now?"
  * "How much disk space is left on the root drive?"
  * "Give me a quick summary of the system hardware usage."
</details>

<details>
<summary>GPU Status Related questions</summary>

  * "Is there an NVIDIA GPU available?"
  * "What is the current GPU temperature? Is it overheating?"
  * "Is the GPU being utilized right now, or is it idle?"
  * "Check the load on all available graphics cards."
</details>

<details> <summary>Resource Audit Related question</summary>
  
  * "Which processes are consuming the most CPU?"
  * "Find the top 3 memory-hogging applications."
  * "Who is running the most resource-intensive task right now?"
  * "List the top 3 scripts that are slowing down the system."
</details>

<details> <summary>Time Context Related question</summary>
  
  * "What time is it now?"
  * "What day of the week is it?"
  * "Give me the current timestamp for the log."
</details>
