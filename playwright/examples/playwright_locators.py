"""Port of Playwright's Locator.all_inner_texts example using CSS locators."""

from rel_playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("https://playwright.dev")

    for heading in page.locator("main h2").all_inner_texts():
        print(heading)

    browser.close()
