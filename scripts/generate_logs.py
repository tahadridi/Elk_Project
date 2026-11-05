#!/usr/bin/env python3
"""Generate fake security logs (CSV + NDJSON) for the ELK project."""
import argparse, csv, json, random, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from faker import Faker

COLUMNS = ["timestamp", "level", "service", "event_action",
           "event_outcome", "source_ip", "user_name", "message"]
SQLI = ["' OR '1'='1", "1; DROP TABLE users;--", "admin'--", "' UNION SELECT password FROM users--"]
XSS = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>"]
FILES = ["/confidential/payroll.xlsx", "/hr/contracts.pdf", "/db/backup.sql", "/finance/q3.xlsx"]


def build_events(fake, count, days, rng):
    now = datetime.now(timezone.utc)
    users = [fake.user_name() for _ in range(25)] + ["admin", "root"]
    attackers = [fake.ipv4_public() for _ in range(6)]
    events = []

    def add(ts, level, service, action, outcome, ip, user, message):
        events.append({"timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "level": level,
                       "service": service, "event_action": action, "event_outcome": outcome,
                       "source_ip": ip, "user_name": user, "message": message})

    def rand_ts():
        return now - timedelta(seconds=rng.randint(0, days * 86400))

    # normal logins (about 60 percent of the volume)
    for _ in range(int(count * 0.6)):
        user, ip, ok = rng.choice(users), fake.ipv4_public(), rng.random() > 0.08
        add(rand_ts(), "INFO" if ok else "WARNING", "auth-service", "login",
            "success" if ok else "failure", ip, user,
            f"Login {'succeeded' if ok else 'failed'} for user {user}")

    # brute force bursts: many failures from the same IP in a few minutes
    for ip in attackers:
        start, target = rand_ts(), rng.choice(users)
        for i in range(rng.randint(8, 25)):
            add(start + timedelta(seconds=i * rng.randint(2, 8)), "WARNING", "auth-service",
                "login", "failure", ip, target, f"Login failed for user {target}")
        add(start + timedelta(minutes=3), "ERROR", "auth-service", "ip_blocked",
            "success", ip, target, f"IP {ip} blocked after 5 failed logins")

    n_rest = max(count - len(events), 20)
    for _ in range(n_rest):
        kind = rng.choice(["sqli", "xss", "firewall", "scan", "file", "admin"])
        ip, ts = rng.choice(attackers + [fake.ipv4_public()]), rand_ts()
        if kind == "sqli":
            add(ts, "CRITICAL", "waf", "sql_injection", "failure", ip, "",
                f"SQL injection attempt on /login: {rng.choice(SQLI)}")
        elif kind == "xss":
            add(ts, "ERROR", "waf", "xss_attempt", "failure", ip, "",
                f"Suspicious payload in comment field: {rng.choice(XSS)}")
        elif kind == "firewall":
            add(ts, "WARNING", "firewall", "firewall_block", "failure", ip, "",
                f"Blocked inbound TCP from {ip} to port {rng.choice([22, 23, 3389, 445, 8080])}")
        elif kind == "scan":
            add(ts, "ERROR", "ids", "port_scan", "failure", ip, "",
                f"Port scan detected from {ip} ({rng.randint(20, 400)} ports)")
        elif kind == "file":
            user, ok = rng.choice(users), rng.random() > 0.3
            add(ts, "INFO" if ok else "WARNING", "file-server", "file_access",
                "success" if ok else "failure", fake.ipv4_private(), user,
                f"Access to {rng.choice(FILES)} by {user}")
        else:
            add(ts, "INFO", "admin-console", "config_change", "success",
                fake.ipv4_private(), "admin", f"Admin changed setting {fake.word()}")

    events.sort(key=lambda e: e["timestamp"])
    return events


def bad_events():
    """Invalid rows to test the error path (bad IP, bad date)."""
    base = {"level": "INFO", "service": "auth-service", "event_action": "login",
            "event_outcome": "success", "user_name": "tester"}
    return [
        {**base, "timestamp": "2026-10-29T10:00:00Z", "source_ip": "999.1.1.1", "message": "bad ip row"},
        {**base, "timestamp": "not-a-date", "source_ip": "8.8.8.8", "message": "bad date row"},
    ]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=2000)
    p.add_argument("--days", type=int, default=3)
    p.add_argument("--out", default="data/input")
    p.add_argument("--file-id", default=uuid.uuid4().hex[:12])
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--with-errors", action="store_true", help="add invalid rows and a broken JSON line")
    a = p.parse_args()

    rng = random.Random(a.seed)
    fake = Faker()
    if a.seed is not None:
        Faker.seed(a.seed)
    events = build_events(fake, a.count, a.days, rng)
    if a.with_errors:
        events += bad_events()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{a.file_id}_security.csv"
    json_path = out / f"{a.file_id}_security.json"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(events)
    with open(json_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        if a.with_errors:
            f.write('{"timestamp": "2026-10-29T10:00:00Z", "level": broken json\n')

    print(f"{len(events)} events -> {csv_path} and {json_path}")


if __name__ == "__main__":
    main()
