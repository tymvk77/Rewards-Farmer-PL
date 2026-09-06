
import os
import re
from dataclasses import dataclass

from constants import USER_DATA_DIR, PROFILE_NAME

ENV_VAR = "REWARDS_ACCOUNTS"

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

RESERVED_NAMES = {".", ".."}

@dataclass(frozen=True)
class Account:

	name: str
	user_data_dir: str
	profile_name: str

	@property
	def is_default(self) -> bool:
		return self.user_data_dir == USER_DATA_DIR

def _named(name: str) -> Account:
	user_data_dir = os.path.join(USER_DATA_DIR, name)

	root = os.path.realpath(USER_DATA_DIR)
	resolved = os.path.realpath(user_data_dir)

	if os.path.commonpath([root, resolved]) != root or resolved == root:
		raise ValueError(
			f"{ENV_VAR} entry {name!r} resolves outside the profile directory"
		)

	return Account(
		name=name,
		user_data_dir=user_data_dir,
		profile_name=PROFILE_NAME,
	)

def configured() -> list[Account]:
	raw = os.environ.get(ENV_VAR, "").strip()

	if not raw:
		return [Account(name="default", user_data_dir=USER_DATA_DIR, profile_name=PROFILE_NAME)]

	names = [part.strip() for part in raw.split(",")]
	names = [name for name in names if name]

	if not names:
		return [Account(name="default", user_data_dir=USER_DATA_DIR, profile_name=PROFILE_NAME)]

	seen: set[str] = set()
	accounts: list[Account] = []

	for name in names:
		if not SAFE_NAME.match(name) or name in RESERVED_NAMES or name.endswith("."):
			raise ValueError(
				f"{ENV_VAR} entry {name!r} is not usable as a directory name; "
				"use letters, digits, dot, dash or underscore, and do not end in a dot"
			)

		if name.lower() in seen:
			continue

		seen.add(name.lower())
		accounts.append(_named(name))

	return accounts
