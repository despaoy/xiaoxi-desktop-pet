import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / 'companion.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS usage (day TEXT, app TEXT, seconds REAL NOT NULL, PRIMARY KEY(day, app))')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (at TEXT, kind TEXT, value REAL)')
        self.db.commit()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))
        self.db.commit()

    def add_usage(self, day, app, seconds):
        self.db.execute('INSERT INTO usage VALUES (?,?,?) ON CONFLICT(day,app) DO UPDATE SET seconds=seconds+excluded.seconds', (day, app, seconds))
        self.db.commit()

    def usage(self, day):
        return self.db.execute('SELECT app,seconds FROM usage WHERE day=? ORDER BY seconds DESC', (day,)).fetchall()

    def usage_records(self, day, include_hidden=False, overrides=None):
        """Group raw usage rows into canonical applications.

        New rows store an app id; old rows store exe names. Both are resolved
        on read, so history is preserved without a destructive migration.
        """
        from desktop_pet import apps
        if overrides is None:
            overrides = self.get('plugin.usage.categories', {}) or {}
        grouped = {}
        for raw, seconds in self.usage(day):
            entry = apps.resolve_key(raw, overrides)
            if entry.hidden and not include_hidden:
                continue
            item = grouped.setdefault(entry.id, {
                'display': entry.display, 'category': entry.category,
                'seconds': 0.0, 'variants': set(),
                'hidden': entry.hidden, 'self': entry.self_process,
            })
            item['seconds'] += seconds
            item['variants'].add(str(raw))
        records = [
            apps.UsageRecord(key, value['display'], value['category'],
                             value['seconds'], variants=len(value['variants']),
                             hidden=value['hidden'], self_process=value['self'])
            for key, value in grouped.items()
        ]
        records.sort(key=lambda record: record.seconds, reverse=True)
        return records

    def usage_total(self, day):
        try:
            return sum(record.seconds for record in self.usage_records(day))
        except Exception:
            return sum(seconds for _, seconds in self.usage(day))

    def event(self, at, kind, value=1):
        self.db.execute('INSERT INTO events VALUES (?,?,?)', (at, kind, value))
        self.db.commit()

    def event_sum(self, day, kind):
        return self.db.execute('SELECT COALESCE(SUM(value),0) FROM events WHERE substr(at,1,10)=? AND kind=?', (day, kind)).fetchone()[0]

    def close(self):
        self.db.close()
