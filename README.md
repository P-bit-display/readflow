# 📖 ReadFlow

> **Universal Zero-UI Book Acquisition & Delivery Engine**  
> *在豆瓣或 Goodreads 随手点「想读」，电子书自动多源检索、入库 Calibre 并秒级送达你的电纸书/邮箱！*

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

---

## 💡 为什么做这个项目？

传统的找书流程极其繁琐且充满摩擦力：
```text
在豆瓣/Goodreads看到好书 -> 复制书名 -> 打开搜索网站找资源 -> 鉴别垃圾弹窗 -> 下载 EPUB -> 连数据线/找传书网页 -> 传输到电纸书 -> 刷新书架
```
**整个过程跨越多个设备、经历 7 个步骤，大量好书就在这个过程中被遗忘了。**

### 第一性原理（First Principles）设计：
- **最小化摩擦力**：人在做决策的一瞬间动作最自然。你只需在手机豆瓣 App 点「想读」或在 Goodreads 点「Want to Read」，无感触发。
- **静默软件哲学 (Quiet Software)**：不需要繁琐的状态弹窗与机器人汇报，**收到带有电子书附件的邮件那一刻，你就知道它已经准备好了**。
- **双重安全网**：
  - **Calibre 负责数字资产终身归档**（防止网络失效、平台封禁）；
  - **邮件与网盘负责最后一公里直达**（电纸书点开邮件直接进原生书架）。

---

## 🏗️ 架构流向图

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. 意图捕获层 (Intent Providers)                           │
│    ├── 🇨🇳 豆瓣 (Douban)       : 个人「想读」书单 (RSS / HTML)│
│    └── 🌐 Goodreads           : 个人「Want to Read」 (RSS)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ (捕获到想读书籍)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 实体消歧与规范化 (Entity Resolution)                     │
│    ├── 提取 ISBN / 豆瓣 / Goodreads 唯一标识 (防同名书漂移)  │
│    └── 标准化书名、作者与语言偏好过滤                       │
└──────────────────────────────┬──────────────────────────────┘
                               │ (携带标准元数据检索)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 聚合书源瀑布流 (Fulfillment Waterfall Chain)             │
│    ├── Priority 0: 本地 Calibre 藏书库查重 (0毫秒零网络开销) │
│    ├── Priority 1: Z-Library (API / 账号检索)               │
│    ├── Priority 2: Anna's Archive (安娜档案: 免登元搜索兜底) │
│    └── Priority 3: Library Genesis (Libgen: 英文/学术兜底)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (成功命中 EPUB)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 资产入库与终端交付 (Ingestion & Quiet Delivery)          │
│    ├── 🏛️ 资产归档: 自动导入 Calibre / Calibre-Web 核心库     │
│    ├── 📬 邮件直达: RFC 2047 中文编码附件 -> 汉王/Kindle    │
│    └── 📦 防爆保护: 文件 > 25MB 自动截断降级为自建书库直取   │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ 核心特性

- 🎯 **双意图捕获源**：原生支持 **豆瓣「想读」** 与 **Goodreads「Want to Read」**，中外图书全覆盖。
- 🔍 **多源瀑布流检索**：
  - 本地 Calibre 库查重 ➔ Z-Library ➔ Anna's Archive ➔ Libgen，彻底消除单一书源失效的风险。
- 📬 **国内邮箱 100% 无乱码**：
  - 内置 **RFC 2047 MIME Base64 编码**，彻底解决网易 163、QQ 邮箱等将中文附件识别为 `noname` 的历史顽疾。
- 📱 **电纸书原生直接上架**：
  - 汉王（N10 / N10 Pro 等）、Kindle 或文石设备只要打开邮件附件，图书自动进入系统原生书架。
- 📦 **大文件优雅降级**：
  - 附件超过 25MB 时自动截断，避免邮件服务器拒收，转为存入自建书库并发送纯文本提示。
- 🐳 **Docker 开箱即用**：支持 Docker Compose 一键拉起，静默后台常驻。

---

## 🚀 快速开始

### 方式一：Docker Compose（推荐）

1. **克隆本仓库**：
   ```bash
   git clone https://github.com/P-bit-display/douban2reader.git
   cd douban2reader
   ```

2. **配置环境变量**：
   ```bash
   cp .env.example .env
   vim .env
   ```
   *填入你的豆瓣 ID、Goodreads ID、发信邮箱授权码与收件邮箱。*

3. **一键启动**：
   ```bash
   docker compose up -d
   ```

---

### 方式二：本地 Python 运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 复制并填写配置
cp .env.example .env

# 3. 运行守护程序
python main.py
```

---

## 📄 免责声明 (Disclaimer)

本项目仅供个人学术研究与开源技术交流使用，所有图书检索逻辑均基于第三方开放接口与用户个人合法账户。请支持正版图书出版物。

## 📜 许可证 (License)

本项目基于 [MIT License](LICENSE) 开源。欢迎提交 PR 和 Issue！
