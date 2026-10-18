# 🤖 ReadFlow AI 自动化安装提示词 (AI Installation Prompt)

> **使用说明**：直接复制下方方框中的完整提示词，粘贴给你本地的 AI 编程助手（如 **Cursor、Claude Code、Windsurf、Cline、GitHub Copilot CLI、或任意具备终端执行权限的本地 AI Agent**），AI 将全自动检测你的环境并完成无人值守安装。

---

```markdown
你是一个全自动化的 DevOps 与系统运维专家助手。你的任务是在当前主机上全自动安装、配置并守护运行「ReadFlow 跨平台图书自动化抓取与推送引擎」。

项目仓库：https://github.com/P-bit-display/readflow.git

请严格按照以下标准化步骤执行，并主动在每一步进行检查验证：

### 第一步：环境探测与代码获取
1. 检查当前操作系统（macOS / Linux / Windows / 群晖）、Python 版本（需 3.10+）以及是否有 Docker、launchctl 或 systemctl。
2. 检查当前目录是否已是 ReadFlow 仓库：
   - 若不是，克隆代码库并进入：`git clone https://github.com/P-bit-display/readflow.git && cd readflow`
   - 若已在仓库中，拉取最新代码：`git pull`

### 第二步：依赖与虚拟环境构建
1. 创建专属 Python 虚拟环境：`python3 -m venv venv`
2. 激活虚拟环境并安装核心依赖：
   - macOS/Linux: `venv/bin/pip install -U pip && venv/bin/pip install -r requirements.txt`
   - Windows: `venv\Scripts\pip install -U pip && venv\Scripts\pip install -r requirements.txt`

### 第三步：交互式配置（或使用默认模板）
1. 检查根目录下是否存在 `.env` 文件。若不存在，基于 `.env.example` 创建 `.env`。
2. 以极简、友好的方式询问用户以下 3 个最核心参数（如果用户已提供或已配置则直接跳过）：
   - `DOUBAN_USER_ID`: 豆瓣用户数字 ID（如 151885595）
   - `TARGET_EMAIL`: 电纸书接收邮箱（如 汉王/Kindle/常用邮箱）
   - `SMTP_SERVER` / `SMTP_USER` / `SMTP_PASSWORD`: 用于发信的 SMTP 服务器与授权码（如 网易 163、QQ 邮箱或 Gmail）
3. 其他高级项（Goodreads、群晖 Calibre 路径、Z-Library 密钥等）保留默认或提示用户稍后可在 WebUI 界面中可视化编辑。将配置原子化写入 `.env`。

### 第四步：根据系统环境配置自启动常驻服务
优先采用原生守护进程方式：
1. **macOS 平台**：
   - 自动生成 LaunchAgent 配置文件 `~/Library/LaunchAgents/com.user.readflow.plist`，工作目录设为项目绝对路径，使用 `venv/bin/python -u main.py` 执行。
   - 创建日志目录 `mkdir -p ~/.readflow/logs`。
   - 执行 `launchctl load -w ~/Library/LaunchAgents/com.user.readflow.plist` 立即加载自启服务。
2. **Linux 平台（Ubuntu / Debian / CentOS）**：
   - 生成 systemd 单元文件 `/etc/systemd/system/readflow.service`。
   - 执行 `sudo systemctl daemon-reload && sudo systemctl enable --now readflow`。
3. **Docker 容器环境**（若宿主机支持 Docker 且用户偏好容器）：
   - 直接执行 `docker compose up -d`。

### 第五步：连通性验证与交付报告
1. 执行 `curl -s http://localhost:8765/api/status` 验证服务是否成功监听 8765 端口且状态正常。
2. 检查最近 10 行日志确认没有报错。
3. 向用户汇报交付成果：
   - 服务状态（PID / 运行方式 / 端口 8765）
   - Web 控制面板入口链接：`http://localhost:8765`
   - 提示用户：稍后在豆瓣点击「想读」，系统就会自动后台捕获、入库并投递到邮箱！
```

---

### 适用场景
* **Cursor / Windsurf**：在 Composer / Chat 窗口中输入 `@terminal` 并粘贴上述提示词，授权执行即可。
* **Claude Code / OpenDevin / Aider**：直接将提示词粘贴进命令行交互会话，AI 会调用 Bash 工具自动跑完所有流程。
* **ChatGPT / 本地大模型 + 自动化脚本**：由大模型根据你的当前路径微调指令后一键执行。
