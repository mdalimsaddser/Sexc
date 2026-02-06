import requests
import time
import os
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ================= CONFIG =================

BOT_TOKEN = "8360458696:AAE2jhLfMaqf4p7bEEAsbMsSf9WhPeFasu0"
CHAT_ID = "-1003671777907"

SITES = [
    {"base": "https://lol49.org", "name": "Lol49"},
    {"base": "https://maal69.com.co", "name": "Maal69"},
    {"base": "https://mmsbaba.com", "name": "MMSBaba"},
    {"base": "https://spicymms.com", "name": "SpicyMMS"},
    {"base": "https://mydesi.net", "name": "MyDesi"},
    {"base": "https://aagmaal.farm", "name": "Aagmaal"},
    # আরও যোগ করতে পারো যদি test করে working পাও
]

LOGO = "logo.png"
TMP = "tmp"
DELAY = 12  # anti-ban

os.makedirs(TMP, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Android 10; Mobile; rv:68.0) Gecko/68.0 Firefox/68.0",
    "Referer": "https://www.google.com/"
}

TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}/"
TG_VIDEO = TG_BASE + "sendVideo"
TG_PHOTO = TG_BASE + "sendPhoto"
TG_DOC = TG_BASE + "sendDocument"

# ================= UTILS =================

def ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

FFMPEG_OK = ffmpeg_available()
print("FFmpeg:", "OK" if FFMPEG_OK else "NOT FOUND (logo disabled)")

# ================= HELPERS =================

def fast_download(url, path):
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=45) as r:
            r.raise_for_status()
            with open(path, "wb", buffering=1024*1024) as f:
                for chunk in r.iter_content(1024*1024):
                    f.write(chunk)
        return True
    except Exception as e:
        print("❌ Download fail:", e)
        return False

def add_logo_fast(inp, out):
    if not FFMPEG_OK or not os.path.exists(LOGO):
        return False
    cmd = [
        "ffmpeg", "-y", "-i", inp, "-i", LOGO,
        "-filter_complex", "overlay=W-w-15:H-h-15",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "copy", out
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and os.path.exists(out)

def extract_content(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    video_urls = []
    pic_urls = []

    # Video extract (improved)
    for form in soup.find_all("form", action=True):
        action = form.get("action")
        if action and ("download" in action.lower() or "mp4" in action.lower()):
            video_urls.append(urljoin(page_url, action))

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".mp4" in href.lower() or "download" in href.lower() or "video" in href.lower():
            video_urls.append(urljoin(page_url, href))

    # Pics extract (gallery/images)
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if src.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and len(src) > 20:
            full_src = urljoin(page_url, src)
            if "thumb" not in full_src and "logo" not in full_src:  # avoid small thumbs
                pic_urls.append(full_src)

    return list(set(video_urls))[:3], list(set(pic_urls))[:5]  # limit to avoid spam

def send_to_telegram_video(path, title, site_name):
    if not os.path.exists(path):
        return False
    size_mb = os.path.getsize(path) / (1024**2)
    print(f"     Video size: {size_mb:.1f} MB")
    caption = f"<b>{title}</b>\nFrom: {site_name}"
    try:
        files = {"video": open(path, "rb")}
        data = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML", "supports_streaming": True}
        r = requests.post(TG_VIDEO, data=data, files=files, timeout=600)
        if r.status_code == 200 and r.json().get("ok"):
            print("     ✔ Video sent!")
            return True
        print("     Video fail:", r.text[:150])
        # fallback doc
        files = {"document": open(path, "rb")}
        r = requests.post(TG_DOC, data=data, files=files, timeout=600)
        if r.status_code == 200 and r.json().get("ok"):
            print("     ✔ Sent as doc")
            return True
        return False
    except Exception as e:
        print("     Send error:", e)
        return False

def send_pics(pic_urls, title, site_name):
    caption = f"<b>Pics from: {title}</b>\n{site_name}"
    for pic in pic_urls[:3]:  # limit
        try:
            files = {"photo": requests.get(pic, timeout=20).content}
            data = {"chat_id": CHAT_ID, "caption": caption if pic == pic_urls[0] else "", "parse_mode": "HTML"}
            r = requests.post(TG_PHOTO, data=data, files=files, timeout=60)
            if r.status_code == 200:
                print("     ✔ Pic sent")
            time.sleep(3)
        except:
            pass

# ================= MAIN =================

print("\n=== Best Desi MMS + Pics Scraper Bot - Feb 2026 ===\n")

for site in SITES:
    base = site["base"]
    name = site["name"]
    print(f"\n=== {name} ({base}) ===")
    
    page = 1
    while page <= 4:  # limit per site
        page_url = f"{base}/" if page == 1 else f"{base}/page/{page}/"
        print(f"  Page {page}")
        
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print("  Error:", e)
            break
        
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.find_all("a", class_="title", href=True)
        if not posts:
            posts = soup.find_all("a", href=True)  # fallback
        
        for i, post in enumerate(posts[:8], 1):
            title = post.get_text(strip=True) or "Untitled"
            href = post.get("href", "")
            if not href:
                continue
            video_page = urljoin(base, href)
            print(f"    [{i}] {title[:50]}...")
            
            time.sleep(4)
            
            try:
                pr = requests.get(video_page, headers=HEADERS, timeout=30)
                video_urls, pic_urls = extract_content(pr.text, video_page)
            except:
                continue
            
            if video_urls:
                for v_url in video_urls:
                    raw = os.path.join(TMP, f"raw_{name}_{page}_{i}.mp4")
                    final = os.path.join(TMP, f"final_{name}_{page}_{i}.mp4")
                    print("      ↓ Video DL...")
                    if fast_download(v_url, raw):
                        use = raw
                        if FFMPEG_OK and os.path.exists(LOGO):
                            if add_logo_fast(raw, final):
                                use = final
                        print("      ↑ Sending video...")
                        send_to_telegram_video(use, title, name)
                        for f in [raw, final]:
                            if os.path.exists(f): os.remove(f)
            
            if pic_urls:
                print("      ↑ Sending pics...")
                send_pics(pic_urls, title, name)
            
            time.sleep(DELAY)
        
        page += 1
        time.sleep(10)

print("\nFinished. Check Telegram channel!")
