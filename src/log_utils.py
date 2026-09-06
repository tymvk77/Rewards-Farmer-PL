
import logging
import os
import re
import sys

LEVEL_ENV_VAR = "REWARDS_FARMER_LOG_LEVEL"
FILE_ENV_VAR = "REWARDS_FARMER_LOG_FILE"

DEFAULT_LEVEL = "INFO"

NOISY_LIBRARIES = ("httpx", "httpcore", "urllib3", "selenium")

MAX_SUMMARY_LENGTH = 300

_SESSION_INFO = re.compile(r"\s*\(Session info:[^)]*\)")

def exception_summary(exc: BaseException) -> str:
	text = str(exc).strip()

	if not text:
		return ""

	text = _SESSION_INFO.sub("", text.splitlines()[0]).strip()

	if len(text) > MAX_SUMMARY_LENGTH:
		text = text[:MAX_SUMMARY_LENGTH - 3].rstrip() + "..."

	return text

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%H:%M:%S"

_configured = False

def _resolve_level(level: str | int | None) -> int:
	if level is None:
		level = os.environ.get(LEVEL_ENV_VAR, DEFAULT_LEVEL)

	if isinstance(level, int):
		return level

	resolved = logging.getLevelNamesMapping().get(str(level).strip().upper())

	if resolved is None:
		logging.getLogger(__name__).warning(
			"Unknown log level %r, falling back to %s", level, DEFAULT_LEVEL
		)

		return logging.getLevelNamesMapping()[DEFAULT_LEVEL]

	return resolved

def setup_logging(level: str | int | None = None, log_file: str | None = None) -> None:
	global _configured

	if _configured:
		return

	root = logging.getLogger()
	root.setLevel(_resolve_level(level))

	formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

	if hasattr(sys.stdout, "reconfigure"):
		sys.stdout.reconfigure(errors="replace")

	console = logging.StreamHandler(sys.stdout)
	console.setFormatter(formatter)
	root.addHandler(console)

	if log_file is None:
		log_file = os.environ.get(FILE_ENV_VAR)

	if log_file:
		file_handler = logging.FileHandler(log_file, encoding="utf-8")
		file_handler.setFormatter(formatter)
		root.addHandler(file_handler)

	for name in NOISY_LIBRARIES:
		logging.getLogger(name).setLevel(logging.WARNING)

	_configured = True
