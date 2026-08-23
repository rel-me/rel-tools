"""Port of Playwright's Pages and Actions examples against REL's fixture."""

from rel_playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(profile="Direct")
    page = browser.new_page()
    page.goto("https://rel.me/browser-actions")

    page.locator("#disco_search").fill("Magickraft")
    page.locator("#submit_button").click()
    print(page.locator("#submission_status").inner_text())

    browser.close()
