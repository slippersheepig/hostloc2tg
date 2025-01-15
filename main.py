from curl_cffi import requests as requests_cffi
import time
import random
import asyncio
import telegram
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os

# 从 .env 文件中读取配置
config = dotenv_values("/opt/h2tg/.env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]
# 关键字过滤
KEYWORDS_WHITELIST = config.get("KEYWORDS_WHITELIST").split(',') if config.get("KEYWORDS_WHITELIST") else []
KEYWORDS_BLACKLIST = config.get("KEYWORDS_BLACKLIST").split(',') if config.get("KEYWORDS_BLACKLIST") else []
# 忽略的图床域名
IGNORED_DOMAINS = config.get("IGNORED_DOMAINS").split(',') if config.get("IGNORED_DOMAINS") else []

# 创建 Telegram Bot 实例
bot = telegram.Bot(token=BOT_TOKEN)

# 上次检查的时间戳，初始设为当前时间 - 3分钟
last_check = int(time.time()) - 180
# 保存已推送过的新贴链接
pushed_posts = set()

# 模拟浏览器的请求头
headers = {
    'Host': 'hostloc.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'DNT': '1',
    'Pragma': 'no-cache',
    'Priority': 'u=0, i',
    'Sec-Ch-Ua': '"Chromium";v="131", "Microsoft Edge";v="131", "Not?A_Brand";v="99"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate', 
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1'
}

# 下载图片并返回文件路径
def download_image(photo_url):
    try:
        parsed_url = urlparse(photo_url)
        domain = parsed_url.netloc
        if any(ignored_domain in domain for ignored_domain in IGNORED_DOMAINS):
            print(f"忽略图床域名： {domain}")
            return None
        
        response = requests_cffi.get(photo_url, headers=headers, impersonate="chrome124")
        if response.status_code == 200:
            file_path = "temp_image.jpg"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        return None
    except Exception as e:
        print(f"下载图片时发生错误： {e}")
        return None

# 发送消息到 Telegram Channel
async def send_message(msg, photo_urls=[], attachment_urls=[]):
    media = []
    # 判断是否为单张图片且字符数不超过1024
    text_with_single_image = len(photo_urls) == 1 and not attachment_urls and len(msg) <= 1024

    # 发送带图片的消息
    for i, photo_url in enumerate(photo_urls):
        file_path = download_image(photo_url)
        if file_path:
            with open(file_path, "rb") as f:
                # 如果是单张图片且满足条件，将文字作为caption
                if text_with_single_image:
                    media.append(telegram.InputMediaPhoto(media=f, caption=msg))
                else:
                    media.append(telegram.InputMediaPhoto(media=f))
            os.remove(file_path)
        else:
            # 使用URL发送图片作为备份
            if text_with_single_image:
                media.append(telegram.InputMediaPhoto(media=photo_url, caption=msg))
            else:
                media.append(telegram.InputMediaPhoto(media=photo_url))
    
    if media:
        # 如果是多图，单独发送图片组
        await bot.send_media_group(chat_id=CHANNEL_ID, media=media)

    # 如果有附件，或者未满足单图文字条件，发送文本消息和附件
    if attachment_urls:
        msg += "\n附件链接：\n" + "\n".join(attachment_urls)
    
    # 如果未发送文本，确保文本消息仍被发送
    if not text_with_single_image or len(photo_urls) > 1:
        await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode='Markdown')

# 解析帖子内容
def parse_post_content(post_link):
    try:
        response = requests_cffi.get(post_link, headers=headers, impersonate="chrome124")
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        post_content_tag = soup.find("td", {"class": "t_f", "id": lambda x: x and x.startswith("postmessage_")})

        content = ""
        photo_urls = []
        attachment_urls = []

        if post_content_tag:
            content = post_content_tag.get_text("\n", strip=True)
            photo_tags = post_content_tag.find_all("img")
            photo_urls = [tag["src"] if tag["src"].startswith("http") else urljoin(post_link, tag['src']) for tag in photo_tags if "src" in tag.attrs]

            attachment_tags = post_content_tag.select("a[href*='forum.php?mod=attachment']")
            attachment_urls = [urljoin(post_link, tag['href']) for tag in attachment_tags]

        return content, photo_urls, attachment_urls

    except Exception as e:
        print(f"发生错误： {e}")
        return "", [], []

def parse_relative_time(relative_time_str):
    if "分钟前" in relative_time_str:
        minutes_ago = int(relative_time_str.split()[0])
        return int(time.time()) - minutes_ago * 60
    else:
        return None

async def check_hostloc():
    global last_check
    try:
        response = requests_cffi.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers, impersonate="chrome124")
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select(".xst")

        for link in reversed(post_links):
            post_link = "https://www.hostloc.com/" + link['href']
            post_title = link.string

            post_time_str = link.parent.find_next('em').text
            post_time = parse_relative_time(post_time_str)

            if post_link not in pushed_posts and post_time is not None and post_time > last_check:
                if (not KEYWORDS_WHITELIST or any(keyword in post_title for keyword in KEYWORDS_WHITELIST)) and not any(keyword in post_title for keyword in KEYWORDS_BLACKLIST):
                    pushed_posts.add(post_link)

                    post_content, photo_urls, attachment_urls = parse_post_content(post_link)

                    message = f"*{post_title}*\n{post_link}\n{post_content}"

                    await send_message(message, photo_urls, attachment_urls)

        if post_links and post_time is not None:
            last_check = post_time

    except Exception as e:
        print(f"发生错误： {e}")

async def run_scheduler():
    while True:
        await asyncio.sleep(random.uniform(60, 120))
        await check_hostloc()

if __name__ == "__main__":
    asyncio.run(run_scheduler())
