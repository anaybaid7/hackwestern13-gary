#!/usr/bin/env python3
"""Dress Auth0's login page as Gary's: his colours, his face, his words.

    auth0 login                                             once
    python3 backend/deploy/auth0_look.py https://your-page-address

Auth0 hosts the sign-in page (Universal Login), so it is styled through the
tenant, not through our code: a name, a logo, a theme and the page's text.
The logo is /gary.png on the page address given. Safe to run again.
"""
import json
import shutil
import subprocess
import sys

A0 = shutil.which("auth0") or "/opt/homebrew/bin/auth0"
SITE = (sys.argv[1] if len(sys.argv) > 1 else "").rstrip("/")
if not SITE.startswith("https://"):
    sys.exit("usage: auth0_look.py https://your-page-address")
LOGO = SITE + "/gary.png"
INK, CREAM, PAPER, LIME, CORAL, ORANGE = "#14202b", "#fff4da", "#fffaf0", "#c8f56b", "#ff5a47", "#ff9f43"


def api(method, path, body=None):
    cmd = [A0, "api", method, path]
    if body is not None:
        cmd += ["--data", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(out.stdout) if out.stdout.strip() else {}
    except ValueError:
        data = {"raw": out.stdout[:200]}
    bad = out.returncode != 0 or (isinstance(data, dict) and (data.get("statusCode", 200) >= 400 or "error" in data))
    return (not bad), data if not bad else (data if data else out.stderr.strip()[:200])


def step(name, ok, detail=""):
    print("%-34s %s" % (name, "done" if ok else "FAILED: %s" % str(detail)[:160]))
    return ok


THEME = {
    "displayName": "Pocket Pixel",
    "colors": {
        "primary_button": CORAL, "primary_button_label": INK,
        "secondary_button_border": INK, "secondary_button_label": INK,
        "base_focus_color": ORANGE, "base_hover_color": INK, "links_focused_components": INK,
        "header": INK, "body_text": INK, "widget_background": CREAM, "widget_border": INK,
        "input_labels_placeholders": "#3d4d5c", "input_filled_text": INK, "input_border": INK,
        "input_background": PAPER, "icons": INK, "error": "#b3261e", "success": "#2e7d32",
    },
    "fonts": {
        "font_url": "", "reference_text_size": 16,
        "title": {"bold": True, "size": 150}, "subtitle": {"bold": False, "size": 87.5},
        "body_text": {"bold": False, "size": 87.5}, "buttons_text": {"bold": True, "size": 100},
        "input_labels": {"bold": False, "size": 100}, "links": {"bold": True, "size": 87.5},
        "links_style": "underlined",
    },
    "borders": {
        "button_border_weight": 3, "buttons_style": "sharp", "button_border_radius": 1,
        "input_border_weight": 3, "inputs_style": "sharp", "input_border_radius": 1,
        "widget_corner_radius": 0, "widget_border_weight": 4, "show_widget_shadow": True,
    },
    "widget": {"logo_position": "center", "logo_url": LOGO, "logo_height": 96,
               "header_text_alignment": "center", "social_buttons_layout": "bottom"},
    "page_background": {"page_layout": "center", "background_color": LIME, "background_image_url": ""},
}

TEXT = {
    "login": {"login": {
        "pageTitle": "Sign in | G.A.R.Y the Goat",
        "title": "Baa! Welcome back",
        "description": "Sign in to walk with Gary. He keeps a goat name for you, never your own.",
        "buttonText": "Let's go",
        "footerText": "New to the herd?",
        "signupActionLinkText": "Join it",
    }},
    "signup": {"signup": {
        "pageTitle": "Join the herd | G.A.R.Y the Goat",
        "title": "Join the herd",
        "description": "One account, so your check-ins stay yours and your Gary knows you.",
        "buttonText": "Let's go",
        "loginActionText": "Already in the herd?",
        "loginActionLinkText": "Sign in",
    }},
    "device-flow": {
        "device-code-activation": {
            "pageTitle": "Pair your Gary",
            "title": "Pair your Gary",
            "description": "Enter the code Gary is showing.",
            "buttonText": "Continue",
        },
        "device-code-confirmation": {
            "pageTitle": "Pair your Gary",
            "title": "Is this Gary's code?",
            "description": "Check it matches the code Gary is showing, then confirm.",
        },
    },
}

ok, tenant = api("patch", "tenants/settings", {"friendly_name": "G.A.R.Y the Goat", "picture_url": LOGO})
step("tenant name and picture", ok, tenant)
ok, out = api("patch", "branding", {"logo_url": LOGO, "colors": {"primary": CORAL, "page_background": LIME}})
step("logo and colours", ok, out)
found, theme = api("get", "branding/themes/default")
if found and theme.get("themeId"):
    ok, out = api("patch", "branding/themes/" + theme["themeId"], THEME)
else:
    ok, out = api("post", "branding/themes", THEME)
step("theme (Pocket Pixel)", ok, out)
for prompt, words in TEXT.items():
    ok, out = api("put", "prompts/%s/custom-text/en" % prompt, words)
    step("words: " + prompt, ok, out)
print("Look at it: sign out on the page, then Sign in.")
