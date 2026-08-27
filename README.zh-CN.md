# DQ QuestionBank Core

[English](README.md) | **简体中文** | [中文产品站](https://wzsisshadiao-crypto.github.io/dq-questionbank-core/zh-CN/)

一个本地优先、开放、可扩展的可视化题库，围绕一道题从来源文档到经过核对的 Word 试卷构建完整工作流。

这是一个面向数学与教育场景的开源题库基础设施：支持中文题库、数学题库、题目管理、
可视化编辑、题库导入、LaTeX 公式、DOCX/Word、PDF、结构化表格、组卷、题库质检、
AI 辅助修正和多格式导出。题目内容可以使用中文或其他语言，公共技术接口仍以英文版本为准。

![成熟本地编辑中心中的 DX_SX_154](docs/assets/question-bank-workspace-zh.png)

> 上图来自作者的成熟本地工作区，展示仓库所有者明确批准公开的示例题 `DX_SX_154` 及公开迁移目标。生产数据库、其他私有题目数据、密钥、供应商配置和维护记录均不随仓库发布。

## 快速开始

需要 Python 3.10 或更新版本。三条路径任选其一：

1. **下载即用**：下载仓库 ZIP 或 clone → 解压 → 双击 `start.bat`（macOS/Linux 运行 `sh start.sh`）；
2. **pip 安装**：`pip install dq-questionbank-core`，然后运行 `dq-local`（`dq` 命令行工具同包提供）；
3. **源码终端**：进入仓库目录执行 `python run.py`。

浏览器自动打开 `http://127.0.0.1:8766`——程序仅在本机回环地址启动服务，
创建被 Git 忽略的本地工作区，并打开包含十道原创合成题的公共案例。
所有数据留在你的电脑上。第一次使用的完整走查见
[Wiki Getting Started](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/wiki/Getting-Started)。

## 当前可以使用的功能

- 题库、编辑、组卷、导入、数据和质检工作区；
- 规范且带版本的题目 Schema；
- JSON、Markdown、LaTeX 和约定式 DOCX 导入导出；
- 带版本指纹的 Word 引用块导出、本机桥接与可审计 VBA 模板；
- 离线 KaTeX 公式、结构化表格、答案与解析；
- 原子文件存储和只读 SQLite 公共案例；
- 插件发现、稳定公共 API 与兼容性 fixtures。
- 五条可执行导入案例：人工网页、网页 AI、常规 AI Coding、PDF AI Coding、考研 OMML 定制；
- 共用的来源证据、字段映射、AI 提案边界、人工接受/驳回与导出状态机。

直接运行案例：

```bash
dq intake cases
dq intake run coding-exam-omml -o workspace/coding-exam-omml
```

每条路径都会输出候选会话、复核会话和规范题集，不会自动写入题库。自定义来源只需在
bundle 边界提供提取记录和证据，后续校验、AI 字段边界、人工复核和导出逻辑完全共用。
详见[可复核导入案例](docs/import-cases.md)。

将复核后的规范题集发布为可刷新的 Word 引用块：

```bash
dq word-publish reviewed.json -o paper.docx --envelope paper.envelope.json
dq word-macro -o DQWordPublishing.bas
dq word-serve reviewed.json
```

宏只连接本机回环服务；题目缺失、版本指纹不匹配或刷新失败时保留原块。
技术契约及 Word 兼容性边界见[英文 Word 发布文档](docs/word-publishing-envelope.md)。

## 想参与贡献

不需要访问私有应用，也不一定需要编程经验：

- 有中文或多语言数学题：可以提交原创、合成或明确允许再分发的测试题；
- 熟悉 LaTeX：可以提供复杂公式、异常公式或公式渲染边界案例；
- 熟悉 Word：可以提供最小化的 DOCX 表格、分页、图片或公式案例；
- 熟悉 Python 或前端：可以认领小型测试、搜索体验和编辑器提示任务。

请先查看置顶的[测试题目征集 Issue](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues/28)，
并阅读[测试 fixture 提交规范](docs/test-fixture-contributions.md)。所有材料都必须有清晰的来源、
许可证和再分发权；网上能看到的题目不等于可以复制到仓库。

## 题目工作流

```text
来源文档
  → 可定制导入
  → 结构化与校验
  → 人工核对
  → 编辑与题库质检
  → 组卷
  → JSON / DOCX 导出
```

公开仓库现已提供可执行的 Word/PDF/OMML 合成导入案例、候选题核对、受约束的 AI 提案边界，以及不依赖私有数据库的 Word 宏发布实现。私有提取规则、生产题目、供应商接线与应用专用渲染配置不会直接复制；后续兼容性继续通过合成 fixture 和公共契约扩展。

## 架构与机制

系统分三层：**核心库** `dq_questionbank`（规范模型、校验、迁移、可复核导入、
质检、三套 LaTeX 引擎、格式与存储适配器）→ **可视化工作台**
`dq_questionbank_local`（仅本机回环服务）→ **你自己的数据**（本地文件，永不上传）。
依赖方向单向：应用层只用核心库的稳定公共 API，核心库默认不做任何网络与磁盘副作用。

题目数据流也是单向显式的：来源文档 → 候选题（什么都不落库）→ 人工逐字段核对
（摘要绑定，防止对旧版本的决策套到新版本上）→ 规范题集 → 质检循环 → 组卷与
可刷新的 Word 发布。每一步都是调用方显式选择的转移，不存在自动贯通。

完整指南（英文，社区规范语言）：

- [Architecture](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/wiki/Architecture)
  ——架构总览：三层结构、模块地图、数据流、硬边界、扩展点；
- [Mechanisms](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/wiki/Mechanisms)
  ——机制原理：Schema 版本化、原子存储、可复核导入、质检与安全修复门禁、
  三套 LaTeX 引擎、Word 发布信封与指纹刷新、PDF 工具链与 AI Coding 门禁、
  确定性验证栈、安全姿态。

对应的中文可读材料：[题目工作流](#题目工作流)、[当前可以使用的功能](#当前可以使用的功能)。

## 中文入口与英文规范

中文 README 和[中文产品站](https://wzsisshadiao-crypto.github.io/dq-questionbank-core/zh-CN/)
用于产品介绍、快速开始和社区沟通；产品站可以随时切换到 English。公共 API、CLI、Schema、Issue、
贡献规范和技术文档仍以英文版本为唯一规范来源，避免出现两套不一致的技术契约。

## 语言与开放边界

中文站和本文件是面向用户的本地化入口。公共 API 名称、CLI、Schema、Issue、贡献规范和技术文档仍以英文版本为唯一规范来源。题目内容本身支持多语言。

仓库绝不包含生产题库、真实用户数据、凭据、供应商配置或业务维护记录。详细边界见 [OPEN_SOURCE_BOUNDARY.md](OPEN_SOURCE_BOUNDARY.md)，贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
