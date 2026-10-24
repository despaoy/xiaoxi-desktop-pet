# Qt hub host protocol

The Tk main process is the sole owner of SQLite, plugins, timer services and OS
commands. A spawned Qt process receives JSON-compatible snapshots and sends
allowlisted intents. No Qt/Tk event loops share a process. The child does not
open the database, load plugins, or persist application preferences.

## Messages

Child request: `{id: unique string, action: string, payload: object}`.
Host result: `{event: "result", id, ok, result? , error?}`.
Host snapshot: `{event: "snapshot", snapshot: object}`.
Host lifecycle: `{event: "show", page?}`, `{event: "hide"}`, `{event: "shutdown"}`.
Child lifecycle: `{event: "ready"}`, `{event: "error", error: string}`.

`HubWindow(send_command)` exposes `apply_snapshot`, `apply_result`, and
`select_page`. Close hides the window and sends `window.close`, not app exit.
Request IDs are deduplicated in the host (last 256). Requests are bounded to
64 KiB. All domain operations execute on the Tk thread. A bounded background
writer prevents a blocked child from hanging Tk. Startup timeout is 12 seconds;
missing PySide6, child failure, disconnect or backpressure returns to the old
fully functional Tk hub. Explicit exit stops the child before closing SQLite.

## Allowlist and payloads

- `action.invoke`: `{id}` from the live shared registry, including plugin actions.
- `timer.start`: `{minutes}` (1–240); `timer.pause`, `timer.resume`, `timer.stop`,
  `timer.break`: `{}`. Pause/resume are idempotent intents; break is five minutes.
- `todo.save`: `{id?, title}`; `todo.toggle`: `{id, done: bool}`;
  `todo.delete`: `{id}`. Omit ID to create. Completion timestamps are retained.
- `reminder.save`: `{id?, title, minutes, interval}` or `{id?,title,due,interval}`.
  Due is a future local ISO datetime without timezone. Interval is minutes, zero
  for one-shot. `reminder.delete`, `reminder.snooze`: `{id}`. Snooze creates a
  separate five-minute reminder and leaves the recurrence unchanged.
- `shortcut.save`: `{id?,name,target,kind}`; kind is `入口` or `场景`. A scene
  target is comma-separated names of existing entries, not executable code.
  `shortcut.delete`, `shortcut.launch`: `{id}`.
- `usage.range`: `{days:1|7|30}`; `usage.enabled`: `{enabled:bool}`;
  `usage.category`: `{id,category}` (built-in category code or label only);
  `usage.limit`: `{id,minutes}`; `usage.break`: `{minutes}` (0–1440, zero off).
- `settings.focused`, `settings.dnd`, `settings.speech`,
  `settings.favorite_hotkeys`, `settings.startup`: `{enabled:bool}`.
- `settings.behavior`: `{key,enabled:bool}`; key is breathe/blink/wings/hair/mouth/actions.
- `settings.visible`: `{visible:bool}`; `settings.scale`: `{scale}` (0.5–1.25,
  Live2D only); `settings.favorites`: `{ids}` (up to four unique registered IDs);
  `settings.double_click`: `{id}` (registered companion action).
- `plugin.enabled`: `{id,enabled:bool}`; applies on restart, does not hot unload.
- `language.save`: `{kind,key,lines}`; kind is events/actions and key must exist.
  `language.preview`: `{kind,key}`. Writes only the user-data override atomically.
- `command.run`: `{text}` invokes the existing local command parser, not a shell.
- `legacy.open`: `{page}` (companion/productivity/shortcuts/usage/settings).
- `data.open`, `plugins.open`, `app.exit`, `window.close`: `{}`.
- `window.editing`: `{editing:bool}` transient focus state only, no keystrokes.

UI retains confirmations before delete/lock/startup actions and communicates
pending/error states. Tests must mock OS actions, never lock or alter the test OS.

## Snapshot

Top-level: version, now, timer, timer_revision, focused, dnd, todos, reminders,
shortcuts, actions, favorites, usage, settings, plugins, history, summary,
language. Existing timer/reminder/todo record formats are preserved.

Actions have id/title/category/enabled. Usage has days/enabled/total/daily,
records `{id,display,category,seconds,limit}`, categories `{name,seconds}`,
category_choices `{id,label}`, break_minutes, error. Errors have total null,
not fake zero. Settings include behavior/speech/pet_visible/scale/double_click,
favorite_hotkeys/startup/live2d_mode/hotkey_registered. Plugin records preserve
runtime status separately from configured enabled state. Summary counts planned
focus minutes and today's completed todos. Language maps event/action keys to
line arrays. History retains the existing notification records.

Visible snapshots refresh at most once a second except after an explicit
command/show. Qt process PID is excluded from usage tracking. Editing focus
suppresses ambient interactions. Legacy settings remain available for PNG
import/reset, accents, permissions/detail views and other specialized editors;
this is a compatible migration, not removal of the legacy implementation.
