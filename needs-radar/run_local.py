#!/usr/bin/env python3
"""本地启动器：不改 radar.py，通过环境变量把 LLM 指向国内模型/第三方中转站。
用法与 radar.py 完全一致：.venv/bin/python run_local.py --dry-run

.env 两种协议二选一（LLM_PROTOCOL 默认 anthropic）：
  anthropic：中转站/厂商提供 Anthropic 兼容接口（/v1/messages），只换 URL/key/模型名
  openai   ：中转站只提供 OpenAI 兼容接口（/v1/chat/completions），本文件内适配
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
import yaml

import radar

# ---- 端点与模型名走环境变量，避免改 radar.py / config.yaml ----
LLM_PROTOCOL = os.environ.get("LLM_PROTOCOL", "anthropic")  # anthropic | openai
if os.environ.get("LLM_BASE_URL"):
    radar.ANTHROPIC_URL = os.environ["LLM_BASE_URL"]

# 本地运行用独立的 seen.db（data_local/），不碰上游 git 跟踪的 data/seen.db，
# 这样本地跑多少次都不会造成 pull 冲突；已存在的数据目录则沿用
if not os.environ.get("RADAR_DATA_DIR"):
    os.environ["RADAR_DATA_DIR"] = str(radar.ROOT / "data_local")

_orig_load_config = radar.load_config

def load_config():
    # 优先读本地配置副本 config_local.yaml（上游更新 config.yaml 不再影响本地、不产生合并冲突）；
    # 副本不存在时回退到原逻辑读 config.yaml。LLM_MODEL 环境变量仍可临时覆盖模型名。
    local = radar.ROOT / "config_local.yaml"
    if local.exists():
        cfg = yaml.safe_load(local.read_text(encoding="utf-8"))
        cfg["events"] = yaml.safe_load(
            (radar.ROOT / "events.yaml").read_text(encoding="utf-8"))["events"]
    else:
        cfg = _orig_load_config()
    if os.environ.get("LLM_MODEL"):
        cfg["llm"]["model"] = os.environ["LLM_MODEL"]
    return cfg

radar.load_config = load_config

# ---- OpenAI 兼容协议适配（仅 LLM_PROTOCOL=openai 时启用）----
def call_llm_openai(cfg, prompt, retries=2):
    """OpenAI 兼容版 call_claude：入参与返回值语义和原函数完全一致。"""
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                radar.ANTHROPIC_URL,
                headers={
                    "Authorization": f"Bearer {os.environ['ANTHROPIC_API_KEY']}",
                    "content-type": "application/json",
                },
                json={
                    "model": cfg["llm"]["model"],
                    "max_tokens": 8192,
                    # GLM-5.3 系列强制思考、不可关闭；reasoning_effort=low 轻推理省 token，
                    # 思考内容在 reasoning_content 里，本函数只取 content，互不干扰
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "low",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=180,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\[.*\]", text, re.DOTALL)
            return json.loads(m.group(0)) if m else []
        except Exception as e:
            if attempt == retries:
                raise
            print(f"[warn] call_llm 第{attempt + 1}次失败将重试: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))

if LLM_PROTOCOL == "openai":
    radar.call_claude = call_llm_openai

# ---- Tavily 搜索适配（可选）：.env 配了 TAVILY_API_KEY 则用 Tavily 替代 Serper/SerpAPI ----
def web_search_tavily(query, tbs=None):
    """Tavily 版 web_search：入参/返回值与原函数一致（[{title,url,snippet}]）。
    Tavily 不认 site: 语法和 tbs 参数，分别映射为 include_domains 和 time_range。"""
    q, include = query, None
    m = re.search(r"site:([A-Za-z0-9.\-]+)", query)
    if m:  # site:reddit.com → include_domains，并从查询串里去掉
        include = [m.group(1).removeprefix("www.")]
        q = (query[:m.start()] + query[m.end():]).strip()
    tr = {"qdr:d": "day", "qdr:w": "week", "qdr:m": "month", "qdr:y": "year"}.get(tbs)
    body = {"query": q, "max_results": 10, "search_depth": "basic"}  # basic 档每次只算 1 个额度
    if include:
        body["include_domains"] = include
    if tr:
        body["time_range"] = tr
    r = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}",
                 "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return [{"title": w.get("title", ""), "url": w.get("url", ""),
             "snippet": (w.get("content", "") or "")[:300]}  # 截断摘要，控制评委轮 token 消耗
            for w in r.json().get("results", [])]

if os.environ.get("TAVILY_API_KEY"):
    radar.web_search = web_search_tavily
    # 原代码两处用「有没有 SERPER/SERPAPI key」当功能开关（radar.py:185、431），
    # 只配 Tavily 时塞个占位值把开关打开；真实搜索全部走上面的 Tavily 实现，
    # 不会碰 SerpAPI（原 web_search 已被整体替换）
    if not (os.environ.get("SERPER_API_KEY") or os.environ.get("SERPAPI_API_KEY")):
        os.environ["SERPAPI_API_KEY"] = "tavily-placeholder"

# ---- 修复上游 upcoming_events 的排序 bug ----
# 原版 radar.py hits.sort() 对 (days, dict) 元组排序，两个事件距今天数相同时
# 会去比较 dict 直接 TypeError 崩溃（radar.py:520）。这里只按天数排序修复。
def upcoming_events_fixed(cfg, today=None):
    today = today or datetime.now(timezone.utc).date()
    hits = []
    for ev in cfg["events"]:
        for year in (today.year, today.year + 1):
            try:
                d = datetime(year, ev["month"], ev["day"]).date()
            except ValueError:
                continue
            days = (d - today).days
            if 0 <= days <= ev["lead_weeks"] * 7:
                hits.append((days, ev))
                break
    hits.sort(key=lambda t: t[0])  # 原版 bug 修复点：只比较天数，不比较 dict
    return hits

radar.upcoming_events = upcoming_events_fixed

# ---- 本地日报加 -me 后缀，与上游 radar.py 生成的日报区分 ----
# radar.py 的报告文件名硬编码（radar.py:725），无法用环境变量覆盖，
# 所以在 main() 跑完后把当天报告重命名：2026-10-13.md → 2026-10-13-me.md
_orig_main = radar.main

def main_with_me_report():
    _orig_main()
    src = radar.ROOT / "reports" / f"{datetime.now(timezone.utc):%Y-%m-%d}.md"
    if src.exists():
        dst = src.with_name(src.stem + "-me.md")
        src.replace(dst)  # 同目录重命名，覆盖旧的 -me 报告
        print(f"本地日报已重命名 {dst}")

if __name__ == "__main__":
    main_with_me_report()