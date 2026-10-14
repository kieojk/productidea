取决于这个“第三方 API”是**透传 Google 官方 Gemini API**，还是只兼容 Gemini 的聊天接口。核心是：在请求体中显式加入 `tools: [{"google_search": {}}]`；若第三方没有透传 `tools` 字段或未开通搜索计费，就无法启用。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)

## 1. 先确认第三方类型

| 第三方接口类型 | 能否启用 Google Search | 判断方法 |
|---|---|---|
| 官方 API 反代 / 透传 | 通常可以 | 请求地址、请求体结构与 `generativelanguage.googleapis.com` 一致，支持 `tools` |
| OpenAI-compatible 网关 | 不一定 | 需看它是否把 `tools` 里的 Gemini 原生工具透传给 Google |
| 自建中转 / 修改过协议 | 通常不行 | 文档没有 `google_search`、`groundingMetadata` 支持说明 |
| 第三方已封装“联网模型” | 可以，但用法不同 | 可能提供 `gemini-xxx-search` 之类模型名，或独立 `web_search` 参数 |

官方 `generateContent` 的启用字段是 `tools: [{"google_search": {}}]`，模型会自动决定是否搜索、生成查询、处理结果并返回引用。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)

## 2. 直接请求示例

假设第三方只是把官方域名替换成自己的 Base URL，例如：

```text
https://your-third-party.com/v1beta/models/gemini-2.5-flash:generateContent
```

则可以这样请求：

```bash
curl "https://your-third-party.com/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "Authorization: Bearer $THIRD_PARTY_API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{
    "contents": [
      {
        "parts": [
          { "text": "搜索并总结 2026 年最新的 Gemini API 价格变化，附来源链接" }
        ]
      }
    ],
    "tools": [
      { "google_search": {} }
    ]
  }'
```

如果第三方要求 `x-goog-api-key` 头，则把鉴权头换成：

```bash
-H "x-goog-api-key: $THIRD_PARTY_API_KEY"
```

官方 REST 格式正是使用 `"tools": [{"google_search": {}}]`；旧模型可能使用 `google_search_retrieval`，当前模型应使用 `google_search`。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)

## 3. 返回里如何拿到搜索结果

成功后，响应的 `candidates[0]` 中除了回答文本，还会有 `groundingMetadata`：

```json
{
  "candidates": [
    {
      "content": {
        "parts": [{ "text": "模型基于搜索结果生成的回答..." }]
      },
      "groundingMetadata": {
        "webSearchQueries": ["Gemini API pricing 2026"],
        "groundingChunks": [
          {
            "web": {
              "uri": "https://example.com/source",
              "title": "Example Source"
            }
          }
        ],
        "groundingSupports": [
          {
            "segment": {
              "startIndex": 0,
              "endIndex": 80,
              "text": "回答中的某段文字"
            },
            "groundingChunkIndices": [0]
          }
        ]
      }
    }
  ]
}
```

你可以提取：

- `webSearchQueries`：模型实际执行的搜索词。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)
- `groundingChunks`：搜索来源网页的 `uri` 和 `title`。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)
- `groundingSupports`：将回答中的文本片段与来源索引关联，用于渲染“点击式引用”。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)

Python 提取来源示例：

```python
import requests

url = "https://your-third-party.com/v1beta/models/gemini-2.5-flash:generateContent"

payload = {
    "contents": [{"parts": [{"text": "搜索并总结最新的 Gemini API 定价"}]}],
    "tools": [{"google_search": {}}]
}

r = requests.post(url, json=payload, headers={
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
})
r.raise_for_status()
data = r.json()

candidate = data["candidates"][0]
answer = candidate["content"]["parts"][0]["text"]

meta = candidate.get("groundingMetadata", {})
queries = meta.get("webSearchQueries", [])
sources = [
    chunk["web"]
    for chunk in meta.get("groundingChunks", [])
    if "web" in chunk
]

print(answer)
print("搜索词：", queries)
print("来源：", sources)
```

## 4. 如果第三方不透传 tools

常见报错或现象包括：

- 返回 `tools` 字段被忽略；
- 报 `Tool use with function calling is not supported`；
- 响应中没有 `groundingMetadata`；
- 第三方文档只提供 `/v1/chat/completions`，且只接受 OpenAI 风格的 `tools`。

这时你有三种可行方案：

1. **问服务商是否支持原生 `google_search` 透传**，并要求提供可用的 Base URL、模型名和请求示例。
2. **改用官方 Gemini API**，自己持有 Google API Key；这是最可靠、能拿到完整 `groundingMetadata` 的方式。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)
3. **自己做搜索增强**：先用 Serper、Tavily、Bing、Brave 等搜索 API 获取结果，把标题、URL、摘要放入 prompt，再交给任意 Gemini 兼容接口生成回答。这样不依赖第三方是否支持 Google grounding。

## 5. 成本注意

Google 官方对 Gemini 3 及更新模型的 Search Grounding 按**模型实际执行的搜索查询次数**计费：每月共享 5,000 次免费搜索请求，之后为 $14 / 1,000 次搜索；一次用户提问若触发多个查询，会计为多次计费。Gemini 2.5 及更早模型则按 prompt 计费。 [ai.google](https://ai.google.dev/gemini-api/docs/generate-content/google-search)

因此如果你的第三方是“按 token 转售”的官方反代，最好先确认：**搜索费用是包含在 token 价格里，还是额外按 Google 官方规则向你的账户/服务商计费**。