# The context baseline of a background session

Measured on 2026-10-10. Before the first line of work, a background session already carried 72k tokens, reread on every
call. After compacting it went back up to about 113k (the baseline, the summary, the invoked skills and the recent files):
sessions compacted every 2 to 9 minutes, and two stopped on their own with "Autocompact is thrashing". What weighed, in a
minimal call:

| What goes away | Tokens per call |
|---|---|
| the Artifact tool (`CLAUDE_CODE_DISABLE_ARTIFACT`) | 11.9k |
| Workflow, ReportFindings and NotebookEdit denied | 2.8k |
| ScheduleWakeup and AskUserQuestion denied, the duplicated auto memory and the connectors | 7.5k |
| the built-in and synced skills out of the listing (`skillOverrides`) | 5.8k |

With the profile (`templates/background-session.settings.json`, passed with `--settings` on every launch and resume) the
session is born at 40k. Facts from the docs that support the profile: a tool denied by its bare name in `permissions.deny`
leaves the context entirely (a scoped rule only blocks the call); `skillOverrides: "user-invocable-only"` takes the skill
out of the model's listing and keeps it in the `/` menu.

What this teaches:
- **Measure with a real call**, one per variant: `"$C" --settings <file> -p "Answer only: ok"
  --output-format json --max-turns 1`, summing `input_tokens`, `cache_creation_input_tokens` and
  `cache_read_input_tokens`. `/context` is an estimate: it did not see the Artifact and gave the same with and without it.
- **Raising the window does not fix the baseline**: each call rereads more, and the baseline is still there. Cut the baseline.
- **The compaction window comes from the settings `env`** (`CLAUDE_CODE_AUTO_COMPACT_WINDOW`, global or project; it wins
  over `autoCompactWindow`). It is only read when the session is born: one already running stays on the old one until it
  is reopened.
- **Memory loaded twice** (the index imported by `CLAUDE.md` with `@` and again by the auto memory, when its directory is a
  symlink to the same index) is cut in the project, with `autoMemoryEnabled: false` in the `.claude/settings.local.json`
  of whoever imports: never in the global profile, because in a project that does not import the index it would vanish.
- **The memory index is a short hook**: one line per memory, the subject and when to open it; the fact lives in the file.
  The auto memory loads only the first 200 lines or the first 25 KB of `MEMORY.md`, whichever comes first: the rest does
  not arrive.
- **What comes back after compaction has a ceiling, and it is high**: each invoked skill comes back, and so do the recent
  files. A skill the step does not ask for is not loaded, and the resume of a session that already wrote the code loads none.
