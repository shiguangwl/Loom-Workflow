# How we work
* Tasks live in `.backlog/` (Backlog.md CLI; `backlog <cmd> --help`). Cards are local state and stay out of git; only `.backlog/config.yml` is tracked. Chat is not state. Rebuild context from `backlog task list --plain`, `git branch --list 'task/*'`, `git worktree list`.
* Only the main agent writes Backlog state (`create`, `edit`, status changes), and only from the `main` checkout. Workers only read their card: `BACKLOG_CWD=<main checkout> backlog task <id> --plain`.
* Branch `task/<n>-<slug>` maps to task `task-<n>`; `<slug>` is a short lowercase kebab-case task summary. One branch, one worktree, one worker per task.
* On a `task/*` branch you are a worker. The delegated task and Review define your scope; planning, Backlog state, dependencies, and integration belong to the main agent.

## Planning
* If product direction, technical direction, or an important shared contract is still open, run the `grilling` skill first.
* Default to working on `main`. Create a task only when work runs in parallel or will outlive this session.
* While tasks are in flight, route every new request before creating anything: if it changes what an in-flight task should produce, or touches that task's area, it belongs to that task. Update the card (goal, decisions, acceptance criteria) and re-prompt the same worker in its pane; it re-reads the card. Only work independent of every in-flight task, or arriving after the related task is Done, becomes a new task.
* A task description holds Goal, Decisions with why, Out of scope, and acceptance criteria.
* Split only where parts can proceed independently; never just to make pieces smaller. Prefer demoable end-to-end vertical slices.
* Related tasks may share a parent epic:
  `backlog task create "<title>" [-p <epic-id>] --ac "<criterion>" --dep <task-ids>`
* Foundation work that defines shared contracts or enables parallel work is done on `main` first.
* Dispatch only tasks whose dependencies are Done, with at most 5 workers running concurrently. Product decisions and irreversible trade-offs go to the human.

## Doing work
* Main agent: work on `main` by default, one logical commit per complete change, with checks proportional to risk.
* Delegated task: work only in its worktree on `task/<n>-<slug>`. Never modify `.backlog/`, another branch, or another in-flight task's owned area without an explicit contract change.
* Implement the smallest solution that fully satisfies the task.
* Ambiguous shared or external contract: stop and ask in your own session; do not commit a guess.
* Local implementation ambiguity: make the smallest reversible choice consistent with existing conventions and continue.
* Workers may create checkpoint commits when useful. Before handoff, the worktree must be clean, the project's existing checks green, and the branch must represent one logical change suitable for squashing onto `main`. The tip commit's message becomes the `main` commit message.
* Final commit subject: `<type>(<scope>): 中文祈使句`.
* Final commit body: `What / Why`. Small changes fully explained by the subject may omit the body.
* Fresh worktree: install what the project already needs to run those checks (lockfile → `npm ci` / `pnpm i` / equivalent).
* Start each worker fresh with its task id, the absolute path of its worktree, and the absolute path of the `main` checkout. Everything else it needs belongs on the card; its open questions come back to the main agent, who records the answers on the card.
* Before each dispatch, check `HERDR_ENV`. If it is `1`, use the herdr skill even if the user did not mention Herdr: create the task worktree, place the Worker in the current tab to the right of the rightmost Worker, and keep the main pane focused. Do not leave the Worker in another workspace, and if Herdr fails, report it and stop — do not switch channels. Close the Worker pane before `integrate`; successful `integrate` removes the worktree. If `HERDR_ENV` is not `1`, use `git worktree add ../<repo>-task-<n> -b task/<n>-<slug> main`, start the same kind of agent in that directory, and deliver only `task-<n>` (`<repo>` is the current directory).

## Review
* Separate code review requires an explicit user request; users may invoke `review-changes`. Normal implementation verification and acceptance checks still apply.

## Integrate
* Infer the checks from the repo each time (`package.json` / Makefile / `justfile` / CI / `pyproject.toml` / `Cargo.toml` / `go.mod`): prefer an existing `check` or `ci` script, otherwise pass the existing test / typecheck / build commands separately. Do not invent a check the project does not have. Do not skip when one exists. Do not ask the human to configure it first.
* Use `.workflow/bin/integrate <n> -- <command> [args...]`, separating additional commands with `--next-check` (e.g. `-- npm test --next-check npm run build`). Commands run directly without shell parsing; do not join them with `&&` or `;`, or quote an entire command into one argument. A command's own `--` is preserved. Where scripts are not directly executable, prefix the invocation with `python`. If the repo has no quality command, `.workflow/bin/integrate <n>` and say so.
* It refuses anything it cannot merge safely: dirty `main`, uncommitted worker changes, worker edits to `.backlog/config.yml`, dependency violations, conflicts, inconsistent task/worktree state, or failed check.
* Worker checkpoint commits may be squashed; `main` receives one logical task commit.
* On success it validates the merged tree, squash-merges the task, marks `task-<n>` Done, moves its card to `.backlog/completed/`, and removes the worktree and branch.
* Any failure leaves `main` unchanged.
* Follow `integrate` errors instead of bypassing its guardrails.
* Conventions enter this file only when the human explicitly adopts them.
