"""将前台窗口原始采样整理为当天可审计的纯文本活动日志。"""

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT_DIR / "daily_worklog_config.json"
DEFAULT_OUTPUT = ROOT_DIR / "输出" / "工作日志"


def load_config(path):
    if not path.is_file():
        return {"output_dir": str(DEFAULT_OUTPUT)}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value):
    return datetime.fromisoformat(value)


def read_events(path, target_date=None):
    events = []
    bad_lines = 0
    if not path.is_file():
        return events, bad_lines
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                item = json.loads(line)
                item["_time"] = parse_time(item["ts"])
                if target_date:
                    event_date = item["_time"].strftime("%Y-%m-%d")
                    if event_date != target_date:
                        continue
                events.append(item)
            except (json.JSONDecodeError, KeyError, ValueError):
                bad_lines += 1
    return sorted(events, key=lambda item: item["_time"]), bad_lines


def build_segments(events):
    focus_events = [item for item in events if item.get("event") == "focus"]
    boundaries = [item for item in events if item.get("event") in {"focus", "heartbeat", "stop"}]
    segments = []
    for index, item in enumerate(focus_events):
        start = item["_time"]
        end = next((entry["_time"] for entry in boundaries if entry["_time"] > start), start)
        title = item.get("window_title") or "（窗口标题为空）"
        process = item.get("process_name") or "（应用名称未知）"
        key = (process, title)
        if segments and segments[-1]["key"] == key and (start - segments[-1]["end"]).total_seconds() <= 15:
            segments[-1]["end"] = end
        else:
            segments.append({"key": key, "start": start, "end": end})
    return [segment for segment in segments if segment["end"] >= segment["start"]]


def format_duration(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes}分{seconds:02d}秒"
    return f"{seconds}秒"


def write_report(output_path, date_text, raw_path, events, bad_lines):
    normal_stops = [item for item in events if item.get("event") == "stop" and item.get("reason") != "day_rollover"]
    all_stops = [item for item in events if item.get("event") == "stop"]
    in_progress = not all_stops and bool(events)
    segments = build_segments(events)
    if in_progress:
        status_text = f"采样进行中（截至 {datetime.now():%H:%M} 的快照）"
    elif all_stops:
        status_text = "采样已正常结束"
    else:
        status_text = "采样未见正常结束记录"
    lines = [
        f"每日工作活动记录｜{date_text}",
        "",
        "状态：" + status_text,
        f"原始采样：{raw_path}",
        "采集范围：前台窗口时间/应用/标题 + 键盘按键记录 + 剪贴板文本变化；不采集截图、音频、文件正文、网页 DOM 或 URL。",
        "说明：以下为活动事实，不代表已完成具体工作成果。",
        "",
        "活动时间线：",
    ]
    if not events:
        lines.extend(["- 未找到当天原始采样记录。", "", "原因：计划任务未运行、采样提前失败，或输出目录配置已变更。"])
    elif not segments:
        lines.extend(["- 原始记录中没有前台窗口事件。", "", "原因：采样期间无可读取的交互桌面窗口，或采样器异常。"])
    else:
        for segment in segments:
            start = segment["start"].strftime("%H:%M:%S")
            end = segment["end"].strftime("%H:%M:%S")
            duration = format_duration((segment["end"] - segment["start"]).total_seconds())
            process, title = segment["key"]
            lines.append(f"- {start}–{end}（{duration}）｜{process}｜{title}")
    # 键盘活动统计
    keystrokes = [item for item in events if item.get("event") == "keystroke"]
    if keystrokes:
        proc_ks = {}
        for k in keystrokes:
            p = k.get("process_name", "?")
            proc_ks[p] = proc_ks.get(p, 0) + 1
        lines.append("")
        lines.append("键盘按键统计（按应用）：")
        for proc, count in sorted(proc_ks.items(), key=lambda x: -x[1]):
            lines.append(f"  {proc}：{count} 次按键")
    # 剪贴板事件
    clipboards = [item for item in events if item.get("event") == "clipboard"]
    if clipboards:
        lines.append("")
        lines.append("剪贴板活动（最新 3 条）：")
        for cb in clipboards[-3:]:
            text = cb.get("text", "")[:80]
            proc = cb.get("process_name", "?")
            ts = cb["_time"].strftime("%H:%M:%S")
            lines.append(f"  {ts}｜{proc}｜{text}")

    lines.extend(["", f"原始事件数：{len(events)}", f"无法解析的原始行数：{bad_lines}"])
    if in_progress:
        lines.append("提示：采样仍在运行，本日志为截至生成时刻的中间快照。")
    elif not normal_stops and events:
        lines.append("异常说明：原始记录缺少正常结束的 stop 事件，可能是电脑关机、休眠、任务被中断或采样器异常退出。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="生成每日工作活动纯文本日志。")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    datetime.strptime(args.date, "%Y-%m-%d")
    output_dir = Path(load_config(args.config).get("output_dir", DEFAULT_OUTPUT))
    raw_path = output_dir / "raw" / f"{args.date}.jsonl"
    report_path = output_dir / f"{args.date}.txt"
    events, bad_lines = read_events(raw_path, target_date=args.date)
    write_report(report_path, args.date, raw_path, events, bad_lines)
    print(report_path)


if __name__ == "__main__":
    main()
