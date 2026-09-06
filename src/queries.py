
import logging
import os

import query_sources

logger = logging.getLogger(__name__)

LLM = "llm"
TRENDS = "trends"

DEFAULT_SOURCE = LLM

ENV_VAR = "QUERY_SOURCE"

def selected_source() -> str:
	choice = os.environ.get(ENV_VAR, DEFAULT_SOURCE).strip().lower()

	return choice if choice in (LLM, TRENDS) else DEFAULT_SOURCE

def search_query_for_task(task_description: str) -> str:
	if selected_source() == TRENDS:
		query = query_sources.query_from_task_description(task_description)

		if query:
			return query

		logger.warning("No query source reachable, using the lowercased task description.")

		return task_description.lower()

	import llm_utils

	return llm_utils.get_search_query_from_task_description(task_description)

def related_queries(count: int):
	if selected_source() == TRENDS:
		queries = query_sources.related_queries(count)

		if queries:
			return queries

		logger.warning("No query source reachable, falling back to the wordlist.")

		return query_sources.wordlist_queries(count)

	import llm_utils

	return llm_utils.get_related_search_queries(llm_utils.get_random_noun(), num_queries=count)
