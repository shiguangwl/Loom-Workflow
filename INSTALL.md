# 安装与更新工作流

本文件给编码 agent 执行。用户把本仓库、本文件或 GitHub URL 交给目标项目里的 agent，说「安装工作流」或「更新工作流」。

装完即可用，不要让用户再填配置。未要求提交就不要提交。不要改宿主业务代码、测试、锁文件或 `.backlog/` 里的任务。

## 不要拷贝

- `.git/`
- 宿主已有的 `README.md`（本仓库 README 只描述模板本身）
- 清单以外的任何文件

## SOURCE

按顺序取第一个能用的，写入目标仓库 `.workflow/SOURCE`（一行，git URL 或本地绝对路径）：

1. 用户给出的 git URL 或本地路径
2. 目标仓库已有的 `.workflow/SOURCE`
3. 当前这篇 `INSTALL.md` 所在的 git 仓库，且该仓库含 `.workflow/bin/integrate`

GitHub blob/tree URL 先收成仓库根 URL（去掉 `/blob/...`、`/tree/...`）。不要猜测 `OWNER/REPO`。

取到后浅克隆到临时目录（本地路径直接用，不要改它）：

```bash
tmp=$(mktemp -d)
git clone --depth 1 --branch main "$SOURCE" "$tmp"
# 本地路径则 tmp=$SOURCE
```

以后以 `$tmp` 为源树。远程克隆在结束后删掉临时目录。

## 模式

在**目标仓库根**判断（先 `cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"`）：

| 条件 | 模式 |
|---|---|
| 没有 git | 先 `git init -b main`，再安装 |
| 无 `.workflow/bin/integrate` | **安装** |
| 有 integrate，无 `.workflow/SOURCE` | **初始化**（本仓库是模板的克隆/拷贝；安装过的仓库一定有 SOURCE） |
| 有 integrate，有 `.workflow/SOURCE` | **更新** |

模式只看文件状态，不看用户说的是「安装」还是「更新」。

三种模式都要：`command -v backlog || npm i -g backlog.md`，并把 `.workflow/bin/integrate` 设为可执行。

## 工作流文件清单

从 `$tmp` 覆盖写入（目录先 `mkdir -p`）：

```
.workflow/bin/integrate
.agents/skills/grilling/
.agents/skills/herdr/
.claude/CLAUDE.md
.claude/skills/grilling          # 符号链接 → ../../.agents/skills/grilling
.claude/skills/herdr             # 符号链接 → ../../.agents/skills/herdr
CLAUDE.md                        # 内容只有 @AGENTS.md；宿主若已有实质内容则只确保首行是 @AGENTS.md
skills-lock.json
INSTALL.md
```

符号链接若 `cp` 没保住，就重建：

```bash
mkdir -p .claude/skills
ln -sfn ../../.agents/skills/grilling .claude/skills/grilling
ln -sfn ../../.agents/skills/herdr .claude/skills/herdr
```

`AGENTS.md` 必须在仓库根，按下面规则合并，不要整文件盲拷。

`.gitignore`：只补宿主没有的行（`node_modules/`、`.env`、`.env.*`、`*.log`、`.DS_Store`），不改已有内容。

## 安装

1. 解析 SOURCE，取源树。
2. 写入清单文件；合并 `AGENTS.md`。
3. 若无 `.backlog/config.yml`：拷贝 `$tmp/.backlog/config.yml`，然后
   `backlog config set projectName "$(basename "$(pwd)")"`。
   已有 `.backlog/` 则不动。
4. 不要运行 `backlog init`、`backlog agents --update-instructions`（会写冲突的指令文件或改状态集）。
5. 写 `.workflow/SOURCE`。
6. 对照「验收」自检，向用户汇报改了什么、未提交。不要要求用户再改 `AGENTS.md`。

## 初始化

已经在模板副本里时不要再克隆一份覆盖自己。

1. `backlog config set projectName "$(basename "$(pwd)")"`（若仍是 `workflow-template`）。
2. 写 `.workflow/SOURCE`：优先用户给的上游 URL，否则用 `git remote get-url origin`（仅当 origin 就是工作流仓库）；两者都没有则停下，向用户要工作流仓库地址。之后把 origin 改成项目自己的远程是用户的事，不要擅自 `git remote set-url`。
3. 验收并汇报。

## 更新

1. 目标仓库工作区必须干净。脏则停，列出文件，让用户先处理。
2. 用 SOURCE 取最新源树。源树没有 `INSTALL.md` 或 `integrate` 则停。
3. 覆盖清单里的工作流文件；按规则合并 `AGENTS.md`（保留宿主自增章节）。
4. 不改 `.backlog/`。
5. 用新 `INSTALL.md` 覆盖旧的。
6. 验收。向用户展示与 SOURCE 的 diff 摘要。已是最新就直说。

skills 只随本工作流更新（覆盖 `.agents/skills/` 与 `skills-lock.json`）。不要对宿主跑 `npx skills add`。用户若只要刷新 skills、不要工作流其余文件：`npx skills update`。

## 合并 AGENTS.md

模板结构：`# How we work`，然后 `## Planning` / `## Doing work` / `## Review` / `## Integrate`。这些章节由模板拥有，更新时用源树替换。

宿主拥有：模板没有的其它 `##` 章节（用户明确写进本文件的约定）。原样放回。

- **无 AGENTS.md**：用源树的。
- **已是本工作流**（含 `.workflow/bin/integrate`）：用源树替换模板拥有部分，原样放回宿主拥有部分。
- **已有但不是本工作流**：用源树全文；把旧文整段接到末尾 `## Existing agent instructions`，不要丢。

合并可用 python3（`python3` 是 integrate 的依赖）。

根目录 `CLAUDE.md` 若原本不只是 `@AGENTS.md`：保留原文，确保第一行是 `@AGENTS.md`。`.claude/CLAUDE.md` 同理（`@../AGENTS.md`）。

合入时跑什么检查，由使用中的 agent 按 `AGENTS.md` Integrate 段从仓库现有入口选定，安装阶段不要写进任何文件。

## 验收

- `test -x .workflow/bin/integrate`
- `AGENTS.md` 在仓库根，含 Integrate 段与 `.workflow/bin/integrate`
- `CLAUDE.md` 第一行 `@AGENTS.md`
- `.claude/skills/grilling` 与 `herdr` 是指向 `.agents/skills/` 的符号链接
- `backlog task list --plain` 能跑
- `.workflow/SOURCE` 存在且可用来再更新
- 宿主 `README.md`、业务代码、已有任务未被覆盖

## 之后

看板：`backlog board`。其余对用户说：讨论需求、拆任务、派 task-3、合 task-3。规则以根目录 `AGENTS.md` 为准。
