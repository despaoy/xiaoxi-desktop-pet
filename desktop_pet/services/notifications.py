"""Notification history and delivery policy; windows remain view adapters."""
from collections import deque
from datetime import datetime


class NotificationService:
    def __init__(self, store, state, clock=datetime.now):
        self.store, self.state, self.clock = store, state, clock
        self.queue = deque()
        self.history = list(store.get('notification_history', []))[-100:]

    def publish(self, title, body, actions=None):
        history = (self.history + [{'at': self.clock().strftime('%m-%d %H:%M'),
                                    'title': title, 'body': body}])[-100:]
        self.store.set('notification_history', history)
        self.history[:] = history
        if self.state.dnd:
            return False
        self.queue.append((title, body, actions))
        return True

    def next(self):
        # Recheck at delivery, not only enqueue: DND may have changed meanwhile.
        if self.state.dnd:
            self.queue.clear()
            return None
        return self.queue.popleft() if self.queue else None

    def set_dnd(self, value):
        self.state.set_dnd(value)
        if value:
            self.queue.clear()
