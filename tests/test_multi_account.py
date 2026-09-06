
import logging
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from selenium.common.exceptions import (
	NoSuchDriverException,
	SessionNotCreatedException,
	WebDriverException,
)

import accounts
import main
from constants import USER_DATA_DIR

REFUSED_NAMES = [
	"..", ".", "../escape", "..\\escape", "a/b", "a\\b",
	"/etc", "\\", "/", "C:", "C:\\Windows", "\\\\server\\share",
	"~", "%TEMP%", "$HOME",
	"...", "....", "personal.", "personal..",
	"a b", "a:b", "a;b", "a|b", "a*b", "a?b", "a<b",
]

def accounts_for(value):
	if value is None:
		os.environ.pop(accounts.ENV_VAR, None)
	else:
		os.environ[accounts.ENV_VAR] = value

	return accounts.configured()

class EnvironmentTestCase(unittest.TestCase):

	def setUp(self):
		self.addCleanup(os.environ.pop, accounts.ENV_VAR, None)

class TestAccountConfiguration(EnvironmentTestCase):
	def test_unset_is_the_existing_single_profile(self):
		configured = accounts_for(None)

		self.assertEqual([a.name for a in configured], ["default"])
		self.assertEqual(configured[0].user_data_dir, USER_DATA_DIR)
		self.assertTrue(configured[0].is_default)

	def test_blank_falls_back_to_the_single_profile(self):
		self.assertEqual([a.name for a in accounts_for("   ")], ["default"])

	def test_names_are_taken_in_order(self):
		self.assertEqual([a.name for a in accounts_for("personal,spare")], ["personal", "spare"])

	def test_surrounding_whitespace_and_empty_entries_are_ignored(self):
		self.assertEqual([a.name for a in accounts_for(" personal , spare ")], ["personal", "spare"])
		self.assertEqual([a.name for a in accounts_for("personal,,spare,")], ["personal", "spare"])

	def test_duplicates_collapse_case_insensitively(self):
		self.assertEqual(
			[a.name for a in accounts_for("personal,PERSONAL,spare")], ["personal", "spare"]
		)

	def test_unusable_directory_names_are_refused(self):
		for name in REFUSED_NAMES:
			with self.subTest(name=name):
				with self.assertRaises(ValueError):
					accounts_for(f"good,{name}")

	def test_a_leading_dot_is_still_usable(self):
		self.assertEqual([a.name for a in accounts_for(".hidden")], [".hidden"])

	def test_each_account_gets_its_own_directory(self):
		named = accounts_for("personal,spare")

		self.assertEqual(len({a.user_data_dir for a in named}), 2)
		self.assertEqual(len({os.path.realpath(a.user_data_dir) for a in named}), 2)

	def test_every_directory_sits_under_the_profile_directory(self):
		root = os.path.realpath(USER_DATA_DIR)

		for account in accounts_for("personal,spare"):
			with self.subTest(account=account.name):
				resolved = os.path.realpath(account.user_data_dir)

				self.assertEqual(os.path.commonpath([root, resolved]), root)
				self.assertNotEqual(resolved, root)
				self.assertFalse(account.is_default)

class TestEdgeOptions(EnvironmentTestCase):
	def test_each_account_is_handed_its_own_profile(self):
		seen = []

		for account in accounts_for("personal,spare"):
			arguments = main.build_options(account).arguments
			user_data = [a for a in arguments if a.startswith("--user-data-dir=")]
			profile = [a for a in arguments if a.startswith("--profile-directory=")]

			with self.subTest(account=account.name):
				self.assertEqual(len(user_data), 1)
				self.assertEqual(len(profile), 1)

			seen.append(user_data[0])

		self.assertEqual(len(set(seen)), 2)

class RunLoopTestCase(EnvironmentTestCase):

	def setUp(self):
		super().setUp()

		headless = main.HEADLESS
		main.HEADLESS = True
		self.addCleanup(setattr, main, "HEADLESS", headless)

		logging.disable(logging.CRITICAL)
		self.addCleanup(logging.disable, logging.NOTSET)

class TestRunLoop(RunLoopTestCase):
	def setUp(self):
		super().setUp()

		self.calls = []
		real = main.run_account
		self.addCleanup(setattr, main, "run_account", real)

	def _record(self, started):
		def run_account(account):
			self.calls.append(account.name)

			return started(account.name)

		main.run_account = run_account

	def test_a_profile_that_fails_to_start_does_not_end_the_run(self):
		accounts_for("personal,spare")
		self._record(lambda name: name != "personal")

		self.assertEqual(main.main(), 0)
		self.assertEqual(self.calls, ["personal", "spare"])

	def test_exit_code_is_one_when_no_account_ran(self):
		accounts_for("personal,spare")
		self._record(lambda name: False)

		self.assertEqual(main.main(), 1)
		self.assertEqual(self.calls, ["personal", "spare"])

	def test_unset_still_runs_the_single_profile(self):
		accounts_for(None)
		self._record(lambda name: True)

		self.assertEqual(main.main(), 0)
		self.assertEqual(self.calls, ["default"])

class TestFailureIsolation(RunLoopTestCase):

	CASES = [
		("the profile is already open", "start", SessionNotCreatedException("profile in use")),
		("the driver will not start", "start", WebDriverException("driver version mismatch")),
		("there is no driver installed", "start", NoSuchDriverException("msedgedriver not found")),
		("the profile directory is unwritable", "start", PermissionError(13, "Permission denied")),
		("the first page never loads", "connect", WebDriverException("net::ERR_NAME_NOT_RESOLVED")),
		("the browser dies mid-run", "tasks", WebDriverException("chrome not reachable")),
		("the browser will not shut down", "quit", WebDriverException("browser already gone")),
	]

	def setUp(self):
		super().setUp()

		edge, tasks = main.webdriver.Edge, main.rewards_tasks.RewardsTaskUtils
		self.addCleanup(setattr, main.webdriver, "Edge", edge)
		self.addCleanup(setattr, main.rewards_tasks, "RewardsTaskUtils", tasks)

	def _install(self, fail_at, exc, started, quit_cleanly):
		def account_of(options):
			flag = next(a for a in options.arguments if a.startswith("--user-data-dir="))

			return os.path.basename(flag.split("=", 1)[1])

		class Driver:
			def __init__(self, options):
				self.name = account_of(options)
				started.append(self.name)

				if self.name == "two" and fail_at == "start":
					raise exc

			def quit(self):
				if self.name == "two" and fail_at == "quit":
					raise exc

				quit_cleanly.append(self.name)

		class Tasks:
			def __init__(self, driver):
				self.driver = driver

				if driver.name == "two" and fail_at == "connect":
					raise exc

			def complete_all_tasks(self):
				if self.driver.name == "two" and fail_at == "tasks":
					raise exc

		main.webdriver.Edge = Driver
		main.rewards_tasks.RewardsTaskUtils = Tasks

	def test_the_remaining_accounts_still_run(self):
		for label, fail_at, exc in self.CASES:
			with self.subTest(case=label):
				started, quit_cleanly = [], []
				self._install(fail_at, exc, started, quit_cleanly)
				accounts_for("one,two,three")

				self.assertEqual(main.main(), 0)
				self.assertEqual(started, ["one", "two", "three"])

				expected = ["one", "three"] if fail_at in ("start", "quit") else ["one", "two", "three"]
				self.assertEqual(quit_cleanly, expected)

	def test_a_lone_accounts_failure_is_still_a_failing_exit_code(self):
		accounts_for(None)
		real = main.run_account
		self.addCleanup(setattr, main, "run_account", real)

		def boom(_):
			raise WebDriverException("chrome not reachable")

		main.run_account = boom

		self.assertEqual(main.main(), 1)

@unittest.skipUnless(
	os.environ.get("REWARDS_BROWSER_TESTS"),
	"starts Edge twice; set REWARDS_BROWSER_TESTS=1 to run",
)
class TestTwoRealProfiles(EnvironmentTestCase):

	def setUp(self):
		super().setUp()

		self.first, self.second = accounts_for("mat_a,mat_b")

		for account in (self.first, self.second):
			self.addCleanup(shutil.rmtree, account.user_data_dir, ignore_errors=True)

	def identity_of(self, account):
		from selenium import webdriver

		driver = webdriver.Edge(options=main.build_options(account))

		try:
			driver.get("https://www.bing.com")
			cookie = driver.get_cookie("MUID")

			return cookie["value"] if cookie else None
		finally:
			driver.quit()

	def test_two_profiles_hold_two_persistent_identities(self):
		first_id = self.identity_of(self.first)
		second_id = self.identity_of(self.second)

		self.assertIsNotNone(first_id)
		self.assertIsNotNone(second_id)
		self.assertNotEqual(first_id, second_id)

		self.assertEqual(self.identity_of(self.first), first_id)
		self.assertEqual(self.identity_of(self.second), second_id)

		for account in (self.first, self.second):
			self.assertTrue(os.path.isdir(account.user_data_dir))

		self.assertEqual(
			len({os.path.realpath(a.user_data_dir) for a in (self.first, self.second)}), 2
		)

if __name__ == "__main__":
	unittest.main()
