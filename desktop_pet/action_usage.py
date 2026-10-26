"""Local, bounded usage ranking for the three adaptive menu shortcuts.

Only reviewed built-in actions are eligible. A use means a successful action
invocation (including opening a dialog), not completion of a dialog or a system
side effect. Lifetime count has a small logarithmic weight; recent use decays
with a seven-day half-life. No labels, arguments or external telemetry are saved.
"""
import logging
import math
import time

KEY = 'navigation.action_usage'
HALF_LIFE_SECONDS = 7 * 24 * 60 * 60
DEFAULT_IDS = ('companion.greeting', 'productivity.focus', 'shortcuts.mute')
ELIGIBLE_IDS = DEFAULT_IDS + (
    'companion.blink', 'companion.stretch', 'companion.mouth',
    'companion.look', 'companion.relax', 'companion.idle',
    'productivity.reminder', 'productivity.todo',
    'shortcuts.volume_up', 'shortcuts.volume_down',
    'usage.today', 'settings.dnd', 'settings.history',
)


def _now(value):
    try:
        result = time.time() if value is None else float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError('Usage time must be a finite nonnegative timestamp') from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError('Usage time must be a finite nonnegative timestamp')
    return result


def _history(store):
    value = store.get(KEY, {})
    return value if isinstance(value, dict) else {}


def _entry(value):
    if not isinstance(value, dict):
        return 0, 0.0, 0.0
    count, recent, updated = value.get('count'), value.get('recent'), value.get('updated')
    if (type(count) is not int or count < 0 or count > 10 ** 12
            or type(recent) not in (int, float) or type(updated) not in (int, float)
            # Compare integers before conversion/isfinite: malformed persisted
            # integers may exceed the floating-point range.
            or recent < 0 or recent > 10 ** 12 or updated < 0 or updated > 10 ** 15
            or not math.isfinite(recent) or not math.isfinite(updated)):
        return 0, 0.0, 0.0
    return count, float(recent), float(updated)


def _decay(recent, updated, now):
    # A backward system-clock adjustment must not inflate use frequency.
    return recent * 2 ** (-max(0.0, now - updated) / HALF_LIFE_SECONDS)


def record_usage(store, action_id, now=None):
    """Record one completed invocation. Storage errors belong to the caller."""
    if action_id not in ELIGIBLE_IDS:
        return
    now = _now(now)
    history = _history(store)
    # Keep this setting bounded even after plugins/actions are retired.
    history = {key: value for key, value in history.items() if key in ELIGIBLE_IDS}
    count, recent, updated = _entry(history.get(action_id))
    history[action_id] = {
        'count': min(count + 1, 10 ** 12),
        'recent': min(_decay(recent, updated, now) + 1, 10 ** 12),
        'updated': now,
    }
    store.set(KEY, history)


def recommended_actions(registry, store, limit=3, now=None):
    """Return a stable snapshot of eligible live actions, without writing data.

    Call once per menu opening. Titles and enabled states remain owned by the
    registry; hidden plugin actions, stale IDs and risky/unreviewed commands do
    not become recommendations, regardless of stored usage.
    """
    now = _now(now)
    try:
        history = _history(store)
    except Exception:
        logging.exception('Could not read adaptive shortcut usage; using defaults')
        history = {}
    candidates = []
    for order, key in enumerate(ELIGIBLE_IDS):
        action = registry.items.get(key)
        if action is None or not registry.available(action):
            continue
        count, recent, updated = _entry(history.get(key))
        score = _decay(recent, updated, now) + 0.2 * math.log1p(count)
        candidates.append((-score, order, action))
    candidates.sort(key=lambda row: row[:2])
    return [row[2] for row in candidates[:max(0, int(limit))]]
