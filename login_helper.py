"""
One-time login helper for the auto-apply automation browser.

Job platforms like LinkedIn, Internshala, and Naukri require you to be signed in
before you can apply. This script opens the SAME persistent browser profile that
autofill_applier.py uses (./playwright_user_data), so any account you log into
here stays logged in for every future auto-apply run — you only do this once.

The automation cannot (and will not) enter your passwords for you. You sign in
yourself in the window that opens, then come back to this terminal and press Enter.

Usage:
    python login_helper.py
"""
import os
import sys
from playwright.sync_api import sync_playwright

# Pages to open for sign-in. Add/remove as you like.
LOGIN_TABS = [
    ("LinkedIn",    "https://www.linkedin.com/login"),
    ("Internshala", "https://internshala.com/login/student"),
    ("Naukri",      "https://www.naukri.com/nlogin/login"),
]


def main():
    user_data_dir = os.path.abspath("./playwright_user_data")
    print("=" * 64)
    print(" AUTO-APPLY LOGIN HELPER")
    print("=" * 64)
    print(" A browser window will open with sign-in tabs for:")
    for name, _ in LOGIN_TABS:
        print(f"   - {name}")
    print()
    print(" 1. Sign in to each platform you want to auto-apply on.")
    print(" 2. Solve any OTP / CAPTCHA yourself (these are normal).")
    print(" 3. Leave them logged in — the session is saved to this profile.")
    print(" 4. Come back here and press ENTER to finish.")
    print("=" * 64)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            viewport=None,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
            ignore_default_args=["--enable-automation"],
        )
        context.add_init_script(
            "const np = navigator.__proto__; delete np.webdriver; navigator.__proto__ = np;"
        )

        # Reuse the first existing page, open new tabs for the rest.
        for idx, (name, url) in enumerate(LOGIN_TABS):
            try:
                page = context.pages[0] if (idx == 0 and context.pages) else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                print(f"  Opened {name} -> {url}")
            except Exception as e:
                print(f"  Could not open {name}: {e}")

        print()
        try:
            input(" >>> When you've finished signing in, press ENTER here to save & close... ")
        except (EOFError, KeyboardInterrupt):
            pass

        print(" Saving session and closing browser...")
        try:
            context.close()
        except Exception:
            pass
        print(" Done. Your logins are saved. Auto-apply will now reuse them.")


if __name__ == "__main__":
    main()
