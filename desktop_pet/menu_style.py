"""Menu-only presentation and metric budgets; no usage or business state."""
import math

SHORTCUT_LABELS = {
    'companion.greeting': '打招呼', 'companion.blink': '眨眨眼',
    'companion.stretch': '舒展翅膀', 'companion.mouth': '嘴型演示',
    'companion.look': '看看周围', 'companion.relax': '轻轻放松',
    'companion.idle': '恢复待机', 'productivity.reminder': '添加提醒',
    'productivity.todo': '添加待办', 'shortcuts.mute': '静音切换',
    'shortcuts.volume_up': '音量增加', 'shortcuts.volume_down': '音量降低',
    'usage.today': '今日排行', 'settings.history': '通知记录',
}
SHORTCUT_ICONS = {
    'productivity.focus': 'clock', 'productivity.reminder': 'bell',
    'productivity.todo': 'check', 'shortcuts.mute': 'speaker',
    'shortcuts.volume_up': 'speaker', 'shortcuts.volume_down': 'speaker',
    'usage.today': 'chart', 'settings.dnd': 'moon', 'settings.history': 'bell',
    'companion.look': 'eye', 'companion.blink': 'eye',
    'companion.stretch': 'sparkle', 'companion.relax': 'sparkle',
}


def shortcut_presentation(action_id, title):
    """Use meaningful action labels, not an ellipsis over the operation/state.

    Only fixed known aliases are shortened. Dynamic pause/resume/break titles
    remain verbatim; an unfamiliar future label expands the metric budget.
    """
    title = ' '.join(str(title).split())
    if action_id == 'productivity.focus':
        label = '开始专注' if title == '开始 25 分钟专注' else title
    elif action_id == 'settings.dnd':
        label = {'开启免打扰': '开启免扰', '关闭免打扰': '关闭免扰'}.get(title, title)
    else:
        label = SHORTCUT_LABELS.get(action_id, title)
    return label, SHORTCUT_ICONS.get(action_id, 'heart')


def display_scale(pixels_per_inch):
    """Tk's measured DPI drives fonts AND dimensions once, not just font size."""
    try:
        value = float(pixels_per_inch) / 96
    except (TypeError, ValueError, OverflowError):
        return 1.0
    return min(4.0, max(0.75, value)) if math.isfinite(value) else 1.0


def layout_width(measure, quick_labels, category_labels, scale, screen_width):
    # Three equal cells: icon+gap+horizontal padding=34 logical px, outer
    # insets/gaps=40px. This was absent from the old category-only calculation.
    quick = max((measure(label) for label in quick_labels), default=0)
    category = max((measure(label) for label in category_labels), default=0)
    wanted = max(280 * scale, 3 * (quick + 34 * scale) + 40 * scale,
                 category + 76 * scale)
    return min(math.ceil(wanted), max(120, int(screen_width) - 16))


def wrap_label(text, measure, width):
    """Keep every character on constrained screens instead of hiding meaning."""
    lines, current = [], ''
    for character in str(text):
        if current and measure(current + character) > width:
            lines.append(current)
            current = character
        else:
            current += character
    if current:
        lines.append(current)
    return lines or ['']
