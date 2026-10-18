# 📚 Douban2Reader

> **在豆瓣随手点「想读」，电子书自动入库 Calibre 并秒级送达你的电纸书 / 邮箱！**  
> *Zero-UI: 将“产生阅读意图”到“沉浸阅读正文”之间的摩擦力降至绝对的零。*

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

---

## 💡 为什么做这个项目？

传统的找书流程极其繁琐且充满摩擦力：
```text
在豆瓣看到好书 -> 复制书名 -> 打开搜索网站找资源 -> 鉴别垃圾弹窗 -> 下载 EPUB -> 连数据线/找传书网页 -> 传输到电纸书 -> 刷新书架
```
**整个过程跨越多个设备、经历 7 个步骤，大量好书就在这个过程中被遗忘了。**

从第一性原理出发，人在做决策的一瞬间动作最自然：  
**你只需要在手机豆瓣 App 里点一下「想读」，剩下的所有事情全部由后端自动化流水线接管！**

---

## ✨ 核心特性

- 🎯 **意图无感捕获**：自动低频侦听你的豆瓣公开想读书单，不侵入、免登录、防封频控。
- ⚡ **本地藏书毫秒级查重**：若 Calibre 库中已有该书，直接调取原档，0 秒等待。
- 🔍 **云端自动抓取**：若私有库中暂无，自动从 Z-Library 检索并加权筛选最新、最优质的中文 EPUB 版本。
- 📬 **国内邮箱无乱码**：内置 **RFC 2047 MIME Base64 编码**，彻底解决网易 163、QQ 邮箱等将中文附件识别为 `noname` 的历史顽疾。
- 📱 **电纸书原生直接上架**：汉王（N10 / N10 Pro 等）、Kindle 或文石设备只要打开邮件附件，图书自动进入系统原生书架。
- 📦 **大文件优雅降级**：附件超过 25MB 时自动截断，避免邮件服务器拒收，转为存入自建书库。
- 🐳 **Docker 开箱即用**：支持 Docker Compose 一键拉起，极速运行。

---

## 🏗️ 架构流向图

```text
[你在豆瓣 App 点击「想读」]
          │
          ▼
   Douban2Reader (后台定时轮询守护)
          │
          ├─► 1. 查重 Calibre 私有书库 (metadata.db)
          │       ├─ 已存在 ──┐
          │       └─ 未收录 ──┴─► 2. 调用 Z-Library 智能加权抓取
          │                              │
          ▼                              ▼
   3. 自动归档入库 Calibre-Web ◄─────────┘
          │
          ▼
   4. 组装 RFC 2047 规范编码的邮件附件
          │
          ▼
[邮件直达：汉王 / Kindle / 163 / QQ 邮箱]
          │
          ▼
[电子纸点开邮件附件 -> 自动加入原生书架开读！]
```

---

## 🚀 快速开始

### 方式一：Docker Compose（推荐）

1. **克隆本仓库**：
   ```bash
   git clone https://github.com/your-username/douban2reader.git
   cd douban2reader
   ```

2. **配置环境变量**：
   ```bash
   cp .env.example .env
   vim .env
   ```
   只需填入 4 项基本信息：
   - `DOUBAN_USER_ID`: 你的豆瓣个人 ID（在豆瓣个人主页网址中查看：`douban.com/people/{ID}/`）
   - `SMTP_USER` & `SMTP_PASSWORD`: 你的发件邮箱与授权码（推荐 Gmail 应用密码 或 163/QQ 授权码）
   - `TARGET_EMAIL`: 你的收件邮箱（如汉王绑定的邮箱、Kindle 邮箱或个人常用邮箱）
   - `ZLIB_EMAIL` & `ZLIB_PASSWORD`: 你的 Z-Library 账号密码

3. **一键启动**：
   ```bash
   docker compose up -d
   ```

---

### 方式二：本地 Python 运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 填写 .env 内容...

# 3. 运行守护程序
python src/main.py
```

---

## 🛠️ 进阶配置与联动

### 1. 联动群晖 NAS / 本地 Calibre 书库
如果你本地已有 Calibre 库，可在 `docker-compose.yml` 中挂载目录：
```yaml
volumes:
  - ./data:/app/data
  - /volume1/books/calibre:/books:ro    # 映射你的 Calibre 书库，启用毫秒级查重
  - /volume1/books/inbox:/inbox         # 映射自动入库目录
```

### 2. 汉王 N10 / N10 Pro 最佳实践
- 在汉王上登录你的收信邮箱（如 163 邮箱）。
- 每次收到新邮件，点击附件中的 `.epub`，汉王系统会自动解析并加入「书架」，无需任何手动拷贝！

---

## 📄 免责声明 (Disclaimer)

本项目仅供个人学术研究与开源技术交流使用，所有图书检索逻辑均基于第三方开放接口与用户个人合法账户。请支持正版图书出版物。

## 📜 许可证 (License)

本项目基于 [MIT License](LICENSE) 开源。欢迎提交 PR 和 Issue！
