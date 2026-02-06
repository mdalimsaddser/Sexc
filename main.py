import requests
import time
import os
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ================= CONFIG =================

BOT_TOKEN = "8360458696:AAE2jhLfMaqf4p7bEEAsbMsSf9WhPeFasu0"
CHAT_ID = "-1003671777907"

SITES = [
    {"base": "https://viralkand.com", "name": "ViralKand"},  # MMS Videos + pics
    {"base": "https://www.viralhub.co.in", "name": "ViralHub"},  # Viral Desi MMS + images
    {"base": "https://kamatv.in", "name": "KamaTV"},  # Active Desi
    {"base": "https://aagmaal.farm", "name": "Aagmaal"},  # Porn + gallery pics
    # যদি fsiblog চেক করো: {"base": "https://fsiblog5.com", "name": "FSIBlog5"},
]

TMP = "tmp"
DELAY = 15  # anti-ban

os.makedirs(TMP, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.google.com/"
}

TG_VIDEO = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
TG_PHOTO = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
TG_DOC = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

# ================= HELPERS =================

def fast_download(url, path):
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"DL fail: {url} -> {e}")
        return False

def extract_video_and_pics(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    video_urls = []
    pic_urls = []

    # Videos: mp4, download links, forms
    for tag in soup.find_all(['a', 'source', 'video', 'form']):
        link = tag.get('href') or tag.get('src') or tag.get('action')
        if link:
            full = urljoin(base_url, link)
            if ".mp4" in full.lower() or "download" in full.lower() or "video" in full.lower():
                video_urls.append(full)

    # Pics: img src (gallery/thumbs, avoid small logos)
    for img in soup.find_all("img", src=True):
        src = img["src"]
        full_src = urljoin(base_url, src)
        if full_src.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and "logo" not in full_src and "thumb" not in full_src.lower():
            pic_urls.append(full_src)

    video_urls = list(set(video_urls))[:2]  # max 2 videos per post
    pic_urls = list(set(pic_urls))[:4]     # max 4 pics per post
    return video_urls, pic_urls

def send_video(path, title, site_name):
    if not os.path.exists(path):
        return False
    size_mb = os.path.getsize(path) / (1024**2)
    print(f"Video size: {size_mb:.1f} MB")
    caption = f"<b>{title}</b>\nFrom: {site_name}"
    api = TG_VIDEO if size_mb <= 50 else TG_DOC
    key = "video" if api == TG_VIDEO else "document"
    data = {
        "chat_id": CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }
    if api == TG_VIDEO:
        data["supports_streaming"] = True
    try:
        with open(path, "rb") as f:
            files = {key: f}
            r = requests.post(api, data=data, files=files, timeout=900)
        print(f"Video response: {r.status_code} - {r.text[:150]}")
        return r.status_code == 200 and r.json().get("ok", False)
    except Exception as e:
        print(f"Video send error: {e}")
        return False

def send_pics(pic_urls, title, site_name):
    caption = f"<b>Pics: {title}</b>\nFrom: {site_name} (separate pics)"
    for idx, pic in enumerate(pic_urls):
        try:
            img_data = requests.get(pic, timeout=30).content
            files = {"photo": img_data}
            data = {
                "chat_id": CHAT_ID,
                "caption": caption if idx == 0 else "",
                "parse_mode": "HTML"
            }
            r = requests.post(TG_PHOTO, data=data, files=files, timeout=60)
            if r.status_code == 200:
                print(f"Pic {idx+1} sent")
            time.sleep(4)  # avoid flood
        except Exception as e:
            print(f"Pic send fail: {e}")

# ================= MAIN =================

print("Bot started - Video + Separate Pics mode (2026 updated sites)")

for site in SITES:
    base = site["base"]
    name = site["name"]
    print(f"\n=== Processing {name} ({base}) ===")
    
    for page in range(1, 4):  # 3 pages per site to test
        page_url = f"{base}/" if page == 1 else f"{base}/page/{page}/"
        print(f"Page {page}")
        
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"Page fail: {e}")
            continue
        
        soup = BeautifulSoup(r.text, "html.parser")
        posts = soup.find_all("a", href=True)
        
        for post in posts[:8]:  # limit per page
            title = post.get_text(strip=True)
            if not title or len(title) < 15:
                continue
            href = post["href"]
            if not href or "#" in href:
                continue
            full_page = urljoin(base, href)
            print(f"  - {title[:60]}...")
            
            time.sleep(6)
            
            try:
                pr = requests.get(full_page, headers=HEADERS, timeout=40)
                videos, pics = extract_video_and_pics(pr.text, full_page)
            except Exception as e:
                print(f"Post page fail: {e}")
                continue
            
            if videos:
                for v_idx, v_url in enumerate(videos):
                    raw_path = os.path.join(TMP, f"vid_{name}_{page}_{v_idx}.mp4")
                    print(f"    ↓ Video {v_idx+1} DL: {v_url[:80]}...")
                    if fast_download(v_url, raw_path):
                        print("    ↑ Sending video...")
                        send_video(raw_path, title, name)
                        try:
                            os.remove(raw_path)
                        except:
                            pass
            
            if pics:
                print(f"    Found {len(pics)} pics → sending separately...")
                send_pics(pics, title, name)
            
            time.sleep(DELAY)

print("\nDone! Check channel. If no video → console-এ error দেখো বা local Bot API চালাও (2GB limit)। আরও site চাইলে বলো।")
