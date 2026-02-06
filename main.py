import requests
import time
import os
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ================= CONFIG =================

BOT_TOKEN = "8360458696:AAE2jhLfMaqf4p7bEEAsbMsSf9WhPeFasu0"
CHAT_ID = "'-1003671777907'"

BASE_URL = "https://lol49.org"

LOGO = "logo.png"
TMP = "tmp"
DELAY = 6

os.makedirs(TMP, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Android 10; Mobile)",
    "Referer": BASE_URL
}

TG_VIDEO = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
TG_DOC = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

# ================= UTILS =================

def ffmpeg_available():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except:
        return False


FFMPEG_OK = ffmpeg_available()
print("FFmpeg:", "OK" if FFMPEG_OK else "NOT FOUND (logo disabled)")

# ================= HELPERS =================

def fast_download(url, path):
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=20) as r:
            r.raise_for_status()
            with open(path, "wb", buffering=1024*1024) as f:
                for chunk in r.iter_content(1024*1024):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        print("❌ Download failed:", e)
        return False


def add_logo_fast(inp, out):
    if not FFMPEG_OK or not os.path.exists(LOGO):
        return False

    if not os.path.exists(inp):
        return False

    cmd = [
        "ffmpeg", "-y",
        "-i", inp,
        "-i", LOGO,
        "-filter_complex", "overlay=W-w-15:H-h-15",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "copy",
        out
    ]

    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        print("❌ FFmpeg failed, sending without logo")
        return False

    return os.path.exists(out)


def extract_video_url(html, page_url):
    soup = BeautifulSoup(html, "html.parser")

    down = soup.find("div", class_="downLink")
    if down:
        form = down.find("form")
        if form and form.get("action"):
            return urljoin(page_url, form["action"])

    for f in soup.find_all("form"):
        btn = f.find("button")
        if btn and "Download" in btn.text:
            if f.get("action"):
                return urljoin(page_url, f["action"])

    return None


def send_to_telegram(path, title):
    if not os.path.exists(path):
        print("❌ File missing:", path)
        return False

    size = os.path.getsize(path)
    caption = f"<b>{title}</b>"

    if size <= 50 * 1024 * 1024:
        api = TG_VIDEO
        files = {"video": open(path, "rb")}
        data = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
            "supports_streaming": True
        }
    else:
        api = TG_DOC
        files = {"document": open(path, "rb")}
        data = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML"
        }

    r = requests.post(api, data=data, files=files, timeout=180)
    return r.status_code == 200

# ================= MAIN =================

page = 1
print("\nBot started...\n")

while True:
    page_url = f"{BASE_URL}/" if page == 1 else f"{BASE_URL}/page/{page}/"
    print(f"→ Page {page}")

    r = requests.get(page_url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        break

    soup = BeautifulSoup(r.text, "html.parser")
    posts = soup.find_all("a", class_="title", href=True)

    if not posts:
        break

    for i, post in enumerate(posts, 1):
        title = post.get_text(strip=True)
        href = post["href"]

        if urlparse(href).netloc not in ("", "lol49.org"):
            continue

        video_page = urljoin(BASE_URL, href)
        print(f"  [{i}] {title}")

        time.sleep(2)

        pr = requests.get(video_page, headers=HEADERS, timeout=15)
        video_url = extract_video_url(pr.text, video_page)

        if not video_url:
            print("     ✖ No video link")
            continue

        raw = os.path.join(TMP, f"raw_{page}_{i}.mp4")
        final = os.path.join(TMP, f"final_{page}_{i}.mp4")

        print("     ↓ Downloading")
        if not fast_download(video_url, raw):
            continue

        use_final = raw

        if FFMPEG_OK:
            print("     🎨 Adding logo")
            if add_logo_fast(raw, final):
                use_final = final

        print("     ↑ Sending to Telegram")
        ok = send_to_telegram(use_final, title)
        print("     ✔ Sent" if ok else "     ✖ Failed")

        for f in (raw, final):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

        time.sleep(DELAY)

    if f"/page/{page+1}/" not in r.text:
        break

    page += 1
    time.sleep(5)

print("\nFinished.")
