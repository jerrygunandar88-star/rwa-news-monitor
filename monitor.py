import os
import time
import schedule
import requests
import hashlib
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
import pytz
from ai_filter import analyze_news_impact

# ============================================================
# KONFIGURASI
# ============================================================
NEWS_API_KEY      = os.environ.get("NEWS_API_KEY")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

JAKARTA_TZ  = pytz.timezone("Asia/Jakarta")
MIN_SHARES  = 0
CHECK_HOURS = list(range(6, 24))


TRUSTED_DOMAINS = [
    "coindesk.com", "cointelegraph.com", "decrypt.co",
    "theblock.co", "blockworks.co", "cryptoslate.com",
    "forbes.com", "reuters.com", "bloomberg.com",
    "ft.com", "wsj.com", "techcrunch.com",
    "defipulse.com", "messari.io", "cryptobriefing.com",
    "beincrypto.com", "cryptonews.com", "ambcrypto.com",
    "theguardian.com", "bbc.com", "cnbc.com",
    # Media Indonesia
    "kontan.co.id", "bisnis.com", "katadata.co.id",
    "cnbcindonesia.com", "detik.com", "tempo.co",
    "mining.com", "miningweekly.com", "kitco.com",
    "spglobal.com", "metalbulletin.com", "argusmedia.com",
    "theassay.com", "mining-technology.com",
    "indonesiabusinesspost.com", "jakartaglobe.id"
]

sent_articles = set()


def is_check_time():
    now_jakarta = datetime.now(JAKARTA_TZ)
    return now_jakarta.hour in CHECK_HOURS


def fetch_news(query):
   def fetch_news(query):
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": yesterday,
        "language": "en",
        "sortBy": "popularity",
        "pageSize": 10,
        "apiKey": NEWS_API_KEY
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("articles", [])
    except Exception as e:
        print(f"  NewsAPI error for '{query}': {e}")
        return []

SEARCH_QUERIES = [
    # RWA
    "real world asset tokenization",
    "RWA crypto blockchain",
    "tokenized assets DeFi",
    "RWA crypto regulation",

    # Nikel Indonesia
    "Indonesia nickel mining",
    "hilirisasi nikel Indonesia",
    "tambang nikel Indonesia",
    "Indonesia nickel export"
]

edelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": yesterday,
        "language": "en",
        "sortBy": "popularity",
        "pageSize": 10,
        "apiKey": NEWS_API_KEY
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("articles", [])
    except Exception as e:
        print(f"  ❌ NewsAPI error for '{query}': {e}")
        return []


def estimate_virality(article):
    score = 0
    source_name = article.get("source", {}).get("name", "").lower()
    title = (article.get("title") or "").lower()
    description = (article.get("description") or "").lower()
    content = title + " " + description

    tier1 = ["bloomberg", "reuters", "wsj", "ft.com", "cnbc", "forbes", "bbc"]
    tier2 = ["coindesk", "cointelegraph", "decrypt", "theblock", "blockworks"]

    if any(t in source_name for t in tier1):
        score += 8000
    elif any(t in source_name for t in tier2):
        score += 5000
    else:
        score += 1000

    high_impact_keywords = [
        "billion", "trillion", "sec approved", "regulation passed",
        "major bank", "institutional", "blackrock", "fidelity",
        "jp morgan", "goldman", "government", "law", "breakthrough",
        "launches", "partnership", "acquisition", "tokenize",
        "nikel", "nickel", "hilirisasi", "smelter", "ekspor", "tambang"
    ]
    for kw in high_impact_keywords:
        if kw in content:
            score += 1500

    try:
        pub_time = dateparser.parse(article.get("publishedAt", ""))
        if pub_time:
            hours_ago = (datetime.now(timezone.utc) - pub_time.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if hours_ago < 3:
                score += 3000
            elif hours_ago < 6:
                score += 2000
            elif hours_ago < 12:
                score += 1000
    except Exception:
        pass

    return score


def is_from_trusted_source(article):
    url = article.get("url", "").lower()
    source = article.get("source", {}).get("name", "").lower()
    return any(domain in url or domain.split(".")[0] in source for domain in TRUSTED_DOMAINS)


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  ❌ Telegram error: {e}")
        return False


def format_alert(article, ai_analysis, virality_score, query):
    title       = article.get("title", "No title")
    source      = article.get("source", {}).get("name", "Unknown")
    url         = article.get("url", "")
    published   = article.get("publishedAt", "")

    try:
        pub_dt = dateparser.parse(published)
        pub_jakarta = pub_dt.astimezone(JAKARTA_TZ)
        pub_str = pub_jakarta.strftime("%d %b %Y, %H:%M WIB")
    except Exception:
        pub_str = published

    virality_label = "🔥🔥🔥 EXTREMELY VIRAL" if virality_score >= 15000 else \
                     "🔥🔥 VIRAL" if virality_score >= 10000 else \
                     "🔥 TRENDING"

    impact_emoji = {"HIGH": "🚨", "MEDIUM": "⚠️", "LOW": "ℹ️"}.get(
        ai_analysis.get("impact_level", "LOW"), "ℹ️"
    )

    # Deteksi kategori berita
    is_nickel = any(kw in query.lower() for kw in ["nickel", "nikel", "tambang", "mining", "hilirisasi"])
    category = "⛏️ NICKEL MINING ALERT" if is_nickel else "🏦 RWA NEWS ALERT"

    message = (
        f"{impact_emoji} *{category}* {impact_emoji}\n"
        f"{'─' * 30}\n\n"
        f"📰 *{title}*\n\n"
        f"📊 Status: {virality_label}\n"
        f"🏢 Source: {source}\n"
        f"📅 Published: {pub_str}\n"
        f"🔍 Keyword: `{query}`\n\n"
        f"🤖 *AI Analysis:*\n"
        f"{ai_analysis.get('summary', 'N/A')}\n\n"
        f"💡 *Why it matters:*\n"
        f"{ai_analysis.get('why_matters', 'N/A')}\n\n"
        f"📈 *Impact:* {ai_analysis.get('market_impact', 'N/A')}\n\n"
        f"🔗 [Baca Selengkapnya]({url})"
    )
    return message


def run_monitor():
    if not is_check_time():
        now_jakarta = datetime.now(JAKARTA_TZ)
        print(f"⏸ Skip — di luar jam operasional ({now_jakarta.strftime('%H:%M')} WIB)")
        return

    now_str = datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M WIB")
    print(f"\n{'='*50}")
    print(f"🔍 Checking news at {now_str}")
    print(f"{'='*50}")

    found_count = 0
    all_candidates = []

    for query in SEARCH_QUERIES:
        print(f"\n📡 Searching: '{query}'")
        articles = fetch_news(query)

        for article in articles:
            if not is_from_trusted_source(article):
                continue

            article_id = hashlib.md5((article.get("url", "") + article.get("title", "")).encode()).hexdigest()
            if article_id in sent_articles:
                continue

            virality_score = estimate_virality(article)
            title = article.get("title", "")[:60]
            print(f"  📄 {title}... | Score: {virality_score:,}")

            if virality_score >= MIN_SHARES:
                all_candidates.append({
                    "article": article,
                    "article_id": article_id,
                    "virality_score": virality_score,
                    "query": query
                })

        time.sleep(1)

    all_candidates.sort(key=lambda x: x["virality_score"], reverse=True)

    print(f"\n🤖 AI analyzing {len(all_candidates)} candidate(s)...")
    for candidate in all_candidates[:5]:
        article        = candidate["article"]
        article_id     = candidate["article_id"]
        virality_score = candidate["virality_score"]
        query          = candidate["query"]

        ai_result = analyze_news_impact(
            title=article.get("title", ""),
            description=article.get("description", ""),
            source=article.get("source", {}).get("name", ""),
            url=article.get("url", ""),
            api_key=ANTHROPIC_API_KEY
        )

        if ai_result.get("impact_level") in ["HIGH", "MEDIUM", "LOW"]:
            message = format_alert(article, ai_result, virality_score, query)
            if send_telegram_message(message):
                sent_articles.add(article_id)
                found_count += 1
                print(f"  ✅ Alert sent! Impact: {ai_result.get('impact_level')}")
        else:
            print(f"  ⏭ Skipped (AI says LOW impact)")
            sent_articles.add(article_id)

        time.sleep(2)

    print(f"\n✅ Done. Sent {found_count} alert(s) this run.")


def send_startup_message():
    now_jakarta = datetime.now(JAKARTA_TZ)
    message = (
        "🟢 *RWA & Nickel News Monitor is LIVE!*\n\n"
        f"⏰ Started at: {now_jakarta.strftime('%d %b %Y, %H:%M WIB')}\n"
        f"📡 Monitoring {len(SEARCH_QUERIES)} keywords\n"
        f"🔥 Viral threshold: {MIN_SHARES:,} estimated reach\n"
        f"⏰ Active hours: 06:00 - 23:00 WIB\n"
        f"🔄 Check interval: every 1 hour\n"
        f"🤖 AI Filter: Enabled (Claude)\n\n"
        "📋 *Kategori:*\n"
        "🏦 RWA Tokenization\n"
        "⛏️ Tambang Nikel Indonesia\n\n"
        "✅ Bot siap monitoring!"
    )
    send_telegram_message(message)
    print("✅ Startup message sent!")


if __name__ == "__main__":
    print("🚀 Starting RWA & Nickel News Monitor...")

    missing = [v for v in ["NEWS_API_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "ANTHROPIC_API_KEY"]
               if not os.environ.get(v)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}")
        exit(1)

    send_startup_message()
    run_monitor()

    schedule.every(3).hours.do(run_monitor)
    print("\n⏰ Scheduler active — checking every hour (06:00-23:00 WIB)...")

    while True:
        schedule.run_pending()
        time.sleep(60)