import requests
import time
import os
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ================= CONFIG =================

BOT_TOKEN = "8360458696:AAE2jhLfMaqf4p7bEEAsbMsSf9WhPeFasu0"
CHAT_ID = "-1003671777907"  # FIXED: removed extra quotes

BASE_URL = "https://lol49.org"

LOGO = "logo.png"
TMP = "tmp"
DELAY = 8  # increased slightly to avoid rate limits

os.makedirs(TMP, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Android 10; Mobile)",
    "Referer": BASE_URL
}

# Use public API by default
TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}/"
TG_VIDEO = TG_BASE + "sendVideo"
TG_DOC = TG_BASE + "sendDocument"

# ================= UTILS =================

def ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

FFMPEG_OK = ffmpeg_available()
print("FFmpeg:", "OK" if FFMPEG_OK else "NOT FOUND (logo & compression disabled)")

# ================= HELPERS =================

def fast_download(url, path):
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=30) as r:
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
        print("❌ FFmpeg logo failed:", result.stderr.decode())
        return False
    return os.path.exists(out)

# Optional: Compress if >50 MB (quality loss, but works on public API)
def compress_if_needed(inp, out):
    if not FFMPEG_OK:
        return inp
    size = os.path.getsize(inp)
    if size <= 50 * 1024 * 1024:
        return inp
    print("     File >50 MB → compressing to ~45 MB")
    cmd = [
        "ffmpeg", "-y",
        "-i", inp,
        "-vf", "scale=854:480",
        "-crf", "27",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "96k",
        "-fs", "48000000",  # force < ~48 MB
        out
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(out) and os.path.getsize(out) < 50*1024*1024:
        print("     Compression OK")
        return out
    print("     Compression failed → will try original (may fail)")
    return inp

def extract_video_url(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    down = soup.find("div", class_="downLink")
    if down:
        form = down.find("form")
        if form and form.get("action"):
            return urljoin(page_url, form["action"])
    for f in soup.find_all("form"):
        btn = f.find("button")
        if btn and "Download" in btn.text.strip():
            if f.get("action"):
                return urljoin(page_url, f["action"])
    return None

def send_to_telegram(path, title):
    if not os.path.exists(path):
        print("❌ File missing:", path)
        return False

    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"     File size: {size_mb:.1f} MB")

    caption = f"<b>{title}</b>"

    # Prefer video for MP4 streaming
    api = TG_VIDEO
    files = {"video": open(path, "rb")}
    data = {
        "chat_id": CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML",
        "supports_streaming": True,
        "width": 1280,   # helps Telegram detect
        "height": 720,
    }

    try:
        print("     ↑ Sending to Telegram...")
        r = requests.post(api, data=data, files=files, timeout=600)
        print("     Response:", r.text[:300])  # truncate if very long
        if r.status_code == 200 and r.json().get("ok"):
            print("     ✔ Sent successfully!")
            return True
        else:
            print(f"     ✖ Failed – status {r.status_code}")
            # Optional fallback to document
            if "too big" in r.text.lower() or "file" in r.text.lower():
                print("     Trying as document...")
                api = TG_DOC
                files = {"document": open(path, "rb")}
                data.pop("supports_streaming", None)
                data.pop("width", None)
                data.pop("height", None)
                r = requests.post(api, data=data, files=files, timeout=600)
                print("     Doc response:", r.text[:300])
                if r.status_code == 200 and r.json().get("ok"):
                    print("     ✔ Sent as document!")
                    return True
            return False
    except Exception as e:
        print("     Request error:", str(e))
        return False

# ================= MAIN =================

page = 1
print("\nBot started...\n")

while True:
    page_url = f"{BASE_URL}/" if page == 1 else f"{BASE_URL}/page/{page}/"
    print(f"→ Page {page}")

    try:
        r = requests.get(page_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("Page fetch failed:", e)
        break

    soup = BeautifulSoup(r.text, "html.parser")
    posts = soup.find_all("a", class_="title", href=True)

    if not posts:
        print("No more posts found.")
        break

    for i, post in enumerate(posts, 1):
        title = post.get_text(strip=True)
        href = post["href"]

        if urlparse(href).netloc not in ("", "lol49.org"):
            continue

        video_page = urljoin(BASE_URL, href)
        print(f"  [{i}] {title}")

        time.sleep(2.5)

        try:
            pr = requests.get(video_page, headers=HEADERS, timeout=20)
            pr.raise_for_status()
        except:
            print("     Page load failed")
            continue

        video_url = extract_video_url(pr.text, video_page)

        if not video_url:
            print("     ✖ No video link found")
            continue

        raw = os.path.join(TMP, f"raw_{page}_{i}.mp4")
        final = os.path.join(TMP, f"final_{page}_{i}.mp4")
        comp = os.path.join(TMP, f"comp_{page}_{i}.mp4")

        print("     ↓ Downloading...")
        if not fast_download(video_url, raw):
            continue

        use_file = raw

        if FFMPEG_OK and os.path.exists(LOGO):
            print("     🎨 Adding logo...")
            if add_logo_fast(raw, final):
                use_file = final

        # Compress if likely too big (optional safety)
        use_file = compress_if_needed(use_file, comp)

        print("     ↑ Sending...")
        ok = send_to_telegram(use_file, title)
        print("     Result:", "Success" if ok else "Failed")

        # Cleanup
        for f in (raw, final, comp):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

        time.sleep(DELAY)

    # Check for next page
    if f"/page/{page+1}/" not in r.text:
        print("No next page link found.")
        break

    page += 1
    time.sleep(6)

print("\nFinished. Check debug output above for failed sends.")
