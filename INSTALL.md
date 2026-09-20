# 安装与更新工作流

本文件由编码 agent 执行。用户给出本仓库的地址或本地路径，说「安装」或「更新」工作流，都按下面同一流程做。安装完成后，宿主只得到工作流运行所需的文件和 `.workflow/installed-files.json`；本文件、`README.md`、`skills-lock.json` 是 Loom 源仓库的开发资产，不复制到宿主。

- 装完即可用，不要让用户再填配置。未要求提交就不要提交。
- 只写本节列出的运行文件，或按规则合并的共享文件；不改宿主业务代码、测试、锁文件和任务；`.gitignore` 只追加 Backlog 忽略规则。
- 不与源仓库关联：不把源地址记进目标仓库，不动目标仓库的 git remote。下次更新时用户会再给一次地址。
- 源目录不能就是目标目录。若本地源路径解析后等于当前宿主根目录，立即停止；这样不会误删 Loom 源仓库自己的开发文件。

## 0. 安装边界与状态清单

### 宿主会接收的文件

以下是由 Loom 完整管理的运行文件。更新时只覆盖这些路径；技能目录以外的宿主技能和文件不动。

```
.workflow/VERSION
.workflow/bin/integrate                 # 保持可执行
.agents/skills/grilling/**              # 源树中该路径下的文件
.agents/skills/herdr/**
.agents/skills/orchestrator/**
.agents/skills/review-changes/**
.claude/skills/grilling                 # 符号链接 → ../../.agents/skills/grilling
.claude/skills/herdr                    # 符号链接 → ../../.agents/skills/herdr
.claude/skills/orchestrator             # 符号链接 → ../../.agents/skills/orchestrator
.claude/skills/review-changes           # 符号链接 → ../../.agents/skills/review-changes
```

`**` 只代表源树实际分发的单个文件或符号链接，不代表要删除目标目录里的其它内容。目录本身永远不是清理目标。

以下路径保留工作流需要的入口，但属于合并或初始化管理，不写入清理清单：

```
AGENTS.md
CLAUDE.md
.claude/CLAUDE.md
.backlog/config.yml                  # 只在宿主没有 .backlog/ 时初始化
.gitignore                           # 只追加缺失的 Backlog 规则
```

安装绝不复制或覆盖宿主的 `INSTALL.md`、`README.md`、`skills-lock.json`。源仓库仍保留这些文件，供下一次安装时读取。任务卡是本机状态，不进 git：宿主 `.gitignore` 只追加下面两行中缺失的行，不加其它规则。

```
.backlog/*
!.backlog/config.yml
```

### `.workflow/installed-files.json`

安装成功后在宿主生成清单。清单不提交到 Loom 源仓库，也不记录源 URL、绝对路径或自身。格式固定为：

```json
{
  "schemaVersion": 1,
  "version": "<源树 .workflow/VERSION 的内容>",
  "files": {
    ".workflow/VERSION": {"sha256": "<sha256>"},
    ".workflow/bin/integrate": {"sha256": "<sha256>"},
    ".agents/skills/grilling/SKILL.md": {"sha256": "<sha256>"},
    ".claude/skills/grilling": {"linkTarget": "../../.agents/skills/grilling"}
  }
}
```

`files` 的键全部是相对于宿主根目录的 POSIX 路径。普通文件只记录 `sha256`（小写十六进制，不含文件名或空白）；符号链接只记录 `linkTarget`（`readlink` 读出的原始目标字符串）。哈希用 `python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' <file>` 计算。只记录源树本次明确分发的单个文件/链接，按路径排序；不记录目录、合并管理的 `AGENTS.md` / `CLAUDE.md` / `.claude/CLAUDE.md` / `.backlog/config.yml`，也不记录清单自身。

## 1. 取源并预读状态

先确定宿主根目录 `dest=$(pwd -P)`，再取源。git URL 浅克隆到固定临时目录，第 4 节收尾时删除；本地路径直接使用，不改它也不删它。GitHub blob/tree URL 先收成仓库根。用户没给地址就问，不要猜。

```bash
# URL 和本地路径是两种互斥分支，按实际输入执行其中一支
# git URL：克隆到固定路径，收尾时显式删除
src=${TMPDIR:-/tmp}/loom-install-src
rm -rf "$src" && git clone -q --depth 1 <url> "$src"
# 本地路径：src=$(cd <local-path> && pwd -P)，永远不删
dest=$(pwd -P)
test "$src" != "$dest" || { echo '源目录不能是宿主目录' >&2; exit 1; }
```

不要用 `trap ... EXIT` 清理克隆目录，也不要依赖变量跨步骤存活：agent 通常每条命令都是新 shell，trap 会在当前命令结束时就删掉源树。每一步都按上面的固定路径重新推导 `src` 和 `dest`；临时文件一律用下文的固定文件名。

开始时先删除宿主里上次留下的 `.workflow/VERSION.tmp`、`.workflow/installed-files.json.tmp`、`.workflow/install-preread.tmp`（若存在）。确认源树存在 `.workflow/VERSION`、`.workflow/bin/integrate` 和第 0 节列出的指定技能路径；缺任一项就停止。**不要先覆盖再读取。**

在任何写入前完成以下预读：

1. 判断宿主是否已有 Loom 安装：`wasInstalled` 为复制前 `test -e .workflow/bin/integrate` 的结果；没有则是新装。后续合并 `AGENTS.md` 必须读预读文件里的值，不能在复制 integrate 后重新判断。
2. 若已有安装且宿主版本、清单 `version` 与源版本三者相同，`.workflow/installed-files.json` 是有效的 `schemaVersion=1` 清单，且清单内每个路径的当前 `sha256` 或 `linkTarget` 仍匹配，则报告已是最新并结束，不写任何文件。
3. 若已有安装但版本不同、没有清单、清单损坏，或清单与磁盘不一致，则继续更新。**同版本缺清单或文件对不上也必须补齐，不能直接跳过。**更新已有安装时，先确认宿主工作区干净；脏则列出文件并停止。新装不改宿主已有业务文件。
4. 读取并暂存宿主原有的 `AGENTS.md`、根 `CLAUDE.md`、`.claude/CLAUDE.md` 内容，之后才能覆盖/合并。
5. 读取并解析宿主旧 `.workflow/installed-files.json`。只有顶层 `schemaVersion=1`、`version` 是字符串、`files` 是对象，且每个路径都是安全的相对路径、每条记录恰好是 `sha256` 或 `linkTarget` 之一，**并且每个路径都属于第 0 节 Loom 完整管理的清理域**时，才把它作为清理授权。清理域包括 `.workflow/VERSION`、`.workflow/bin/integrate`、第 0 节指定 `.agents/skills/<skill>/` 路径下的任意历史单文件/链接，以及对应的固定 `.claude/skills/*` 链接；共享入口、Backlog 任务、锁文件、README 和其它宿主路径即使出现在格式有效的清单中也使整份清单失效。否则视为无有效清单，保留原文件并汇报。

判定需要继续写入后，把预读结果写成 `.workflow/install-preread.tmp`，三行：`wasInstalled=<true|false>`、`srcVersion=<源版本>`、`destVersion=<宿主版本或空>`。之后每步从该文件重读；成功或失败后都删除它。判定已是最新则不要创建该文件。

先运行 `command -v backlog || npm i -g backlog.md`。目标没有 git 时先 `git init -b main`；不要改 git remote。

## 2. 计算旧文件清理范围

在复制新文件前，根据刚才保存的旧清单和源树本次文件集合计算待清理项。新集合只包含第 0 节列出的 `.workflow/VERSION`、`.workflow/bin/integrate`、指定技能路径下源树本次实际存在的单个文件，以及对应的 `.claude/skills/*` 链接；不包含文档、清单和共享文件。旧清单的授权域则允许这些指定技能路径下已从源树删除的历史单文件/链接进入差集，但仍不得越过上述 Loom 清理域去删除共享入口、Backlog 任务、锁文件或业务文件。

旧清单中不在新集合的项，逐项执行以下检查：

- 清单记录 `sha256` 时，仅当目标当前是普通文件且当前 SHA-256 仍等于旧记录才 `unlink`；哈希不同、文件不存在或是目录都保留并汇报。
- 清单记录 `linkTarget` 时，仅当目标当前仍是符号链接且 `readlink` 结果仍等于旧记录才 `unlink`；目标改变、变成普通文件/目录或不存在都保留并汇报。
- 每次只删除一个普通文件或符号链接；清理宿主时不使用 `rm -rf`，不递归删除技能目录，也不删除空目录（安装结束时删除临时源目录不属于宿主清理）。清单中的路径若含绝对路径或 `..`，整份清单不用于清理。

## 3. 写入运行文件与共享入口

所有写入都在第 1 节的旧内容读取完成后进行。复制前确保父目录存在；失败就停止，不输出“安装完成”，并且不要提前写新的版本或成功清单。

在执行复制或 `ln` 之前检查目标类型：`.workflow`、`.workflow/bin`、`.agents`、`.agents/skills`、`.claude`、`.claude/skills` 若已存在必须是目录而不是符号链接；已有 `.workflow/VERSION`、`.workflow/bin/integrate` 必须是普通文件；第 0 节指定技能路径若已存在必须是目录；对应的 `.claude/skills/*` 若已存在必须已经是指向预期目标的符号链接。任一类型或链接目标冲突都先停止并汇报，不能让后面的 `cp`/`ln` 覆盖宿主内容。

确认目标类型无冲突后，从源树复制/更新以下内容：

```bash
mkdir -p .workflow/bin .agents/skills .claude/skills
cp "$src/.workflow/bin/integrate" .workflow/bin/integrate
chmod +x .workflow/bin/integrate
for skill in grilling herdr orchestrator review-changes; do
  cp -R "$src/.agents/skills/$skill" .agents/skills/
done
ln -sfn ../../.agents/skills/grilling .claude/skills/grilling
ln -sfn ../../.agents/skills/herdr .claude/skills/herdr
ln -sfn ../../.agents/skills/orchestrator .claude/skills/orchestrator
ln -sfn ../../.agents/skills/review-changes .claude/skills/review-changes
# 只暂存版本；先不要覆盖目标 VERSION
cp "$src/.workflow/VERSION" .workflow/VERSION.tmp
```

`cp -R` 只更新同名源文件并保留目标指定技能目录中的其它文件；不得用整个 `.agents/skills` 覆盖宿主技能目录。

### 合并 `AGENTS.md`

模板结构为 `# How we work`，以及模板拥有的 `## Planning`、`## Doing work`、`## Review`、`## Integrate` 四节。宿主自有的其它 `##` 节原样保留。

- 宿主没有 `AGENTS.md`：复制源树版本。
- `.workflow/install-preread.tmp` 中 `wasInstalled=true`：用源树替换上述模板拥有的标题节，原样放回宿主其它 `##` 节及其内容；不要用复制 integrate 之后的文件存在性重新判断。
- 宿主有 `AGENTS.md` 但不是 Loom 安装：使用源树全文，并在末尾追加原文件全文，标题为 `## Existing agent instructions`；不得丢弃旧规则。

不要整文件盲拷宿主 `AGENTS.md`。可用 `python3` 按二级标题切分和合并；合并结果应有 Integrate 节并引用 `.workflow/bin/integrate`。

### Claude 入口与 Backlog 初始化

根 `CLAUDE.md` 若不存在则复制源树版本；若已存在则保留原文，只确保第一行是 `@AGENTS.md`（原本只有重定向时不得改成其它内容）。`.claude/CLAUDE.md` 同理，首行应为 `@../AGENTS.md`。这两个文件都不写入清理清单。

宿主不存在 `.backlog/` 时，只复制 `$src/.backlog/config.yml` 为 `.backlog/config.yml`（先 `mkdir -p .backlog`），不要复制 `.backlog/tasks` 或整个 `.backlog/`，然后执行：

```bash
backlog config set projectName "$(basename "$(pwd)")"
```

已有 `.backlog/`（即使缺少 `config.yml`）则全部不动；不要运行 `backlog init`、`backlog agents --update-instructions`，不要改任务文件。`.gitignore` 缺 `.backlog/*` 或 `!.backlog/config.yml` 哪一行就追加哪一行，没有该文件就创建；不改已有内容。

## 4. 清理、生成清单并收尾

在所有复制、合并和初始化都成功后，按第 2 节逐项 `unlink` 旧清单废弃项。清理前再次检查当前字节/链接目标，任何不匹配都保留并汇报。

先验收运行文件、技能实际内容、链接目标、合并入口和 Backlog 初始化均成功，再把 `.workflow/VERSION.tmp` 原子改名为 `.workflow/VERSION`。确认这个新文件已经落盘后，才从宿主当前字节生成新清单：普通文件用宿主当前字节计算 SHA-256（包括刚写入的 `.workflow/VERSION`），符号链接用 `readlink` 记录目标；路径排序后写入临时文件，校验 JSON 可读，再原子改名为 `.workflow/installed-files.json`。清单生成时不要遍历或记录目录，不把清单自身加入 `files`。若中途失败，删除 `.workflow/VERSION.tmp`、`.workflow/installed-files.json.tmp` 和 `.workflow/install-preread.tmp`，不输出成功；下次运行仍按旧版本/旧清单处理。成功收尾后也删除 `.workflow/install-preread.tmp`。

```bash
mv .workflow/VERSION.tmp .workflow/VERSION
# 此处重新读取 .workflow/VERSION 计算 files 中的 sha256，写入并校验 .workflow/installed-files.json.tmp，最后：
mv .workflow/installed-files.json.tmp .workflow/installed-files.json
```

`.workflow/VERSION` 和 `.workflow/installed-files.json` 是成功收尾标记：在其它写入和验证通过后才依次写入/改名，清单里的 VERSION 哈希必须对应刚落盘的字节；任何失败不得提前宣称完成。最终验证至少包括：

```bash
test -x .workflow/bin/integrate
test "$(tr -d '[:space:]' < .workflow/VERSION)" = "$(tr -d '[:space:]' < "$src/.workflow/VERSION")"
python3 -m json.tool .workflow/installed-files.json >/dev/null
backlog task list --plain
```

源是 URL 时，验证通过后 `rm -rf "${TMPDIR:-/tmp}/loom-install-src"`；本地路径不删。然后汇报源版本（更新时写“旧版本 → 新版本”）、实际更新的运行文件、清理时保留的修改/未知文件，以及未提交状态。不要汇报或写入源 URL。

## 5. 安装后核验

每次安装完成后核验并汇报：`.workflow/VERSION` 与源版本一致且 `integrate` 可执行；清单是有效 JSON、`version` 与源/目标版本一致、只含第 0 节的 Loom 完整管理文件/链接且与磁盘哈希/链接目标匹配；`AGENTS.md` 含 Integrate 节且引用 `.workflow/bin/integrate`；根 `CLAUDE.md` 首行是 `@AGENTS.md`，`.claude/CLAUDE.md` 首行是 `@../AGENTS.md`；第 0 节列出的 `.claude/skills/*` 是指向 `.agents/skills/` 的预期符号链接；`backlog task list --plain` 能运行。根据预读快照确认宿主 `README.md`、`INSTALL.md`、`skills-lock.json`、业务文件、无关技能和已有任务未被覆盖，`.gitignore` 除两行 Backlog 规则外未变；旧清单清理中因修改、未知归属或类型冲突而保留的文件逐项报告。
