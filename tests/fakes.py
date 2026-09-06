
from selenium.common.exceptions import NoSuchElementException

class FakeElement:
	def __init__(self, text="", attributes=None, children=None, displayed=True):
		self.text = text
		self.attributes = attributes or {}
		self.children = children or {}
		self.displayed = displayed

	def get_dom_attribute(self, name):
		return self.attributes.get(name)

	def is_displayed(self):
		return self.displayed

	def find_elements(self, by, selector):
		return list(self.children.get((by, selector), []))

	def find_element(self, by, selector):
		found = self.find_elements(by, selector)

		if not found:
			raise NoSuchElementException(f"no element for {by} {selector!r}")

		return found[0]

class FakeDriver(FakeElement):

	def __init__(self, children=None):
		super().__init__(children=children)
