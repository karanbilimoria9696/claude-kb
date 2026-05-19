import json
import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an expert assistant helping SaaS salespeople in Australia and New Zealand (ANZ) stay informed about IT and technology news relevant to their accounts.

For each news article, you will produce a structured JSON analysis that helps salespeople:
1. Quickly understand what happened
2. Identify which companies are involved
3. Spot the sales opportunity
4. Know which SaaS categories are relevant
5. Have 2–3 sharp talking points to open a conversation

Keep language concise, practical, and sales-ready. Avoid jargon for jargon's sake. Think like a senior AE preparing a 5-minute brief for their team."""

ARTICLE_PROMPT = """Analyse this IT/SaaS news article for ANZ salespeople and return a JSON object with exactly these keys:

- "company": the primary company or companies in the news (string, e.g. "Woolworths Group" or "Telstra, Ericsson")
- "summary": a 2–3 sentence plain-English summary of what happened and why it matters (string)
- "sales_opportunity": 2–3 sentences explaining what this signals for a SaaS salesperson — what pain point, budget signal, or transformation initiative does this reveal? Be specific and actionable. (string)
- "saas_categories": comma-separated list of relevant SaaS categories a salesperson might position (e.g. "Cloud infrastructure, Cybersecurity, ITSM") (string)
- "talking_points": a JSON array of exactly 2–3 short, punchy strings a salesperson could use to start a conversation or email about this news. Each should be one sentence, framed as a question or insight. (array of strings)

Return only valid JSON. No markdown fences, no extra text.

Article title: {title}
Source: {source}
Content: {content}"""


def process_article(article: dict) -> dict | None:
    """Call Claude to enrich a raw article. Returns enriched dict or None on failure."""
    prompt = ARTICLE_PROMPT.format(
        title=article["title"],
        source=article["source"],
        content=article["summary"][:3000],
    )

    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1024,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        text = next(
            (b.text for b in response.content if b.type == "text"),
            None,
        )
        if not text:
            return None

        data = json.loads(text.strip())

        # Validate required keys
        required = {"company", "summary", "sales_opportunity", "saas_categories", "talking_points"}
        if not required.issubset(data.keys()):
            return None

        # Normalise talking_points to a JSON string for storage
        talking_points = data["talking_points"]
        if isinstance(talking_points, list):
            talking_points = json.dumps(talking_points)

        return {
            "title": article["title"],
            "source": article["source"],
            "original_url": article["url"],
            "company": data["company"],
            "summary": data["summary"],
            "sales_opportunity": data["sales_opportunity"],
            "saas_categories": data["saas_categories"],
            "talking_points": talking_points,
        }

    except json.JSONDecodeError as e:
        print(f"[ai_processor] JSON parse error for '{article['title']}': {e}")
        return None
    except Exception as e:
        print(f"[ai_processor] Error processing '{article['title']}': {e}")
        return None


def process_articles(articles: list[dict]) -> list[dict]:
    enriched = []
    for article in articles:
        result = process_article(article)
        if result:
            enriched.append(result)
            print(f"[ai_processor] Processed: {article['title'][:60]}")
        else:
            print(f"[ai_processor] Skipped: {article['title'][:60]}")
    return enriched
