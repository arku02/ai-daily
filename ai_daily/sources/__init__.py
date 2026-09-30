from . import github, hf, hn, rss

# 順序即跨來源合併時的優先順序（R4）
SOURCES = {
    "github_trending": github.fetch_trending,
    "github_search": github.fetch_search,
    "hf_models": hf.fetch_models,
    "hf_papers": hf.fetch_papers,
    "hn": hn.fetch,
    "rss": rss.fetch,
}
