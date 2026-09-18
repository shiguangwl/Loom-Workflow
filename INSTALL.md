# 安装与更新工作流

本文件给编码 agent 执行。用户给出本仓库的地址或本地路径，说「安装」或「更新」工作流，都按下面同一流程做。

- 装完即可用，不要让用户再填配置。未要求提交就不要提交。
- 只动下面清单里的文件，不改宿主业务代码、测试、锁文件、`README.md` 或 `.backlog/` 里的任务。
- 不与源仓库关联：不把源地址记进目标仓库，不动它的 git remote。下次更新时用户会再给一次地址。

## 1. 取源

git URL 浅克隆到临时目录，用完删掉；本地路径直接用，不要改它。GitHub blob/tree URL 先收成仓库根。用户没给地址就问，不要猜。

```bash
src=$(mktemp -d) && git clone -q --depth 1 <url> "$src"
```

## 2. 比对版本

在目标仓库根（没有 git 就先 `git init -b main`）比对两边的 `.workflow/VERSION`：

- 目标没有 `.workflow/bin/integrate`：安装。
- 版本相同：已是最新，告诉用户，结束。
- 其余情况（含没有 `VERSION` 的旧安装）：更新。目标工作区必须干净，脏则列出文件停下。

## 3. 写入

先 `command -v backlog || npm i -g backlog.md`。

更新时，覆盖前先读目标里旧的 `INSTALL.md`：旧清单有、新清单没有的文件删掉。旧版留下的 `.workflow/SOURCE` 也删掉。

从源树覆盖写入清单（目录先 `mkdir -p`）：

```
.workflow/VERSION
.workflow/bin/integrate          # 保持可执行
.agents/skills/grilling/
.agents/skills/herdr/
.agents/skills/orchestrator/
.claude/CLAUDE.md
.claude/skills/grilling          # 符号链接 → ../../.agents/skills/grilling
.claude/skills/herdr             # 符号链接 → ../../.agents/skills/herdr
.claude/skills/orchestrator      # 符号链接 → ../../.agents/skills/orchestrator
CLAUDE.md                        # 内容只有 @AGENTS.md；宿主若已有实质内容则只确保首行是 @AGENTS.md
skills-lock.json
INSTALL.md
```

符号链接若 `cp` 没保住，就重建：

```bash
mkdir -p .claude/skills
ln -sfn ../../.agents/skills/grilling .claude/skills/grilling
ln -sfn ../../.agents/skills/herdr .claude/skills/herdr
ln -sfn ../../.agents/skills/orchestrator .claude/skills/orchestrator
```

另外：

- `AGENTS.md`：按下节合并，不要整文件盲拷。
- `.gitignore`：只补宿主没有的行（`node_modules/`、`.env`、`.env.*`、`*.log`、`.DS_Store`），不改已有内容。
- `.backlog/config.yml` 不存在时：拷贝源树的，再 `backlog config set projectName "$(basename "$(pwd)")"`。已有 `.backlog/` 则不动。不要运行 `backlog init`、`backlog agents --update-instructions`（会写冲突的指令文件或改状态集）。
- 合入时跑什么检查，由使用中的 agent 按 `AGENTS.md` Integrate 段从仓库现有入口选定，不要写进任何文件。

## 合并 AGENTS.md

模板结构：`# How we work`，然后 `## Planning` / `## Doing work` / `## Review` / `## Integrate`。这些章节由模板拥有，更新时用源树替换。

宿主拥有：模板没有的其它 `##` 章节（用户明确写进本文件的约定）。原样放回。

- **无 AGENTS.md**：用源树的。
- **已是本工作流**（含 `.workflow/bin/integrate`）：用源树替换模板拥有部分，原样放回宿主拥有部分。
- **已有但不是本工作流**：用源树全文；把旧文整段接到末尾 `## Existing agent instructions`，不要丢。

合并可用 python3（`python3` 是 integrate 的依赖）。

根目录 `CLAUDE.md` 若原本不只是 `@AGENTS.md`：保留原文，确保第一行是 `@AGENTS.md`。`.claude/CLAUDE.md` 同理（`@../AGENTS.md`）。

## 验收

- `.workflow/VERSION` 与源树一致，`test -x .workflow/bin/integrate`
- `AGENTS.md` 在仓库根，含 Integrate 段与 `.workflow/bin/integrate`
- `CLAUDE.md` 第一行 `@AGENTS.md`
- `.claude/skills/grilling`、`herdr`、`orchestrator` 是指向 `.agents/skills/` 的符号链接
- `backlog task list --plain` 能跑
- 宿主 `README.md`、业务代码、已有任务未被覆盖

## 汇报

说明装的是哪个版本（更新时写 `旧版本 → 新版本`）、改了哪些文件、未提交。

之后对用户说：看板用 `backlog board`；日常直接说讨论需求、拆任务、派 task-3、合 task-3；想让当前会话只做调度、实现全部委派，输入 `/orchestrator`（Codex 用 `$orchestrator`）。规则以根目录 `AGENTS.md` 为准。
