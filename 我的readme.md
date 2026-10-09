
git remote add upstream https://github.com/shenjiayi692-maker/productidea.git
git remote -v
git fetch upstream
git pull upstream main

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