from ..extensions import get_redis


def _key(kind, ip):
    return f"auth:{kind}:{ip}"


def is_blocked(ip):
    return bool(get_redis().exists(_key("block", ip)))


def block_ttl(ip):
    return max(int(get_redis().ttl(_key("block", ip)) or 0), 0)


def failure_count(ip):
    return int(get_redis().get(_key("fail", ip)) or 0)


def record_failure(ip, max_failures, block_minutes):
    client = get_redis()
    failure_key = _key("fail", ip)
    ttl_seconds = max(int(block_minutes), 1) * 60
    pipe = client.pipeline()
    pipe.incr(failure_key)
    pipe.expire(failure_key, ttl_seconds)
    count = int(pipe.execute()[0])

    blocked = count >= max(int(max_failures), 1)
    if blocked:
        client.setex(_key("block", ip), ttl_seconds, "1")
    return count, blocked


def reset_failures(ip):
    get_redis().delete(_key("fail", ip))


def block_ip(ip, minutes):
    get_redis().setex(_key("block", ip), max(int(minutes), 1) * 60, "1")


def unblock_ip(ip):
    get_redis().delete(_key("block", ip), _key("fail", ip))


def list_blocked_ips():
    client = get_redis()
    keys = client.scan_iter(match="auth:block:*")
    results = []
    for key in keys:
        ip = key.split("auth:block:", 1)[1]
        results.append({"ip": ip, "ttl_seconds": max(int(client.ttl(key) or 0), 0)})
    return sorted(results, key=lambda item: item["ip"])
