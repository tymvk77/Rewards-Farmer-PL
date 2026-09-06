import logging
import log_utils
import os
import random
import time
from typing import Callable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
import tab_utils
import queries
import mouse_trajectory
import mimic_typing
import element_selectors

VISUAL_SEARCH_IMAGE_PATH = os.path.abspath("visual_search.jpg")

logger = logging.getLogger(__name__)

class RewardsTaskUtils:
	def __init__(self, driver: webdriver.Edge):
		self.driver = driver

		self.driver.get("https://rewards.bing.com/")

		self.tab_utils = tab_utils.TabUtils(driver)
		self.tab_utils.ensure_focus()

		self.mouse = mouse_trajectory.MouseUtils(driver)
		self.keyboard = mimic_typing.KeyboardUtils(driver)
		self.elements = element_selectors.ElementSelectionUtils(driver)

	def find_element(self, xpath: str):
		return self.driver.find_element(By.XPATH, xpath)

	def wait_for_element(self, element_getter: Callable[[], WebElement | list[WebElement]], timeout: int = 10) -> WebElement | list[WebElement]:
		def condition(_: webdriver.Edge):
			try:
				element_or_elements = element_getter()

				return element_or_elements
			except:
				return False

		return WebDriverWait(self.driver, timeout).until(condition)

	def switch_to_earn_page(self):
		self.move_to_and_click(self.elements.get_earn_tab())

	def switch_to_dashboard(self):
		self.move_to_and_click(self.elements.get_dashboard_tab())

	def move_to_and_click(self, elem: WebElement):
		self.mouse.move_to_element(elem)
		self.mouse.human_like_click()

	def wait_for_then_click(self, element_getter: Callable[[], WebElement], timeout: int = 10):
		elem = self.wait_for_element(element_getter, timeout)
		self.move_to_and_click(elem)

	def complete_bing_daily_set(self, expected_activities: int = 3):
		self.switch_to_earn_page()

		self.wait_for_then_click(self.elements.get_open_daily_set_button)

		def full_activity_list():
			activities = self.elements.get_daily_set_elements()

			return activities if len(activities) >= expected_activities else False

		try:
			daily_set_links = self.wait_for_element(full_activity_list, timeout=30)
		except TimeoutException:
			daily_set_links = self.elements.get_daily_set_elements()

			logger.warning(
				"Daily set panel only shows %s of %s activities",
				len(daily_set_links), expected_activities
			)

		for index in range(len(daily_set_links)):
			activities = self.elements.get_daily_set_elements()

			if index >= len(activities):
				break

			self.move_to_and_click(activities[index])
			time.sleep(random.uniform(2, 3))
			self.driver.switch_to.window(self.driver.current_window_handle)

		self.tab_utils.close_all_other_tabs()

	def complete_explore_on_bing_tasks(self):
		self.switch_to_earn_page()

		explore_on_bing_links = self.elements.get_explore_on_bing_elements()

		if not explore_on_bing_links:
			raise NoSuchElementException("no Explore on Bing section in this UI variant")

		for card in explore_on_bing_links:
			desc = self.elements.extract_card_descriptions(card)
			query = queries.search_query_for_task(desc)

			self.move_to_and_click(card)
			self.tab_utils.switch_to_other_tab()

			self.wait_for_element(self.elements.get_bing_search_bar)

			self.keyboard.send_keys(f"{query} -noai{Keys.ENTER}")

			time.sleep(random.uniform(2, 3))

			self.tab_utils.switch_to_other_tab()
			self.tab_utils.close_all_other_tabs()

		time.sleep(random.uniform(1, 2))

		for card in explore_on_bing_links:
			if not self.elements.card_is_complete(card):
				logger.warning(
					"Explore on Bing Card [desc=%r] is not complete after searching. Please check manually.",
					self.elements.extract_card_descriptions(card)
				)

	def complete_visual_search(self):
		self.switch_to_earn_page()

		self.wait_for_then_click(self.elements.get_open_visual_search_sidebar)

		self.wait_for_then_click(self.elements.get_search_now_link_from_visual_search_sidebar)

		self.tab_utils.switch_to_other_tab()

		self.wait_for_then_click(self.elements.get_visual_search_button)

		file_input = self.wait_for_element(self.elements.get_visual_search_file_input)

		file_input.send_keys(VISUAL_SEARCH_IMAGE_PATH)

		time.sleep(random.uniform(3, 5))

		self.tab_utils.switch_to_other_tab()
		self.tab_utils.close_all_other_tabs()

	def complete_misc_cards(self):
		self.switch_to_earn_page()

		misc_cards: list[WebElement] = self.wait_for_element(self.elements.get_all_misc_cards)

		for card in misc_cards:
			self.mouse.wheel_scroll_element_into_view(card)

			if not self.elements.card_is_complete(card) and self.elements.get_card_point_value(card) > 0:
				self.move_to_and_click(card)
				time.sleep(random.uniform(1, 2))
				self.driver.switch_to.window(self.driver.current_window_handle)

		for card in misc_cards:
			if not self.elements.card_is_complete(card) and self.elements.get_card_point_value(card) > 0:
				logger.warning(
					"Misc Card [desc=%r] is not complete after clicking. Please check manually.",
					self.elements.extract_card_descriptions(card)
				)

		self.tab_utils.close_all_other_tabs()

		self.mouse.wheel_scroll_to_top()

	def complete_required_searches(self, max_rounds: int = 6):
		points_earned, max_pts = self.read_search_points()

		logger.info("Search points before: %s/%s", points_earned, max_pts)

		for round_number in range(1, max_rounds + 1):
			if points_earned >= max_pts:
				break

			searches = max(1, (max_pts - points_earned) // 3)

			self.run_search_batch(searches)

			previous = points_earned
			points_earned, max_pts = self.read_search_points()

			logger.info(
				"Round %s: %s searches -> %s/%s",
				round_number, searches, points_earned, max_pts
			)

			if points_earned <= previous:
				logger.warning("Round produced no points, stopping instead of searching pointlessly.")
				break

		if points_earned < max_pts:
			logger.warning("Search quota not filled: %s/%s", points_earned, max_pts)
		else:
			logger.info("Search quota complete: %s/%s", points_earned, max_pts)

	def read_search_points(self):
		self.switch_to_earn_page()

		self.wait_for_then_click(self.elements.get_points_breakdown_button, timeout=30)

		points_earned, max_pts = self.wait_for_element(
			self.elements.get_points_earned_from_searches_on_points_breakdown,
			timeout=30
		)

		try:
			self.move_to_and_click(self.elements.get_generic_sidebar_close_button())
		except Exception:
			pass

		return points_earned, max_pts

	def run_search_batch(self, count: int):
		self.driver.get("https://www.bing.com/")
		self.tab_utils.ensure_focus()

		self.wait_for_element(self.elements.get_bing_search_bar)

		for i, query in enumerate(
			queries.related_queries(count)
		):
			self.keyboard.send_keys(f"{query} -noai{Keys.ENTER}")

			time.sleep(random.uniform(0.5, 1))

			try: self.wait_for_then_click(self.elements.get_clear_bing_search_query_button)
			except StaleElementReferenceException:
				logger.warning(
					"StaleElementReferenceException when trying to click the clear button for query %s. Trying again...",
					i + 1
				)
				self.wait_for_then_click(self.elements.get_clear_bing_search_query_button)

		self.driver.get("https://rewards.bing.com/")
		self.tab_utils.ensure_focus()

	def claim_bonus_points(self):
		self.switch_to_dashboard()

		self.wait_for_then_click(self.elements.get_bonus_button_on_dashboard)

		try:
			self.wait_for_then_click(self.elements.get_claim_bonus_points_button)
		except TimeoutException:
			logger.warning("Could not find the 'Claim Bonus Points' button. There are likely no bonus points to claim at this time.")

	def complete_all_tasks(self):
		steps = (
			("Bing daily set", self.complete_bing_daily_set),
			("Explore on Bing", self.complete_explore_on_bing_tasks),
			("Visual search", self.complete_visual_search),
			("Misc cards", self.complete_misc_cards),
			("Required searches", self.complete_required_searches),
			("Bonus points", self.claim_bonus_points),
		)

		for name, step in steps:
			try:
				step()
				logger.info("[OK] %s", name)
			except (NoSuchElementException, TimeoutException) as exc:
				logger.warning("[SKIP] %s: not available in this UI variant (%s)", name, type(exc).__name__)
			except Exception as exc:
				logger.error(
					"[FAIL] %s: %s: %s", name, type(exc).__name__, log_utils.exception_summary(exc),
					exc_info=logger.isEnabledFor(logging.DEBUG)
				)

			try:
				self.tab_utils.close_all_other_tabs()
			except Exception:
				pass