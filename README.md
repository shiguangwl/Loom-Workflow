# 工作流

安装和更新：把本仓库或 `INSTALL.md` 交给目标项目的编码 agent，说「安装工作流」或「更新工作流」。

## 目录

```
INSTALL.md                agent 执行：安装 / 初始化 / 更新
AGENTS.md                 agent 规则（必须在仓库根）
CLAUDE.md                 引用 AGENTS.md
.backlog/                 Backlog.md 任务库，只通过 backlog CLI 读写
.agents/skills/           grilling、herdr；.claude/skills 为其符号链接
skills-lock.json          skills 来源与版本
.workflow/bin/integrate   合并 task/<n> 到 main 并关闭 task-<n>
.workflow/SOURCE          安装后写入，更新时用（模板仓库本身没有）
```

Codex 和 Cursor 只从根目录读 `AGENTS.md`。装完即可用。合入检查由 agent 按仓库已有脚本选定。

## 使用

看板 `backlog board`。其余对 agent 说：讨论需求、拆任务、派 task-3、合 task-3。
