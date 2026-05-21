import os
import time
import schedule
import requests
import hashlib
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
import pytz
from ai_filter import analyze_news_impact

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
MIN_SHARES = 0
CHECK_HOURS = list(range(6, 24))

SEARCH_QUERIES = [
    "real world asset tokenization",
    "RWA crypto blockchain",
    "tokenized assets DeFi",
    "RWA crypto regulation",
    "Indonesia nickel mining",
    "hilirisasi nikel Indonesia",
    "tambang nikel Indonesia",
    "Indonesia nickel export"
]

TRUSTED_DOMAINS = [
    "coindesk.com", "cointelegraph.com", "decrypt.co",
    "theblock.co", "blockworks.co", "cryptoslate.com",
    "forbes.com", "reuters.com", "bloomberg.com",
    "ft.com", "wsj.com", "techcrunch.com",
    "messari.io", "cryptobriefing.com",
    "beincrypto.com", "cryptonews.com",
    "theguardian.com", "bbc.com", "cnbc.com",
    "kontan.co.id", "bisnis.com", "katadata.co.id",
    "cnbcindonesia.com", "detik.com", "tempo.co",
    "mining.com", "miningweekly.com", "kitco.com",
    "spglobal.com", "metalbulletin.com",
    "indonesiabusinesspost.com", "jakartaglobe.id"
]

sent_articles = set()


def is_check_time():
    now_jakarta = datetime.now(JAKARTA_TZ)
    return now_jakarta.hour in CHECK_HOURS


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
        print("NewsAPI error for " + query + ": " + str(e))
        return []


def is_from_trusted_source(article):
    url = article.get("url", "").lower()
    source = article.get("source", {}).get("name", "").lower()
    return any(domain in url or domain.split(".")[0] in source for domain in TRUSTED_DOMAINS)


def send_telegram_message(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
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
        print("Telegram error: " + str(e))
        return False


def format_alert(article, ai_analysis, query):
    title = article.get("title", "No title")
    source = article.get("source", {}).get("name", "Unknown")
    url = article.get("url", "")
    published = article.get("publishedAt", "")

    try:
        pub_dt = dateparser.parse(published)
        pub_jakarta = pub_dt.astimezone(JAKARTA_TZ)
        pub_str = pub_jakarta.strftime("%d %b %Y, %H:%M WIB")
    except Exception:
        pub_str = published

    is_nickel = any(kw in query.lower() for kw in ["nickel", "nikel", "tambang", "hilirisasi"])
    category = "NICKEL MINING" if is_nickel else "RWA NEWS"

    message = (
        "*" + category + "*\n\n"
        "*" + title + "*\n\n"
        "Source: " + source + "\n"
        "Published: " + pub_str + "\n"
        "Keyword: " + query + "\n\n"
        "Summary: " + ai_analysis.get("summary", "N/A") + "\n\n"
        "[Baca Selengkapnya](" + url + ")"
    )
    return message


def run_monitor():
    if not is_check_time():
        now_jakarta = datetime.now(JAKARTA_TZ)
        print("Skip - di luar jam operasional " + now_jakarta.strftime("%H:%M") + " WIB")
        return

    now_str = datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M WIB")
    print("Checking news at " + now_str)

    found_count = 0

    for query in SEARCH_QUERIES:
        print("Searching: " + query)
        articles = fetch_news(query)

        for article in articles:
            if not is_from_trusted_source(article):
                continue

            article_id = hashlib.md5((article.get("url", "") + article.get("title", "")).encode()).hexdigest()
            if article_id in sent_articles:
                continue

            ai_result = analyze_news_impact(
                title=article.get("title", ""),
                description=article.get("description", ""),
                source=article.get("source", {}).get("name", ""),
                url=article.get("url", ""),
                api_key=ANTHROPIC_API_KEY
            )

            message = format_alert(article, ai_result, query)
            if send_telegram_message(message):
                sent_articles.add(article_id)
                found_count += 1
                print("Alert sent: " + article.get("title", "")[:50])

            time.sleep(2)

        time.sleep(1)

    print("Done. Sent " + str(found_count) + " alert(s) this run.")


def send_startup_message():
    now_jakarta = datetime.now(JAKARTA_TZ)
    message = (
        "RWA and Nickel News Monitor is LIVE!\n\n"
        "Started: " + now_jakarta.strftime("%d %b %Y, %H:%M WIB") + "\n"
        "Keywords: " + str(len(SEARCH_QUERIES)) + "\n"
        "Active hours: 06:00 - 23:00 WIB\n"
        "Check interval: every 3 hours\n\n"
        "Bot siap monitoring!"
    )
    send_telegram_message(message)
    print("Startup message sent!")


if __name__ == "__main__":
    print("Starting RWA and Nickel News Monitor...")

    missing = [v for v in ["NEWS_API_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "ANTHROPIC_API_KEY"]
               if not os.environ.get(v)]
    if missing:
        print("Missing env vars: " + str(missing))
        exit(1)

    send_startup_message()
    run_monitor()

    schedule.every(3).hours.do(run_monitor)
    print("Scheduler active - checking every 3 hours (06:00-23:00 WIB)...")

    while True:
        schedule.run_pending()
        time.sleep(60)