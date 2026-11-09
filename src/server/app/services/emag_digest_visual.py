"""Source-backed, bounded PNG digests. No network or generated imagery."""

from datetime import datetime, time, timedelta
from pathlib import Path
import os
import re
import unicodedata
from zoneinfo import ZoneInfo


def clean(value, limit=110):
    value = re.sub(r"https?://\S+", "", str(value or ""))
    return " ".join("".join(" " if unicodedata.category(c).startswith("C") else c for c in value).split())[:limit]


def build_visual(snapshot, report):
    from app.services import emag_digest

    end = datetime.fromisoformat(report["period"]["end"]).date()
    start = end - timedelta(days=7)
    labels = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    trend = {"dates": labels, "values": None, "basis": "unavailable"}
    if snapshot is not None:
        if snapshot["snapshot_id"] != report["snapshot_id"] or snapshot["store_id"] != report["store_id"]:
            raise ValueError("Visual snapshot identity mismatch")
        data = snapshot["data"]
        evidence = data.get("commercial_evidence", {})
        window = data.get("commercial_summary", {}).get("window", {})
        zone = ZoneInfo(report["timezone"])
        values = []
        bases = set()
        for day in labels:
            lower = datetime.combine(datetime.fromisoformat(day).date(), time(), zone)
            count = emag_digest._counts(
                evidence,
                "orders",
                window,
                lower,
                lower + timedelta(days=1),
                emag_digest._calendar_contract(snapshot, "orders", window),
            )
            values.append(count["current"])
            bases.add(count["basis"])
        if all(type(v) is int and v >= 0 for v in values) and len(bases) == 1:
            trend.update(values=values, basis=next(iter(bases)))
    return {"schema_version": 1, "snapshot_id": report["snapshot_id"], "trend": trend}


def _font(path, zh):
    from PIL import ImageFont

    if path:
        candidates = [Path(path)]
    else:
        candidates = [
            Path(p)
            for p in (
                os.environ.get("IVYEA_OPS_REPORT_FONT", ""),
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" if not zh else "",
                "C:/Windows/Fonts/msyh.ttc",
            )
            if p
        ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                loaded = ImageFont.truetype(str(candidate), 32)
                if zh and bytes(loaded.getmask("中")) == bytes(loaded.getmask("\u0378")):
                    continue
                return str(candidate)
            except OSError:
                pass
    raise ValueError("A readable report font is required")


def render(report, destination, *, font_path=None):
    """Render existing digest values; unknown values stay unknown, never inferred."""
    from PIL import Image, ImageDraw, ImageFont

    zh = report.get("locale") == "zh-CN"
    font = _font(font_path, zh)
    fonts = {s: ImageFont.truetype(font, s) for s in (22, 25, 28, 32, 38, 48, 62)}
    image = Image.new("RGB", (1120, 5000), "#f3f7fa")
    draw = ImageDraw.Draw(image)
    ink = "#142c3c"
    muted = "#526a7c"
    blue = "#167d9a"
    orange = "#ba4b2b"
    y = 52
    glyphs = {}
    missing = fonts[28].getmask("\U0010ffff")
    missing_shape = (missing.size, bytes(missing))

    def text(x, yy, value, size=28, color=ink, limit=110, max_width=None):
        content = clean(value, limit)
        width = 1060 - x if max_width is None else min(max_width, 1060 - x)
        truncated = False
        while content and draw.textlength(content + ("…" if truncated else ""), font=fonts[size]) > width:
            content = content[:-1]
            truncated = True
        content += "…" if truncated else ""
        for character in set(content):
            if character.isspace():
                continue
            if character not in glyphs:
                mask = fonts[28].getmask(character)
                glyphs[character] = bool(mask.getbbox()) and (mask.size, bytes(mask)) != missing_shape
            if not glyphs[character]:
                raise ValueError("Report font lacks a rendered character")
        draw.text((x, yy), content, font=fonts[size], fill=color)

    def wrapped(value, width=960, size=25, limit=500, color=ink):
        nonlocal y
        line = ""
        for char in clean(value, limit):
            if draw.textlength(line + char, font=fonts[size]) > width:
                text(68, y, line, size, color)
                y += 39
                line = ""
            line += char
        if line:
            text(68, y, line, size, color)
            y += 39

    def heading(title):
        nonlocal y
        y += 28
        draw.rounded_rectangle((44, y - 8, 1076, y + 54), 12, fill="white")
        text(64, y, title, 32)
        y += 76

    def value(v):
        return "待核对" if v is None and zh else "Unknown" if v is None else str(v)

    m = report.get("metrics", {})
    orders = m.get("orders", {})
    returns = m.get("returns", {})
    products = m.get("products", {})
    current = products.get("current", {})
    inventory = m.get("inventory_risks", {})
    title = (
        ("经营日报" if report["kind"] == "daily" else "经营周报")
        if zh
        else ("DAILY OPERATIONS" if report["kind"] == "daily" else "WEEKLY OPERATIONS")
    )
    text(60, y, title, 48)
    y += 72
    text(60, y, report.get("store_id"), 28, blue, 65)
    y += 45
    end = datetime.fromisoformat(report["period"]["end"]).date() - timedelta(days=1)
    text(60, y, f"{report['period']['start']} — {end}", 28)
    y += 43
    captured = report.get("captured_at")
    try:
        stamp = datetime.fromisoformat(captured.replace("Z", "+00:00"))
        captured = (
            stamp.astimezone(ZoneInfo(report["timezone"])).strftime("%Y-%m-%d %H:%M %Z")
            if stamp.tzinfo
            else value(None)
        )
    except (ValueError, TypeError, AttributeError, KeyError):
        captured = value(None)
    text(60, y, ("更新 " if zh else "Updated ") + str(captured), 22, muted)
    y += 38
    if report.get("freshness") != "fresh":
        text(60, y, "历史或缺失数据" if zh else "Stale or missing evidence", 25, orange)
        y += 45
    for i, (label, number, previous) in enumerate(
        [
            ("订单" if zh else "Orders", orders.get("current"), orders.get("previous")),
            ("退货申请" if zh else "Return requests", returns.get("current"), returns.get("previous")),
            (
                "已完成订单商品件数" if zh else "Finalized-order units",
                current.get("units"),
                products.get("previous", {}).get("units"),
            ),
        ]
    ):
        x = 44 + i * 348
        draw.rounded_rectangle((x, y, x + 336, y + 170), 16, fill="white")
        text(x + 20, y + 16, label, 22, max_width=296)
        text(x + 20, y + 55, value(number), 48, blue, max_width=296)
        delta = f" ({number - previous:+d})" if type(number) is int and type(previous) is int else ""
        text(x + 20, y + 122, ("上期 " if zh else "Previous ") + value(previous) + delta, 22, muted)
    y += 180
    heading("订单创建日期趋势 · 近7日" if zh else "Orders by creation date · 7 days")
    trend = report.get("visual", {}).get("trend", {})
    vals = trend.get("values")
    if isinstance(vals, list) and len(vals) == 7 and all(type(v) is int and 0 <= v <= 10**9 for v in vals):
        max_v = max(vals) or 1
        base = y + 210
        for i, v in enumerate(vals):
            x = 90 + i * 140
            h = int(v / max_v * 165)
            draw.rounded_rectangle((x, base - h, x + 75, base), 4, fill=blue) if h else draw.line(
                (x, base, x + 75, base), fill=blue, width=2
            )
            text(x, base - h - 38, v, 25)
            text(x - 5, base + 15, str(trend["dates"][i])[5:], 22, muted)
        y = base + 65
    else:
        wrapped(
            "来源日期或覆盖不足，趋势待核对。"
            if zh
            else "Trend unavailable: source dates or coverage need verification."
        )
    heading("商品件数前3" if zh else "Top products by finalized-order units")
    top = current.get("top")
    if isinstance(top, list) and top:
        if current.get("all_tied"):
            wrapped(("全部商品并列；展示其中3款。" if zh else "All products tie; showing three."))
        elif current.get("cutoff_tied_products", 0) > 1:
            wrapped("末位存在并列" if zh else "Tie at cutoff")
        maximum = max(row["units"] for row in top) or 1
        for row in top[:3]:
            text(68, y, row["label"], 25, ink, 42)
            y += 43
            draw.rounded_rectangle((68, y, 68 + max(2, int(row["units"] / maximum * 830)), y + 23), 6, fill=blue)
            text(940, y - 10, row["units"], 28)
            y += 50
    else:
        wrapped("本期无排行或明细待核对。" if zh else "No ranked units or product detail unavailable.")
    heading("订单状态 · 采集时观测" if zh else "Order states · observed at capture")
    statuses = orders.get("current_statuses")
    labels = {
        "0": ("取消", "Canceled"),
        "1": ("新订单", "New"),
        "2": ("处理中", "Processing"),
        "3": ("已备货", "Prepared"),
        "4": ("已完成", "Finalized"),
        "5": ("已退货", "Returned"),
    }
    if isinstance(statuses, dict):
        total = sum(statuses.values())
        x = 68
        colors = ["#a8b7bf", "#268bb3", "#5caab8", "#6a94be", "#226b79", "#cd7652"]
        for index, (code, n) in enumerate(sorted(statuses.items())):
            w = int(980 * n / total) if total else 0
            if w:
                draw.rectangle((x, y, x + w, y + 30), fill=colors[index % 6])
                x += w
        y += 45
        wrapped(
            " / ".join(
                f"{labels.get(code, ('未知', 'Unknown'))[0 if zh else 1]} {n}" for code, n in sorted(statuses.items())
            )
        )
    else:
        wrapped(value(None))
    heading("当前库存与风险" if zh else "Current inventory and risks")
    for a, b in [
        ("商品数 / Offers", m.get("offer_rows")),
        ("已知库存 / Known units", m.get("stock_known_total")),
        ("零库存商品 / Zero-stock offers", m.get("out_of_stock_rows")),
        ("库存未知商品 / Unknown stock offers", m.get("stock_unknown_rows")),
        ("有库存校验异常 / Stocked issues", inventory.get("blocked_products")),
        ("涉及件数 / Affected units", inventory.get("blocked_units")),
        ("181天以上已核对库存 / Reconciled 181+ units", inventory.get("aged_181_plus_units")),
        ("库龄待核对商品 / Aging unverified", inventory.get("aging_unverified_products")),
    ]:
        text(68, y, a.split(" / ")[0 if zh else 1], 25)
        text(950, y, value(b), 28, orange if "issue" in a or "Affected" in a else ink)
        y += 46
    for label, numerator, denominator in [
        (
            "零库存商品 / 所有商品" if zh else "Zero-stock offers / all offers",
            m.get("out_of_stock_rows"),
            m.get("offer_rows"),
        ),
        (
            "校验异常件数 / 已知库存件数" if zh else "Validation-issue units / known stock units",
            inventory.get("blocked_units"),
            m.get("stock_known_total"),
        ),
    ]:
        if type(numerator) is int and type(denominator) is int and 0 <= numerator <= denominator and denominator > 0:
            wrapped(f"{label}: {numerator} / {denominator}", size=22)
            draw.rounded_rectangle((68, y, 1048, y + 22), 6, fill="#dae4eb")
            if numerator:
                draw.rounded_rectangle((68, y, 68 + max(2, int(980 * numerator / denominator)), y + 22), 6, fill=orange)
            y += 42
    for row in inventory.get("priorities", [])[:3]:
        wrapped(f"{row['label']} · {row['stock']} " + ("件库存" if zh else "units in stock"))
    heading("费用与结算" if zh else "Fees and payouts")
    scopes = report.get("reconciliation", {}).get("scopes", [])
    if not scopes:
        wrapped("暂无已导入的结算证据，待核对。" if zh else "No imported payout evidence; reconciliation unknown.")
    for scope in scopes[:2]:
        coverage = scope.get("coverage", "partial")
        coverage_label = {"complete": "完整覆盖", "partial": "部分覆盖"}.get(coverage, "覆盖待核对") if zh else coverage
        wrapped(f"{scope['company']} / {scope['currency']} · {coverage_label}")
        wrapped(
            ("财务数据采集时间：" if zh else "Financial evidence captured: ")
            + str(scope.get("captured_at") or value(None))
        )
        payouts = scope.get("payouts", [])
        for payout in payouts[-2:]:
            superseded = payout.get("superseded_by_processed")
            if superseded:
                wrapped(
                    ("预计记录已被处理记录替代：" if zh else "Estimate superseded by processed record: ")
                    + str(superseded)
                )
                continue
            status = (
                {"estimated": "预计净额", "processed": "已处理净额"}.get(payout["status"], "待核对")
                if zh
                else payout["status"] + " net"
            )
            wrapped(
                f"{payout['payout_date']} · {status} · {payout['net_amount']} {scope['currency']}",
                color=orange if str(payout["net_amount"]).startswith("-") else ink,
            )
        wrapped(
            ("已确认抵扣关联 " if zh else "Confirmed allocation links ") + str(scope.get("confirmed_allocations", 0))
        )
        wrapped(("待核对项 " if zh else "Issues ") + str(scope.get("issue_count", len(scope.get("issues", [])))))
    if len(scopes) > 2:
        wrapped("更多主体/币种请查看文字与详细报告。" if zh else "More entities/currencies in the detailed report.")
    heading("优先检查" if zh else "Priority actions")
    marker = "## 优先检查" if zh else "## Priority checks"
    section = report.get("markdown", "").split(marker)[-1] if marker in report.get("markdown", "") else ""
    actions = []
    for line in section.splitlines():
        if line.lstrip().startswith("#"):
            break
        if line.startswith("- "):
            actions.append(line[2:])
    for line in actions[:3]:
        wrapped("• " + line)
    y += 28
    for note in [
        ("日期口径：" if zh else "Date basis: ")
        + (
            {
                "platform_calendar": "eMAG平台日期（时区未核实）",
                "verified_timezone": "已核实时区",
                "unavailable": "待核对",
                "mixed": "混合口径",
            }.get(report.get("date_basis"), "待核对")
            if zh
            else str(report.get("date_basis", "unavailable"))
        ),
        "订单按创建日期分组；状态为采集时观测；库存不是期间销量。"
        if zh
        else "Orders grouped by creation date; states at capture; stock is not period sales.",
        "预计/已处理结算均不代表银行到账；完整依据见详细报告。"
        if zh
        else "Estimated/processed payout does not prove bank receipt; see detailed evidence.",
        ("来源快照：" if zh else "Snapshot: ") + str(report.get("snapshot_id")),
    ]:
        wrapped(note, size=22)
    if y > 4950:
        raise ValueError("Visual report exceeds height bound")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.crop((0, 0, 1120, max(1600, y + 38))).save(destination, "PNG")
    destination.chmod(0o600)
    if destination.stat().st_size > 10_000_000:
        raise ValueError("Visual report exceeds size bound")
    return {
        "path": str(destination),
        "snapshot_id": report.get("snapshot_id"),
        "width": 1120,
        "height": max(1600, y + 38),
    }
