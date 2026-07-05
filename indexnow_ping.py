#!/usr/bin/env python3
"""Ping IndexNow (Bing/Yandex/Seznam…) with all URLs from the live sitemap.

No account needed. Requires the key file to be live at KEY_LOCATION first.
Run after deploying new pages: python3 indexnow_ping.py
"""
import json, urllib.request, re

KEY = "2ff4734efad874fcc4174fd6413f4d35"
HOST = "idsexyhomme-code.github.io"
KEY_LOCATION = f"https://{HOST}/1000/web/en/{KEY}.txt"
SITEMAP = "https://idsexyhomme-code.github.io/1000/web/en/sitemap.xml"

def urls_from_sitemap():
    xml = urllib.request.urlopen(SITEMAP, timeout=20).read().decode()
    return re.findall(r"<loc>(.*?)</loc>", xml)

def main():
    urls = urls_from_sitemap()
    payload = {"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION, "urlList": urls}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"IndexNow HTTP {r.status} — submitted {len(urls)} urls")
        print(r.read().decode() or "(empty body = accepted)")

if __name__ == "__main__":
    main()
