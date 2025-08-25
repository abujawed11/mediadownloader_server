def fmt_bytes(n: int) -> str:
    if n is None:
        return "â€”"
    units = ["B","KB","MB","GB","TB"]
    u = 0
    v = float(n)
    while v >= 1024 and u < len(units) - 1:
        v /= 1024
        u += 1
    return f"{v:.1f} {units[u]}"
