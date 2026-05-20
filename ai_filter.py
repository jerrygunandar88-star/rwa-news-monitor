import requests
import json


def analyze_news_impact(title, description, source, url, api_key):
    prompt = f"""You are an expert analyst specializing in Real World Asset (RWA) tokenization, blockchain technology, and Indonesia nickel mining industry.

Analyze this news article and determine its impact:

TITLE: {title}
SOURCE: {source}
DESCRIPTION: {description}
URL: {url}

Evaluate based on these criteria:
1. VIRAL POTENTIAL: Could this news spread to 10,000+ people and influence their behavior?
2. REAL WORLD IMPACT: Does it involve actual tokenization of real-world assets OR Indonesia nickel mining business?
3. MARKET IMPACT: Could this significantly affect crypto markets, nickel prices, or institutional investment?
4. LEGITIMACY: Is this from a credible business/financial perspective?
5. BEHAVIORAL CHANGE: Could this change how investors, institutions, or regulators behave?

Respond ONLY in this exact JSON format with no other text outside the braces:
impact_level is HIGH or MEDIUM or LOW
summary is 2-3 sentence summary in Bahasa Indonesia
why_matters is 1-2 sentence in Bahasa Indonesia
market_impact is brief prediction in Bahasa Indonesia
is_relevant is true or false
confidence_score is 0 to 100

HIGH = Major institutional move, regulation change, billion-dollar deal
MEDIUM = Significant but not massive, new partnership, policy update
LOW = Minor news, speculation, small project"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        raw_text = data["content"][0]["text"].strip()

        if "```" in raw_text:
            parts = raw_text.split("```")
            if len(parts) > 1:
                raw_text = parts[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        raw_text = raw_text.strip()
        result = json.loads(raw_text)

        if not result.get("is_relevant", True):
            result["impact_level"] = "LOW"

        return result

    except json.JSONDecodeError as e:
        print(f"  WARNING AI JSON parse error: {e}")
        return {
            "impact_level": "LOW",
            "summary": "Could not analyze",
            "why_matters": "Analysis failed",
            "market_impact": "Unknown",
            "is_relevant": False,
            "confidence_score": 0
        }
    except Exception as e:
        print(f"  ERROR AI analysis error: {e}")
        return {
            "impact_level": "MEDIUM",
            "summary": "AI analysis unavailable. Manual review needed.",
            "why_matters": "Please check the article directly.",
            "market_impact": "Unknown — API error occurred",
            "is_relevant": True,
            "confidence_score": 0
        }