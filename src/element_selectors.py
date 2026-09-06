import re

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium import webdriver

class Labels:

	POINTS_BREAKDOWN = "podział punktów"
	READY_TO_CLAIM = "gotowe do odebrania"
	CLAIM = "odbierz"
	DAILY_SET_STREAK = "seria zestawu dziennego"
	CARD_COMPLETED = "ukończon"
	VISUAL_SEARCH_STREAK = "seria wyszukiwania wizualnego"

class ElementSelectionUtils:

	def __init__(self, driver: webdriver.Edge):
		self.driver = driver

	def resolve(self, xpath: str):
		return self.driver.find_element(By.XPATH, xpath)

	def _container_by_id(self, element_id: str) -> WebElement:
		matches = self.driver.find_elements(By.ID, element_id)

		if not matches:
			raise NoSuchElementException(f"no element with id {element_id!r}")

		for match in matches:
			try:
				if match.is_displayed() and match.find_elements(By.TAG_NAME, "a"):
					return match
			except StaleElementReferenceException:
				continue

		raise NoSuchElementException(
			f"{element_id!r} is present but no visible copy has content yet"
		)

	def _button_containing(self, needle: str, root: WebElement = None) -> WebElement:
		scope = self.driver if root is None else root
		needle = needle.lower()

		for button in scope.find_elements(By.TAG_NAME, "button"):
			try:
				if needle in (button.text or "").lower():
					return button
			except StaleElementReferenceException:
				continue

		raise NoSuchElementException(f"no button containing {needle!r}")

	def _link_containing(self, needle: str, root: WebElement = None) -> WebElement:
		scope = self.driver if root is None else root
		needle = needle.lower()

		for link in scope.find_elements(By.TAG_NAME, "a"):
			try:
				if needle in (link.text or "").lower():
					return link
			except StaleElementReferenceException:
				continue

		raise NoSuchElementException(f"no link containing {needle!r}")

	def get_earn_tab(self):
		return self.driver.find_element(By.CSS_SELECTOR, '[id$="-tab-/earn"]')

	def get_dashboard_tab(self):
		return self.driver.find_element(By.CSS_SELECTOR, '[id$="-tab-/dashboard"]')

	def get_sidebar_section(self):
		for section in self.driver.find_elements(By.TAG_NAME, "section"):
			try:
				if (section.get_dom_attribute("id") or "").startswith("react-aria"):
					return section
			except StaleElementReferenceException:
				continue

		raise NoSuchElementException("sidebar section not found")

	def _streaks_button(self, index: int) -> WebElement:
		streaks = self.driver.find_element(By.ID, "streaks")

		return streaks.find_element(By.XPATH, f"./div/div[2]/div/div/button[{index}]")

	def get_open_daily_set_button(self):
		try:
			return self._button_containing(Labels.DAILY_SET_STREAK)
		except NoSuchElementException:
			pass

		candidate = self._streaks_button(3)
		label = (candidate.text or "").strip()

		if "zestaw" not in label.lower():
			raise NoSuchElementException(
				"daily set opener not found by label, and position 3 holds "
				f"{label.splitlines()[0] if label else '<empty>'!r} instead"
			)

		return candidate

	def get_daily_set_elements(self):
		activities = []

		for link in self.get_sidebar_section().find_elements(By.TAG_NAME, "a"):
			try:
				if self._is_daily_set_activity(link.get_dom_attribute("href") or ""):
					activities.append(link)
			except StaleElementReferenceException:
				continue

		return activities

	@staticmethod
	def _is_daily_set_activity(href: str) -> bool:
		return any(
			marker in href
			for marker in ("bing.com/search", "bing.com/rewards", "rewards.bing.com/")
		)

	def get_explore_on_bing_elements(self):
		try:
			container = self._container_by_id("exploreonbing")
		except NoSuchElementException:
			return []

		return container.find_elements(By.TAG_NAME, "a")

	def get_open_visual_search_sidebar(self):
		try:
			return self._button_containing(Labels.VISUAL_SEARCH_STREAK)
		except NoSuchElementException:
			return self._streaks_button(5)

	def get_search_now_link_from_visual_search_sidebar(self):
		sidebar = self.get_sidebar_section()

		try:
			return self._link_containing("wyszukaj teraz", sidebar)
		except NoSuchElementException:
			links = sidebar.find_elements(By.TAG_NAME, "a")

			if len(links) < 2:
				raise NoSuchElementException("visual search sidebar has no usable link")

			return links[1]

	def get_visual_search_button(self):
		return self.driver.find_element(By.CSS_SELECTOR, "#sb_form > div.camera.icon")

	def get_visual_search_file_input(self):
		return self.driver.find_element(By.CSS_SELECTOR, "#sb_fileinput")

	def get_all_misc_cards(self):
		return self._container_by_id("moreactivities").find_elements(By.TAG_NAME, "a")

	def extract_card_descriptions(self, card: WebElement):
		try:
			return card.find_element(By.CSS_SELECTOR, "p:nth-child(2)").text
		except NoSuchElementException:
			paragraphs = card.find_elements(By.TAG_NAME, "p")

			return paragraphs[1].text if len(paragraphs) > 1 else (card.text or "")

	def _card_status_element(self, card: WebElement):
		return card.find_element(By.CSS_SELECTOR, "div.flex.w-full.items-center.gap-2")

	def card_is_complete(self, card: WebElement):
		try:
			status = self._card_status_element(card).text
		except NoSuchElementException:
			return False

		return Labels.CARD_COMPLETED in (status or "").lower()

	def get_card_point_value(self, card: WebElement):
		try:
			elem = self._card_status_element(card).find_element(By.TAG_NAME, "p")
		except NoSuchElementException:
			return 0

		digits = re.search(r"\d+", elem.text or "")

		return int(digits.group()) if digits else 0

	def element_is_fully_in_viewport(self, elem: WebElement) -> bool:
		js_viewport_check = """
var elem = arguments[0];
var box = elem.getBoundingClientRect();

return (
	box.top >= 0 &&
	box.left >= 0 &&
	box.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
	box.right <= (window.innerWidth || document.documentElement.clientWidth)
);
"""

		return self.driver.execute_script(js_viewport_check, elem)

	def get_points_breakdown_button(self):
		return self._button_containing(Labels.POINTS_BREAKDOWN)

	def get_close_button_on_points_breakdown(self):
		return self.get_generic_sidebar_close_button()

	def get_points_earned_from_searches_on_points_breakdown(self):
		sidebar = self.get_sidebar_section()
		text = sidebar.text or ""
		lines = [line.strip() for line in text.splitlines()]

		def parse(candidate: str):
			match = re.fullmatch(r"([\d,]+)\s*/\s*([\d,]+)", candidate)

			if not match:
				return None

			return int(match.group(1).replace(",", "")), int(match.group(2).replace(",", ""))

		for index, line in enumerate(lines):
			if "wyszukiwanie bing" in line.lower():
				for candidate in lines[index + 1:index + 3]:
					parsed = parse(candidate)

					if parsed:
						return parsed

		match = re.search(r"([\d,]+)\s*/\s*([\d,]+)", text)

		if match:
			return int(match.group(1).replace(",", "")), int(match.group(2).replace(",", ""))

		raise NoSuchElementException("no points fraction found in the breakdown sidebar")

	def get_bonus_button_on_dashboard(self):
		return self._button_containing(Labels.READY_TO_CLAIM)

	def get_claim_bonus_points_button(self):
		sidebar = self.get_sidebar_section()
		buttons = sidebar.find_elements(By.TAG_NAME, "button")

		for button in buttons:
			try:
				if (button.text or "").strip().lower() == Labels.CLAIM:
					return button
			except StaleElementReferenceException:
				continue

		for button in buttons:
			try:
				if Labels.CLAIM in (button.text or "").lower():
					return button
			except StaleElementReferenceException:
				continue

		if len(buttons) < 3:
			raise NoSuchElementException("bonus sidebar has no claim button")

		return buttons[2]

	def get_generic_sidebar_close_button(self):
		sidebar = self.get_sidebar_section()

		try:
			return sidebar.find_element(By.CSS_SELECTOR, "button[aria-label*='Zamknij']")
		except NoSuchElementException:
			buttons = sidebar.find_elements(By.TAG_NAME, "button")

			if not buttons:
				raise NoSuchElementException("sidebar has no buttons")

			return buttons[0]

	def get_bing_search_bar(self):
		return self.driver.find_element(By.TAG_NAME, "textarea")

	def get_clear_bing_search_query_button(self):
		return self.driver.find_element(By.ID, "sw_clx")
