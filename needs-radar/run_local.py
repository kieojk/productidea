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

import requests

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

if __name__ == "__main__":
    radar.main()