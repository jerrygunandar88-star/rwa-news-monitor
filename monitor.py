import os
import time
import schedule
import requests
import hashlib
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
import pytz

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
CHECK_HOURS = list(range(6, 24))

SEARCH_QUERIES = [
    "real world asset tokenization",
    "RWA crypto blockchain",
    "Indonesia nickel mining",
    "tambang nikel Indonesia"
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
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("articles", [])
    except Exception as e:
        print("NewsAPI error: " + str(e))
        return []


def send_telegram(message):
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


def run_monitor():
    if not is_check_time():
        print("Skip - luar jam operasional")
        return

    now_str = datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M WIB")
    print("Checking news at " + now_str)
    found = 0

    for query in SEARCH_QUERIES:
        print("Searching: " + query)
        articles = fetch_news(query)
        print("Found " + str(len(articles)) + " articles")

        for article in articles:
            title = article.get("title", "")
            url = article.get("url", "")
            source = article.get("source", {}).get("name", "Unknown")
            published = article.get("publishedAt", "")

            article_id = hashlib.md5((url + title).encode()).hexdigest()
            if article_id in sent_articles:
                continue

            try:
                pub_dt = dateparser.parse(published)
                pub_str = pub_dt.astimezone(JAKARTA_TZ).strftime("%d %b %Y, %H:%M WIB")
            except Exception:
                pub_str = published

            is_nickel = any(kw in query.lower() for kw in ["nickel", "nikel", "tambang"])
            category = "NICKEL MINING" if is_nickel else "RWA NEWS"

            message = (
                "*" + category + "*\n\n"
                + "*" + title + "*\n\n"
                + "Source: " + source + "\n"
                + "Published: " + pub_str + "\n\n"
                + "[Baca Selengkapnya](" + url + ")"
            )

            if send_telegram(message):
                sent_articles.add(article_id)
                found += 1
                print("Sent: " + title[:50])

            time.sleep(1)

        time.sleep(2)

    print("Done. Sent " + str(found) + " alerts.")


if __name__ == "__main__":
    print("Starting monitor...")

    missing = [v for v in ["NEWS_API_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
               if not os.environ.get(v)]
    if missing:
        print("Missing: " + str(missing))
        exit(1)

    send_telegram("Monitor is LIVE! Checking every 3 hours.")
    run_monitor()

    schedule.every(3).hours.do(run_monitor)
    print("Scheduler active...")

    while True:
        schedule.run_pending()
        time.sleep(60)