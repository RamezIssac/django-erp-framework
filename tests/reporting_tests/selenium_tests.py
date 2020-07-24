
# from django.contrib.staticfiles.testing import StaticLiveServerTestCase
# from selenium.webdriver.firefox.webdriver import WebDriver
#
# class MySeleniumTests(StaticLiveServerTestCase):
#     fixtures = ['user-data.json']
#
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#         cls.selenium = WebDriver()
#         cls.selenium.implicitly_wait(10)
#
#     @classmethod
#     def tearDownClass(cls):
#         cls.selenium.quit()
#         super().tearDownClass()
#
#
#     def test_total_footer_creation_on_crosstab(self):
#         self.selenium.get('%s%s' % (self.live_server_url, reverse('/login/'))
