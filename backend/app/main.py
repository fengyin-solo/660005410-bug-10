import re, math, time, random, json, sqlite3, uuid, os
from typing import Optional
import numpy as np
from collections import defaultdict, Counter
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Log Anomaly Detector")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------------------------------------------------------------------
# Snapshot persistence
#
# A snapshot is the single source of truth for one generation: it stores the
# FULL generated log set plus the latest analysis envelope. /api/detect always
# recomputes from the stored full log set (never from the truncated page the
# client displays), and /api/snapshot/latest restores the exact same view after
# a page refresh or re-entry.
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots.db")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                log_type    TEXT NOT NULL,
                count       INTEGER NOT NULL,
                rules_json  TEXT NOT NULL,
                query       TEXT NOT NULL,
                logs_json   TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            )"""
        )


init_db()


def save_snapshot(snapshot_id, log_type, count, rules, query, logs, envelope, create_only=False):
    now = time.time()
    with _db() as conn:
        if create_only:
            conn.execute(
                """INSERT INTO snapshots
                   (snapshot_id, log_type, count, rules_json, query, logs_json, result_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (snapshot_id, log_type, count, json.dumps(rules, ensure_ascii=False), query,
                 json.dumps(logs, ensure_ascii=False), json.dumps(envelope, ensure_ascii=False), now, now),
            )
        else:
            row = conn.execute("SELECT snapshot_id FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="snapshot not found")
            conn.execute(
                """UPDATE snapshots SET rules_json=?, query=?, result_json=?, updated_at=?
                   WHERE snapshot_id=?""",
                (json.dumps(rules, ensure_ascii=False), query,
                 json.dumps(envelope, ensure_ascii=False), now, snapshot_id),
            )


def load_snapshot(snapshot_id):
    with _db() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    if row is None:
        return None
    return {
        "snapshotId": row["snapshot_id"],
        "logType": row["log_type"],
        "count": row["count"],
        "rules": json.loads(row["rules_json"]),
        "query": row["query"],
        "logs": json.loads(row["logs_json"]),
        "result": json.loads(row["result_json"]),
    }


def latest_snapshot():
    with _db() as conn:
        row = conn.execute("SELECT result_json FROM snapshots ORDER BY updated_at DESC LIMIT 1").fetchone()
    return json.loads(row["result_json"]) if row else None


LOG_TEMPLATES = {
    "nginx": {
        "pattern": r'(?P<timestamp>\S+ \+\d{4}) (?P<source>\S+) (?P<level>\w+) (?P<message>.+)',
        "generator": lambda: {
            "timestamp": f"{random.randint(1,28):02d}/{'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[random.randint(0,11)]}/{2024}:{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d} +0000",
            "source": random.choice(["nginx", "api-gateway", "load-balancer"]),
            "level": random.choices(["INFO", "WARN", "ERROR", "DEBUG"], weights=[50, 15, 5, 30])[0],
            "message": random.choice([
                'GET /api/users 200 0.032s', 'POST /api/orders 201 0.145s', 'GET /api/products 304 0.008s',
                'GET /static/main.js 200 0.002s', 'POST /api/login 401 0.023s', 'GET /admin 403 0.005s',
                'GET /api/health 200 0.001s', 'GET /api/orders?page=2 200 0.056s', 'connection timeout upstream',
                'SSL handshake failed', 'worker process exited on signal 9', 'upstream server unavailable'
            ])
        }
    },
    "apache": {
        "pattern": r'\[(?P<timestamp>[^\]]+)\] \[(?P<level>\w+)\] \[(?P<source>\S+)\] (?P<message>.+)',
        "generator": lambda: {
            "timestamp": f"{'Sun Mon Tue Wed Thu Fri Sat'.split()[random.randint(0,6)]} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[random.randint(0,11)]} {random.randint(1,28):02d} {random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d} {2024}",
            "source": random.choice(["httpd", "mod_ssl", "mod_rewrite"]),
            "level": random.choices(["notice", "warn", "error", "info"], weights=[40, 15, 5, 40])[0],
            "message": random.choice(["server configured", "caught SIGTERM", "resuming normal ops", "request exceeded limit",
                        "file does not exist", "client denied by server", "Invalid method in request"])
        }
    },
    "json_app": {
        "pattern": None,
        "generator": lambda: {
            "timestamp": f"{2024}-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}.{random.randint(0,999):03d}Z",
            "source": random.choice(["user-service", "order-service", "payment-service", "auth-service"]),
            "level": random.choices(["INFO", "WARN", "ERROR", "DEBUG"], weights=[45, 20, 5, 30])[0],
            "message": random.choice([
                'User login successful user_id=10' + str(random.randint(100, 999)),
                'Order created order_id=ORD-' + str(random.randint(10000, 99999)),
                'Payment processed amount=' + str(random.randint(10, 999)),
                'Database connection pool exhausted',
                'Cache miss for key user_session_' + str(random.randint(100, 999)),
                'Circuit breaker opened for service payment',
                'Request latency exceeds threshold 5000ms',
                'NullPointerException at com.app.controller.UserController.getProfile'
            ])
        }
    },
    "custom": {
        "pattern": None,
        "generator": lambda: {
            "timestamp": str(int(time.time() - random.randint(0, 86400))),
            "source": random.choice(["cron", "systemd", "kernel", "docker"]),
            "level": random.choices(["info", "warning", "error", "debug"], weights=[40, 20, 5, 35])[0],
            "message": random.choice(["OOM killer invoked", "disk usage above 90%", "container restarted", "NTP sync lost",
                        "process oom_score_adj=500", "firewall rule updated", "mount point not found"])
        }
    }
}


class GenerateRequest(BaseModel):
    type: str = "nginx"
    count: int = 1000
    rules: list = []
    query: str = ""


class DetectRequest(BaseModel):
    snapshotId: Optional[str] = None
    logs: Optional[list] = None
    rules: list = []
    query: str = ""


def _envelope(snapshot_id, log_type, rules, query, analysis):
    """One response shape shared by generate / detect / snapshot restore, so the
    server-side contract is identical on every path."""
    return {
        "snapshotId": snapshot_id,
        "logType": log_type,
        "query": query,
        "rules": rules,
        **analysis,
    }


@app.post("/api/generate")
def generate_logs(req: GenerateRequest):
    tmpl = LOG_TEMPLATES.get(req.type, LOG_TEMPLATES["nginx"])
    logs = []
    for i in range(req.count):
        entry = tmpl["generator"]()
        logs.append({
            "id": i + 1,
            "timestamp": entry["timestamp"],
            "level": entry["level"],
            "source": entry["source"],
            "message": entry["message"],
            "raw": f"[{entry['timestamp']}] [{entry['level']}] [{entry['source']}] {entry['message']}"
        })

    analysis = analyze_logs(logs, req.rules, req.query)
    snapshot_id = uuid.uuid4().hex
    envelope = _envelope(snapshot_id, req.type, req.rules, req.query, analysis)
    # Persist the FULL log set; the envelope only carries the display page.
    save_snapshot(snapshot_id, req.type, len(logs), req.rules, req.query, logs, envelope, create_only=True)
    return envelope


@app.post("/api/detect")
def detect_anomalies(req: DetectRequest):
    # Always recompute from the full log set owned by the snapshot, so windowing
    # and anomaly scores are identical to generation regardless of query/rules.
    snap = load_snapshot(req.snapshotId) if req.snapshotId else None
    if req.snapshotId and snap is None:
        raise HTTPException(status_code=404, detail="snapshot not found or expired")

    if snap is not None:
        logs = snap["logs"]
        log_type = snap["logType"]
        snapshot_id = req.snapshotId
    else:
        # Stateless fallback for clients posting logs directly: still snapshot
        # the result so it survives refresh.
        logs = req.logs or []
        log_type = "unknown"
        snapshot_id = uuid.uuid4().hex

    analysis = analyze_logs(logs, req.rules, req.query)
    envelope = _envelope(snapshot_id, log_type, req.rules, req.query, analysis)
    save_snapshot(snapshot_id, log_type, len(logs), req.rules, req.query, logs, envelope,
                  create_only=snap is None)
    return envelope


@app.get("/api/snapshot/latest")
def get_latest_snapshot():
    envelope = latest_snapshot()
    if envelope is None:
        raise HTTPException(status_code=404, detail="no snapshot available")
    return envelope


def analyze_logs(logs_data, rules, query):
    logs = logs_data
    n = len(logs)

    # Time windows (1min each for demonstration)
    window_size = 20
    windows = []
    for i in range(0, n, window_size):
        chunk = logs[i:i + window_size]
        levels = Counter(l["level"] for l in chunk)
        sources = Counter(l["source"] for l in chunk)
        windows.append({
            "start": i, "end": min(i + window_size, n),
            "count": len(chunk),
            "levels": dict(levels),
            "sources": dict(sources)
        })

    anomalies = []
    if n > 0:
        # 3-sigma + IQR anomaly detection — computed on the full log set
        counts = [w["count"] for w in windows]
        mean = float(np.mean(counts))
        std = float(np.std(counts)) if len(counts) > 1 else 1.0
        q1 = float(np.percentile(counts, 25)) if len(counts) > 3 else mean - std
        q3 = float(np.percentile(counts, 75)) if len(counts) > 3 else mean + std
        iqr = q3 - q1 if q3 > q1 else 1.0

        for i, w in enumerate(windows):
            sigma_score = abs(w["count"] - mean) / max(std, 1e-5)
            iqr_low = q1 - 1.5 * iqr
            iqr_high = q3 + 1.5 * iqr
            iqr_score = 0.0
            if w["count"] < iqr_low or w["count"] > iqr_high:
                iqr_score = min(10.0, abs(w["count"] - (mean)) / max(iqr, 1e-5))
            anomalies.append({
                "windowIndex": i,
                "sigmaScore": round(sigma_score, 2),
                "iqrScore": round(iqr_score, 2),
                "isAnomaly": sigma_score > 2.5 or iqr_score > 3.0,
                "timestamp": logs[i * window_size]["timestamp"] if i * window_size < len(logs) else ""
            })

    # Alert rules — timestamps derive from the window data (not wall clock) so
    # the same snapshot yields byte-identical alerts on generate/detect/reload.
    alerts = []
    for i, rule in enumerate(rules):
        rule = rule if isinstance(rule, dict) else {}
        for w in windows:
            window_ts = logs[w["start"]].get("timestamp", "") if w["start"] < len(logs) else ""
            if rule.get("type") == "level" and w["levels"].get("ERROR", 0) > rule.get("threshold", 5):
                alerts.append({
                    "id": len(alerts) + 1, "ruleName": rule.get("name", "高频ERROR"),
                    "severity": "high", "message": f"窗口{w['start']}内ERROR日志{w['levels']['ERROR']}条超过阈值{rule.get('threshold',5)}",
                    "timestamp": window_ts
                })
            if rule.get("type") == "count" and w["count"] > rule.get("threshold", 200):
                alerts.append({
                    "id": len(alerts) + 1, "ruleName": rule.get("name", "异常流量"),
                    "severity": "medium", "message": f"窗口{w['start']}日志量{w['count']}超过阈值",
                    "timestamp": window_ts
                })

    # Add non-rule alerts for high anomaly windows
    for a in anomalies:
        if a["isAnomaly"]:
            alerts.append({
                "id": len(alerts) + 1, "ruleName": "统计异常检测",
                "severity": "critical" if a["sigmaScore"] > 4 else "high",
                "message": f"窗口{a['windowIndex']}: 3-sigma={a['sigmaScore']}, IQR={a['iqrScore']}",
                "timestamp": a["timestamp"]
            })

    # Full-text search only affects the displayed log page; it must never touch
    # windowing / anomaly scores, which always describe the full log set.
    display_logs = logs
    if query:
        query_terms = query.lower().split()
        scored = []
        for log in logs:
            raw_lower = log["raw"].lower()
            score = sum(1 for t in query_terms if t in raw_lower)
            if score > 0:
                scored.append((score, log))
        display_logs = [l for _, l in sorted(scored, key=lambda x: x[0], reverse=True)]

    return {
        "logs": display_logs[:200],
        "windows": windows,
        "anomalies": anomalies,
        "alerts": alerts[:20],
        "totalLogs": n
    }
