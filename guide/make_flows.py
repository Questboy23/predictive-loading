"""Writes flows.json for the setup guide. Every pasted value comes from
docs/STORE_LISTING.md or from the files the installer placed in SUPPORT_DIR.
Usage: python3 guide/make_flows.py SUPPORT_DIR"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUP = sys.argv[1]
EXT = os.path.join(SUP, "extension")
ZIP = os.path.join(SUP, "predictive-loading-extension.zip")
STORE = os.path.join(SUP, "store")

# Parse "- Key: value" items; indented lines continue the previous item.
items, key = {}, None
for line in open(os.path.join(ROOT, "docs", "STORE_LISTING.md")).read().splitlines()[2:]:
    if line.startswith("- ") and ":" in line:
        key, val = line[2:].split(":", 1)
        items[key.strip()] = val.strip()
    elif key and line.startswith("  "):
        items[key] += ("\n" if items[key] else "") + line.strip()
    elif key and not line.strip():
        items[key] += "\n"
desc = items["Detailed description"].strip()
desc = "\n\n".join(p.strip() for p in desc.split("\n\n") if p.strip())


def step(title, text, copy=None, target=None, done_when=None, done_unless=None, show_when=None, auto=None, click_right_of=None):
    s = {"title": title, "text": text}
    if copy:
        s["copy"] = copy
    if target:
        s["target"] = target
    if done_when:
        s["doneWhen"] = done_when
    if done_unless:
        s["doneUnless"] = done_unless
    if show_when:
        s["showWhen"] = show_when
    if auto:
        s["auto"] = auto
    if click_right_of is not None:
        s["clickRightOf"] = click_right_of
    return s


GOTO = "Click Open this folder for me (by hand: click the file window, press Command+Shift+G, Command+V, Return; not the Search box)."
chrome = [
    step("Open Chrome's Extensions page", "The installer opened it in Chrome. If you don't see it, click Chrome's address bar, paste this and press Return.",
         "chrome://extensions", done_when=["Developer mode"]),
    step("Turn on Developer mode", "Click the Developer mode switch at the top right of the Extensions page.",
         target=["Developer mode"], done_when=["Load unpacked"], auto=["click"], click_right_of=28),
    step("Click Load unpacked", "Click the Load unpacked button at the top left. A file window opens.",
         target=["Load unpacked"], done_when=["Select the extension directory"], auto=["click"]),
    step("Pick the extension folder", "Click Open this folder for me. (By hand: click the file window, press Command+Shift+G, then Command+V, then Return. Do not type in the Search box.) The extension folder opens. Do not go into icons. Then click Select.",
         EXT, target=["Select"], show_when=["Select the extension directory"], auto=["clickText:Select the extension directory", "goto", "click"]),
    step("Done", "Predictive Loading is installed and on. Browse normally: it learns which page you open next on each site. Click its icon to see time saved, turn it off, or delete all data. Nothing leaves this Mac.",
         show_when=["Predictive Loading", "Developer mode"]),
]

store = [
    step("Open the developer dashboard", "Chrome is opening the Chrome Web Store developer dashboard. If it isn't open, paste this into the address bar. Sign in with your Google account (you type your own password).",
         "https://chrome.google.com/webstore/devconsole", done_when=["Items"]),
    step("Pay the one-time $5 fee (only if asked)", "Google asks new developers for a one-time $5 registration fee. Pay it on Google's page yourself, then click Next here. Skip if it doesn't ask."),
    step("Click New item", "Click the New item button.", target=["New item", "Add new item"], done_when=["Browse"]),
    step("Click Browse files", "Click Browse files. A file window opens.", target=["Browse files", "Browse"], done_when=["Cancel"]),
    step("Pick the extension zip", GOTO + " Then click Upload (or Open). The path is below.", ZIP, target=["Go to"]),
    step("Description", "Click inside the Description box, then press Paste it for me (or Copy, then Command+V).", desc, target=["Description"]),
    step("Category", "Open the Category menu and choose Productivity.", target=["Category"]),
    step("Language", "Open the Language menu and choose English.", target=["Language"]),
    step("Store icon", "Under Store icon click Select image (or the upload box). Then in the file window: " + GOTO,
         os.path.join(STORE, "icon-128.png"), target=["Store icon"]),
    step("Screenshot", "Scroll to Screenshots and click the upload box. Then in the file window: " + GOTO,
         os.path.join(STORE, "screenshot-1280x800.png"), target=["Screenshots"]),
    step("Small promo tile", "Scroll to Small promo tile and click the upload box. Then in the file window: " + GOTO,
         os.path.join(STORE, "promo-440x280.png"), target=["Small promo tile", "promo tile"]),
    step("Homepage URL", "Click the Homepage URL box and paste.", items["Homepage URL"], target=["Homepage URL"]),
    step("Support URL", "Click the Support URL box and paste.", items["Support URL"], target=["Support URL"]),
    step("Save the listing", "Click Save draft at the top right.", target=["Save draft"]),
    step("Open the Privacy tab", "Click Privacy in the left menu.", target=["Privacy"], done_when=["Single purpose"]),
    step("Single purpose", "Click the Single purpose description box and paste.", items["Single purpose"], target=["Single purpose"]),
    step("storage justification", "Click the box under storage justification and paste.", items["Permission justification, `storage`"], target=["storage justification", "Storage justification"]),
    step("Host permission justification", "If a Host permission justification box is shown, click it and paste. Otherwise click Next.",
         "Content script on http/https pages reads the current page path, finds same-site links and adds a Speculation Rules script. No page data leaves the device.",
         target=["Host permission justification", "host permission"]),
    step("Remote code", "Choose: No, I am not using remote code.", target=["remote code"]),
    step("Data usage", "Leave every data type unchecked (nothing is collected). Tick all three certification boxes at the bottom: no selling or transferring, no unrelated use, no creditworthiness use.",
         target=["I do not sell", "certify"]),
    step("Privacy policy URL", "Click the Privacy policy URL box and paste.", items["Privacy policy URL"], target=["Privacy policy"]),
    step("Save the privacy page", "Click Save draft at the top right.", target=["Save draft"]),
    step("Keep it private", "Click Distribution in the left menu. Under Visibility choose Private, so only you (trusted testers) can see it. It is not public.",
         target=["Private", "Visibility"]),
    step("Add yourself as a tester", "Click Account in the left menu. Under Trusted testers, type the Google account you use in Chrome. Click Save changes.",
         target=["Trusted testers", "testers"]),
    step("Submit for review", "Go back to the item and click Submit for review, then confirm. Google reviews it (often 1 to 3 days). It stays private.",
         target=["Submit for review"]),
    step("Done", "Submitted. The daily check (9:08 AM) adds the store link to the site and README once Google approves it."),
]

mac = [
    step("Open Terminal", "Open the Terminal app (Command+Space, type Terminal, Return)."),
    step("Turn on the Mac tool", "In Terminal, click Paste it for me (or Copy, then Command+V) and press Return. macOS asks for your Mac password once: type it in that box.",
         "predictive-loading enable"),
    step("Check it", "Paste this in Terminal and press Return. It shows ms saved per day once there is enough data (a day or so).", "predictive-loading stats"),
    step("Done", "To undo everything later: predictive-loading uninstall (restores DNS exactly and deletes all data)."),
]

out = os.path.join(SUP, "flows.json")
json.dump({"flows": {"chrome": chrome, "store": store, "mac": mac}}, open(out, "w"), indent=1)
print(out)
