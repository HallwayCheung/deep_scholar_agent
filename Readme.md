# 🏛️ DeepScholar

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18.0+-61dafb.svg?style=for-the-badge&logo=react" alt="React">
  <img src="https://img.shields.io/badge/LangGraph-Production--Ready-orange.svg?style=for-the-badge" alt="LangGraph">
</p>

DeepScholar 是一个基于大语言模型（LLM）的多智能体学术研究工作站。系统利用 **LangGraph** 进行复杂流程编排，旨在实现学术文献调研、筛选、精读与综述合成的端到端自动化。通过引入 **人机协同 (Human-in-the-Loop)** 机制与持久化架构，系统能够在保证研究深度的同时，提供极高的可控性与透明度。

---

## 🚀 核心特性

### 1. 结构化智能体协同
系统将复杂的科研任务拆解为多个专业化节点，通过状态机进行循环调度：
*   **Planner**: 自动拆解课题维度。
*   **Screener**: 全网实时文献检索。
*   **Reader**: 深度语义解析与防幻觉 RAG 研读。
*   **DataMiner**: 跨文献定量指标挖掘。
*   **Writer & Reviewer**: 迭代式学术写作与引用校准。

### 2. 人机协同机制 (HITL)
DeepScholar 拒绝“黑盒生成”，在关键环节提供决策干预：
*   **路径校准**: 启动前审核 Agent 的研究计划。
*   **文献优选**: 手动干预筛选列表，确保样本文献的高相关性。

### 3. 可观测性与持久化
*   **实时思维流**: 基于 SSE 协议，前端实时观测智能体的推理逻辑与决策权重。
*   **任务快照**: 基于 SQLite 的 Checkpointer 机制，支持任务随时中断与恢复。

### 4. 学术辅助工具
*   **BYO-PDF**: 支持用户上传本地文献并无缝接入分析流程。
*   **Academic Copilot**: 针对生成的综述提供上下文相关的即时答疑。

---

## 🛠️ 技术堆栈

| 领域 | 技术方案 |
| :--- | :--- |
| **后端** | FastAPI + LangGraph + LangChain |
| **持久化** | SQLite3 + langgraph-checkpoint-sqlite |
| **前端** | React 18 + Vite + TailwindCSS + Framer Motion |
| **解析引擎** | PyMuPDF (fitz) + React Markdown |
| **协议** | Server-Sent Events (SSE) 异步流传输 |

---

## 📦 快速启动

### 1. 环境准备
```bash
conda create -n deep_scholar python=3.10
conda activate deep_scholar
pip install -r requirements.txt
```

### 2. 配置环境变量
在项目根目录创建 `.env` 文件，配置您的 LLM API Key (支持 OpenRouter, DashScope 等兼容 OpenAI 格式的服务)。

### 3. 启动项目
**后端 API:**
```bash
python api.py
```

**前端界面:**
```bash
cd frontend
npm install
npm run dev
```

---

## 🎨 项目展示

### 📊 智能协作看板
![智能协作看板](./assets/screenshots/image-20260421154840641.png)
实时可视化多智能体推理图谱，系统自动化完成文献调研与综述合成全流程。

---

### 📝 研究路径确认
![研究路径确认](./assets/screenshots/image-20260421154250793.png)
在正式研究开始前，对 Agent 拆解的课题维度进行人工审核与校准。

---

### 🔍 文献精细筛选
![文献精细筛选](./assets/screenshots/image-20260421154314135.png)
可视化卡片式确认，支持手动剔除无关条目以确保后续分析精度。

---

### 🌐 领域概念雷达
![领域概念雷达](./assets/screenshots/image-20260421154902495.png)
AI 自动生成领域全景脉络图，揭示核心技术与概念之间的深层关联。

---

### 📂 核心文献资产库
![核心文献库](./assets/screenshots/image-20260421154920986.png)
集中展示深度解析后的学术资产，支持元数据预览与原文追溯。

---

### 📉 学术数据情报
![学术数据情报](./assets/screenshots/image-20260421154929567.png)
多维矩阵式挖掘，自动提取研究方法、关键指标与前沿定性结论。

---

### 🛡️ 红队学术批判
![红队学术批判](./assets/screenshots/image-20260421154944692.png)
针对综述的潜在盲点、过度假设与争议领域进行高密度的“红队律师”式考问。

---

### ✍️ 综述合成工坊
![综述合成工坊](./assets/screenshots/image-20260421154955855.png)
产出具备严谨引注的综述，并辅以术语百科（Jargon Buster）辅助理解。

---

### 🤖 学术 AI 导师
![学术 AI 导师](./assets/screenshots/image-20260421155002548.png)
Interactive Copilot，针对生成的综述内容提供即时答疑与知识拓展。

---

<p align="center">
  <b>DeepScholar</b> —— 提升学术研究的效率与深度
</p>
