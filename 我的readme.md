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


如何运行
cd needs-radar/
set -a && source ./.env && set +a && .venv/bin/python run_local.py --dry-run