import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wellbeing.db')

# ──────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS usage_logs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id    TEXT    NOT NULL,
        device_name  TEXT    NOT NULL,
        package_name TEXT    NOT NULL,
        event_type   TEXT    NOT NULL,
        timestamp    TEXT    NOT NULL,
        duration_ms  INTEGER DEFAULT 0,
        received_at  TEXT    NOT NULL
    )''')
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# API endpoint
# ──────────────────────────────────────────────

@app.route('/api/logs', methods=['POST'])
def receive_logs():
    """Accept JSON payloads with device details and usage logs."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid or missing JSON payload'}), 400

    device_id   = data.get('device_id', 'unknown')
    device_name = data.get('device_name', 'unknown')
    logs        = data.get('logs', [])

    if not isinstance(logs, list) or len(logs) == 0:
        return jsonify({'error': 'No log entries provided'}), 400

    received_at = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cur  = conn.cursor()

    inserted = 0
    for entry in logs:
        try:
            cur.execute(
                '''INSERT INTO usage_logs
                   (device_id, device_name, package_name, event_type,
                    timestamp, duration_ms, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (
                    device_id,
                    device_name,
                    entry.get('package_name', ''),
                    entry.get('event_type', ''),
                    entry.get('timestamp', ''),
                    entry.get('duration_ms', 0),
                    received_at,
                ),
            )
            inserted += 1
        except Exception:
            pass  # skip malformed entries

    conn.commit()
    conn.close()
    return jsonify({'status': 'ok', 'inserted': inserted}), 200


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({'service': 'WellBeing Tracker Backend', 'status': 'running'})


# ──────────────────────────────────────────────
# Admin dashboard
# ──────────────────────────────────────────────

ADMIN_HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WellBeing Tracker &mdash; Admin Console</title>
  <style>
    :root { --accent: #4f46e5; --bg: #f8fafc; --card: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: var(--bg); color: #1e293b;
    }
    header {
      background: var(--accent); color: #fff; padding: 1.25rem 2rem;
      display: flex; align-items: center; gap: 0.75rem;
    }
    header h1 { font-size: 1.35rem; font-weight: 600; }
    .stats-bar {
      display: flex; gap: 1.5rem; padding: 1rem 2rem;
      flex-wrap: wrap;
    }
    .stat-card {
      background: var(--card); border-radius: 10px; padding: 1rem 1.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,.08); min-width: 180px;
    }
    .stat-card .label { font-size: .8rem; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
    .stat-card .value { font-size: 1.5rem; font-weight: 700; color: var(--accent); margin-top: .25rem; }
    .container { padding: 0 2rem 2rem; }
    table {
      width: 100%; border-collapse: collapse; background: var(--card);
      border-radius: 10px; overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,.08);
    }
    th {
      background: #f1f5f9; text-align: left; padding: .75rem 1rem;
      font-size: .8rem; text-transform: uppercase; letter-spacing: .04em;
      color: #475569; position: sticky; top: 0;
    }
    td { padding: .65rem 1rem; border-top: 1px solid #e2e8f0; font-size: .9rem; }
    tr:hover td { background: #f8fafc; }
    .badge {
      display: inline-block; padding: .15rem .55rem; border-radius: 999px;
      font-size: .75rem; font-weight: 600;
    }
    .badge-open   { background: #dcfce7; color: #166534; }
    .badge-close  { background: #fee2e2; color: #991b1b; }
    .badge-dur    { background: #dbeafe; color: #1e40af; }
    .empty { text-align: center; padding: 3rem; color: #94a3b8; }
  </style>
</head>
<body>
  <header>
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
    <h1>WellBeing Tracker &mdash; Admin Console</h1>
  </header>

  <div class="stats-bar">
    <div class="stat-card">
      <div class="label">Total Logs</div>
      <div class="value">{{ total }}</div>
    </div>
    <div class="stat-card">
      <div class="label">Unique Devices</div>
      <div class="value">{{ devices }}</div>
    </div>
    <div class="stat-card">
      <div class="label">Unique Apps</div>
      <div class="value">{{ apps }}</div>
    </div>
  </div>

  <div class="container">
    {% if logs %}
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Device Name</th>
          <th>Device ID</th>
          <th>App / Package</th>
          <th>Activity Type</th>
          <th>Duration</th>
          <th>Timestamp</th>
        </tr>
      </thead>
      <tbody>
        {% for row in logs %}
        <tr>
          <td>{{ row['id'] }}</td>
          <td>{{ row['device_name'] }}</td>
          <td><code>{{ row['device_id'][:12] }}…</code></td>
          <td>{{ row['package_name'] }}</td>
          <td>
            {% if 'open' in row['event_type']|lower or 'foreground' in row['event_type']|lower %}
              <span class="badge badge-open">{{ row['event_type'] }}</span>
            {% elif 'close' in row['event_type']|lower or 'background' in row['event_type']|lower %}
              <span class="badge badge-close">{{ row['event_type'] }}</span>
            {% else %}
              <span class="badge badge-dur">{{ row['event_type'] }}</span>
            {% endif %}
          </td>
          <td>{{ '%d min %d sec' | format(row['duration_ms'] // 60000, (row['duration_ms'] % 60000) // 1000) if row['duration_ms'] > 0 else '—' }}</td>
          <td>{{ row['timestamp'] }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="empty">No usage logs recorded yet. Waiting for data&hellip;</div>
    {% endif %}
  </div>
</body>
</html>
'''


@app.route('/admin')
def admin():
    conn = get_db()
    logs    = conn.execute('SELECT * FROM usage_logs ORDER BY timestamp DESC LIMIT 500').fetchall()
    total   = conn.execute('SELECT COUNT(*) FROM usage_logs').fetchone()[0]
    devices = conn.execute('SELECT COUNT(DISTINCT device_id) FROM usage_logs').fetchone()[0]
    apps    = conn.execute('SELECT COUNT(DISTINCT package_name) FROM usage_logs').fetchone()[0]
    conn.close()
    return render_template_string(ADMIN_HTML, logs=logs, total=total, devices=devices, apps=apps)


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print('\n  WellBeing Tracker Backend')
    print('  API  → http://0.0.0.0:5000/api/logs')
    print('  Admin → http://0.0.0.0:5000/admin\n')
    app.run(host='0.0.0.0', port=5000, debug=True)
