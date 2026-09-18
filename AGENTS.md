# How we work
* Tasks live in `.backlog/` (Backlog.md CLI; `backlog <cmd> --help`). Chat is not state. Rebuild context from `backlog task list --plain`, `git branch --list 'task/*'`, `git worktree list`.
* Only the main agent writes Backlog state (`create`, `edit`, status changes), and only on `main`. Workers only read their card with `backlog task <id> --plain`.
* Branch `task/<n>` always maps to task `task-<n>`.
* On a `task/*` branch you are a worker. The delegated task and Review define your scope; planning, Backlog state, dependencies, and integration belong to the main agent.

## Planning
* If product direction, technical direction, or an important shared contract is still open, run the `grilling` skill first.
* Default to working on `main`. Create a task only when work runs in parallel, will outlive this session, or overlaps an in-flight task's area.
* A task description holds Goal, Decisions with why, Out of scope, and acceptance criteria.
* Split only where parts can proceed independently; never just to make pieces smaller. Prefer demoable end-to-end vertical slices.
* Related tasks may share a parent epic:
  `backlog task create "<title>" [-p <epic-id>] --ac "<criterion>" --dep <task-ids>`
* Commit `.backlog/` before implementation.
* Foundation work that defines shared contracts or enables parallel work is done on `main` first.
* Dispatch only tasks whose dependencies are Done. Product decisions and irreversible trade-offs go to the human.

## Doing work
* Main agent: work on `main` by default, one logical commit per complete change, with checks proportional to risk.
* Delegated task: work only in its worktree on `task/<n>`. Never modify `.backlog/`, another branch, or another in-flight task's owned area without an explicit contract change.
* Implement the smallest solution that fully satisfies the task.
* Ambiguous shared or external contract: stop and ask in your own session; do not commit a guess.
* Local implementation ambiguity: make the smallest reversible choice consistent with existing conventions and continue.
* Workers may create checkpoint commits when useful. Before handoff, the worktree must be clean, the project's existing checks green, and the branch must represent one logical change suitable for squashing onto `main`. The tip commit's message becomes the `main` commit message.
* Final commit subject: `<type>(<scope>): 中文祈使句`.
* Final commit body:
  `What / Verified (command + relevant output) / Deviations`
  Add `Open questions` only when a genuine non-blocking issue remains.
* Fresh worktree: install what the project already needs to run those checks (lockfile → `npm ci` / `pnpm i` / equivalent).
* In Herdr, the `herdr` skill creates the task worktree, starts the worker in it, and removes that workspace before `integrate`. Outside Herdr: `git worktree add ../<repo>-task-<n> -b task/<n> main`, start the same kind of agent in that directory, deliver only `task-<n>`. `<repo>` is the current directory name.

## Review
* Cross-vendor review only when a wrong change would be costly and automated checks cannot sufficiently vouch for it: shared/public contracts, data or migrations, concurrency, security-sensitive boundaries, or edits to tests/checks themselves.
* Claude-authored → `codex review --uncommitted` on `main`, or `codex review --base main` in a task worktree.
* Codex-authored → a Claude session reviews the equivalent diff.
* Review findings are claims; verify them before acting.

## Integrate
* Infer the check from the repo each time (`package.json` / Makefile / `justfile` / CI / `pyproject.toml` / `Cargo.toml` / `go.mod`): prefer an existing `check` or `ci` script, otherwise compose the existing test / typecheck / build entries into one shell command. Do not invent a check the project does not have. Do not skip when one exists. Do not ask the human to configure it first.
* Use `.workflow/bin/integrate <n> -- <that command>` only. If the repo has no quality command, `.workflow/bin/integrate <n>` and say so.
* It refuses anything it cannot merge safely: dirty `main`, uncommitted worker changes, `.backlog/` edits, dependency violations, conflicts, inconsistent task/worktree state, or failed check.
* Worker checkpoint commits may be squashed; `main` receives one logical task commit.
* On success it validates the merged tree, squash-merges the task, marks `task-<n>` Done in the same state transition, and removes the worktree and branch.
* Any failure leaves `main` unchanged.
* Follow `integrate` errors instead of bypassing its guardrails.
* Conventions enter this file only when the human explicitly adopts them.
