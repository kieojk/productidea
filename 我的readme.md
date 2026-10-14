```
git remote add upstream https://github.com/shenjiayi692-maker/productidea.git
git remote set-url upstream git@github.com:shenjiayi692-maker/productidea.git
git remote -v
git fetch upstream
git pull upstream main
```

## 每次拉取上游更新，完整命令如下（按顺序执行）：
`cd ~/productidea`

### 1. 拉取上游并合并（--no-edit 避免弹编辑器，--no-rebase 用 merge 模式）
`git pull --no-rebase --no-edit upstream main`

### 2. 如果提示 seen.db 冲突，取上游版本（你的记录已在 data_local/seen.db）
```
git checkout --theirs needs-radar/data/seen.db
git add needs-radar/data/seen.db
git commit --no-edit
```

### 3. 同步到你的 fork
`git push origin main`


如何测试网络环境是否连通外网

curl -sI -m 10 "https://trends.google.com/trending/rss?geo=US" | head -1
HTTP/2 200 

curl -s -m 10 -A "web:needs-radar:v0.1 (personal research aggregator)" \
  "https://www.reddit.com/r/renting/top.rss?t=day" \
  -o /dev/null -w "HTTP %{http_code}, %{size_download} bytes\n"
HTTP 200, 8775 bytes


User asks: where in run_local.py do the two uses map? Answer: both uses call radar.web_search — the replacement point is L111-112 (radar.web_search = web_search_tavily). The Tavily adapter L85-109 serves both; the gate-opening L111-117 enables both call sites in radar.py. The two "uses" live in radar.py (L185 phrase search, L431 competitor scan), run_local.py only replaces the shared function. Concise.
两个用途在 `run_local.py` 里**共用同一段代码**——因为它替换的是底层搜索函数，上层谁调用它，谁就走 Tavily。对应关系如下：

## run_local.py 里的位置

| 位置 | 作用 |
|---|---|
| [L84-109](file:///home/jk/productidea/needs-radar/run_local.py#L84-L109) | Tavily 适配函数 `web_search_tavily` 本体（两个用途**共用**这一份实现） |
| [L111-112](file:///home/jk/productidea/needs-radar/run_local.py#L111-L112) | `radar.web_search = web_search_tavily` —— **替换发生的地方**，radar.py 里所有搜索调用从此改道 Tavily |
| [L113-117](file:///home/jk/productidea/needs-radar/run_local.py#L113-L117) | 打开 radar.py 里两道功能开关（一句对应用途 1，一句对应用途 2） |

## 两个用途的“调用点”其实在 radar.py

`run_local.py` 只负责替换函数本体，真正的两个用途发起于 radar.py 内部：

| 用途 | radar.py 调用点 | 走到 run_local 的哪段 |
|---|---|---|
| 句式搜索（间接搜 Reddit） | [radar.py:185](file:///home/jk/productidea/needs-radar/radar.py#L185) 的开关 + 内部调 `web_search("site:reddit.com \"句式\"")` | 开关靠 [L116-117](file:///home/jk/productidea/needs-radar/run_local.py#L116-L117) 打开，搜索走 [L85-109](file:///home/jk/productidea/needs-radar/run_local.py#L85-L109)（`site:` 在 [L89-92](file:///home/jk/productidea/needs-radar/run_local.py#L89-L92) 被翻译成 `include_domains`） |
| 竞品核查 | [radar.py:431](file:///home/jk/productidea/needs-radar/radar.py#L431) 的开关 + `competitor_scan` 内部调 `web_search(卡片关键词)` | 开关同样靠 [L116-117](file:///home/jk/productidea/needs-radar/run_local.py#L116-L117)，搜索走同一段适配函数（这次没有 `site:`，不带 `include_domains`） |

一句话记忆：**`run_local.py` 只改“搜索怎么发”（L84-117），不改“搜索用来干嘛”（那两处逻辑在 radar.py 里，一行没动）。** 以后上游改了用途逻辑（比如核查策略升级），你的启动器照常生效；上游改了 `web_search` 函数签名，才需要回来调适配函数。


## 如何运行
cd needs-radar/
set -a && source ./.env && set +a && .venv/bin/python run_local.py --dry-run


后台那个网络冒烟测试已确认停掉了（本来也不需要它，真实连通性你自己测即可）。代码层面的工作此前已全部完成：`run_local.py` 里 Gemini google_search 接口已就位，优先级 Gemini > Tavily，上游 `radar.py` 未动，配套的 `gemini_search_test.py`、`.env` 注释说明和 `config_local.yaml` 注释也都已更新。

等你在 `.env` 里填上 `GEMINI_API_KEY`（需要 Bearer 鉴权的话再设 `GEMINI_AUTH=bearer`，反代就设 `GEMINI_BASE_URL`），然后运行：

```bash
cd needs-radar
set -a && source ./.env && set +a
.venv/bin/python gemini_search_test.py "habit tracker app"
```

测试中有任何问题（比如第三方不透传 `tools` 导致返回空列表并打 warn）随时反馈。