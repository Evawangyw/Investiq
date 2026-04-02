import requests
import re

HEADERS = {"User-Agent": "InvestIQ research@investiq.com", "Accept": "application/json"}

base = "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000230/"

# 直접 試 主文档的可能文件名
candidates = [
    "nvda-20251026.htm",
    "nvda20261027.htm", 
    "nv10q2026q3.htm",
]

for name in candidates:
    url = base + name
    r = requests.get(url, headers=HEADERS)
    print(name + " -> " + str(r.status_code))

# 同时看完整提交文件里有哪些 htm 文件名
txt_url = base + "0001045810-25-000230.txt"
r2 = requests.get(txt_url, headers=HEADERS)
# 找所有 htm 文件名
htm_names = re.findall(r'<FILENAME>([^\n]+\.htm)', r2.text[:50000])
print("\n完整提交文件中的 htm 文件名:")
for n in htm_names:
    print("  " + n.strip())