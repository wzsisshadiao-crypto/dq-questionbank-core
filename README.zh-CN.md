# DQ QuestionBank Core

[English](README.md) | **简体中文** | [中文产品站](https://wzsisshadiao-crypto.github.io/dq-questionbank-core/zh-CN/)

一个本地优先、开放、可扩展的可视化题库，围绕一道题从来源文档到经过核对的 Word 试卷构建完整工作流。

![成熟本地编辑中心中的 DX_SX_154](docs/assets/question-bank-workspace-zh.png)

> 上图来自作者的成熟本地工作区，展示仓库所有者明确批准公开的示例题 `DX_SX_154` 及公开迁移目标。生产数据库、其他私有题目数据、密钥、供应商配置和维护记录均不随仓库发布。

## 快速开始

需要 Python 3.10 或更新版本：

```bash
python run.py
```

程序仅在本机回环地址启动服务，创建被 Git 忽略的本地工作区，并打开包含十道原创合成题的公共案例。

## 当前可以使用的功能

- 题库、编辑、组卷、导入、数据和质检工作区；
- 规范且带版本的题目 Schema；
- JSON、Markdown、LaTeX 和约定式 DOCX 导入导出；
- 离线 KaTeX 公式、结构化表格、答案与解析；
- 原子文件存储和只读 SQLite 公共案例；
- 插件发现、稳定公共 API 与兼容性 fixtures。

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

成熟私有应用还包含更完整的 Word/PDF 流程、候选题核对、受约束的 AI 修正和 Word 宏发布。这些模块会在经过边界审查、合成 fixture 和兼容测试后逐步迁移到公开仓库；这里不把迁移目标描述成已经可下载的功能。

## 语言与开放边界

中文站和本文件是面向用户的本地化入口。公共 API 名称、CLI、Schema、Issue、贡献规范和技术文档仍以英文版本为唯一规范来源。题目内容本身支持多语言。

仓库绝不包含生产题库、真实用户数据、凭据、供应商配置或业务维护记录。详细边界见 [OPEN_SOURCE_BOUNDARY.md](OPEN_SOURCE_BOUNDARY.md)，贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
