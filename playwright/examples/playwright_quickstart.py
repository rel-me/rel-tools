"""Port of Playwright's Python library quickstart and screenshot examples."""

from rel_playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("https://playwright.dev")

    print(page.title())
    page.screenshot(path="playwright-home.png", full_page=True)
    browser.close()
