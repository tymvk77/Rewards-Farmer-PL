
import json
import random
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

TRENDS_URL = "https://trends.google.com/trending/rss?geo={geo}"
WIKIPEDIA_URL = "https://en.wikipedia.org/api/rest_v1/feed/featured/{y}/{m:02d}/{d:02d}"
AUTOSUGGEST_URL = "https://api.bing.com/osjson.aspx?query={query}"

USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 15

INSTRUCTION_WORDS = {
	"search", "searching", "bing", "on", "to", "the", "a", "an", "for", "your",
	"you", "use", "using", "find", "get", "with", "and", "or", "of", "in",
	"at", "by", "now", "today", "this", "that", "these", "those", "learn",
	"discover", "explore", "check", "see", "our", "more", "about", "how",
}

def _fetch(url: str) -> str | None:
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

	try:
		with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
			return response.read().decode("utf-8", "replace")
	except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
		return None

def trending_queries(geo: str = "US") -> list[str]:
	body = _fetch(TRENDS_URL.format(geo=urllib.parse.quote(geo)))

	if not body:
		return []

	titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", body, re.S)

	return [_clean(t) for t in titles[1:] if _clean(t)]

def wikipedia_topics(days_ago: int = 1) -> list[str]:
	day = date.today() - timedelta(days=days_ago)
	body = _fetch(WIKIPEDIA_URL.format(y=day.year, m=day.month, d=day.day))

	if not body:
		return []

	try:
		payload = json.loads(body)
	except json.JSONDecodeError:
		return []

	articles = payload.get("mostread", {}).get("articles", [])
	titles = [a.get("titles", {}).get("normalized", "") for a in articles]

	skipped = ("Main Page", "Special:", "Wikipedia:", "Portal:")

	return [
		_clean(t) for t in titles
		if t and not t.startswith(skipped) and _clean(t)
	]

def suggestions(seed: str) -> list[str]:
	if not seed.strip():
		return []

	body = _fetch(AUTOSUGGEST_URL.format(query=urllib.parse.quote(seed)))

	if not body:
		return []

	try:
		payload = json.loads(body)
	except json.JSONDecodeError:
		return []

	if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
		return []

	return [_clean(s) for s in payload[1] if _clean(s)]

def wordlist_queries(count: int) -> list[str]:
	try:
		with open("nouns.txt", encoding="utf-8") as handle:
			nouns = [line.strip().lower() for line in handle if len(line.strip()) >= 3]
	except OSError:
		return []

	if not nouns:
		return []

	return random.sample(nouns, min(count, len(nouns)))

def _clean(text: str) -> str:
	text = re.sub(r"<[^>]+>", " ", text or "")
	text = re.sub(r"[\"'?!,;:]", " ", text)

	return " ".join(text.split()).strip().lower()

def query_from_task_description(description: str) -> str | None:
	words = [w for w in _clean(description).split() if w not in INSTRUCTION_WORDS]

	if not words:
		return None

	seed = " ".join(words[:6])
	options = suggestions(seed)

	return options[0] if options else seed

def related_queries(count: int, seed: str | None = None) -> list[str]:
	collected: list[str] = []
	seen: set[str] = set()

	def take(candidates):
		for candidate in candidates:
			if candidate and candidate not in seen and len(candidate) > 2:
				seen.add(candidate)
				collected.append(candidate)

				if len(collected) >= count:
					return True
		return False

	if seed:
		take(suggestions(seed))

	if len(collected) < count and take(trending_queries()):
		return collected[:count]

	if len(collected) < count:
		take(wikipedia_topics())

	for term in list(collected):
		if len(collected) >= count:
			break

		take(suggestions(term))

	return collected[:count]
