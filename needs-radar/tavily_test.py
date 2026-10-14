
#!/usr/bin/env python3
"""Tavily 搜索模拟脚本：打印 Tavily 实际发出的查询与结果，供手工上 Google 对照验证。
/home/jk/productidea/needs-radar/tavily_test.py
用途1（间接搜 Reddit）：site:reddit.com + config_local.yaml 句式，限一周（同 radar.py:185）
用途2（竞品核查）：任意产品关键词直接搜，无站点/时间限制（同 radar.py:431 competitor_scan）

用法（先加载 .env 再运行，与 run_local.py 相同）：
  cd needs-radar
  set -a && source ./.env && set +a
  .venv/bin/python tavily_test.py                      # 用途1，默认取前3个句式
  .venv/bin/python tavily_test.py "habit tracker app"  # 用途2，竞品核查
"""
import os
import sys
from urllib.parse import quote_plus

import yaml

import radar  # 只为拿 ROOT 路径（import run_local 时它已被加载，无额外开销）
from run_local import web_search_tavily

def show(tag, query, results):
    # 打印一次搜索的查询串、Google 对照链接和结果列表
    print(f"\n{'=' * 60}")
    print(f"[{tag}] query: {query}")
    print(f"[google check] https://www.google.com/search?q={quote_plus(query)}")
    if not results:
        print("(no results)")
        return
    for i, h in enumerate(results, 1):
        print(f"{i}. {h['title']}")
        print(f"   {h['url']}")
        print(f"   {h['snippet'][:120]}")

def reddit_line(limit=3):
    # 用途1：与 radar.py 句式搜索同款输入 —— site: 由适配函数映射为 include_domains，限一周
    cfg = yaml.safe_load((radar.ROOT / "config_local.yaml").read_text(encoding="utf-8"))
    for q in cfg["search_queries"][:limit]:
        full = f"site:reddit.com {q}"
        show("reddit", full, web_search_tavily(full, tbs="qdr:w"))

def competitor_line(query):
    # 用途2：与 competitor_scan 同款 —— 关键词原样查询
    show("competitor", query, web_search_tavily(query))

if __name__ == "__main__":
    if not os.environ.get("TAVILY_API_KEY"):
        sys.exit("[error] TAVILY_API_KEY not set, run: set -a && source ./.env && set +a")
    if len(sys.argv) > 1:
        competitor_line(" ".join(sys.argv[1:]))
    else:
        reddit_line()