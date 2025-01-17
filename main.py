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

# 检查图片是否有效（忽略小于1KB的图片）
def is_valid_image(image_url):
    try:
        response = requests_cffi.get(image_url, headers=headers, stream=True, impersonate="chrome124")
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            if 'image' in content_type:  # 确保是图片类型
                # 获取图片的Content-Length（文件大小），如果小于1KB则认为是无效图片
                content_length = response.headers.get('Content-Length', None)
                if content_length and int(content_length) > 1024:  # 至少需要 1KB 的图片
                    return True
        return False
    except Exception as e:
        print(f"检查图片有效性时发生错误： {e}")
        return False

# 下载图片并返回文件路径
def download_image(photo_url):
    try:
        parsed_url = urlparse(photo_url)
        domain = parsed_url.netloc
        if any(ignored_domain in domain for ignored_domain in IGNORED_DOMAINS):
            print(f"忽略图床域名： {domain}")
            return None
        
        if is_valid_image(photo_url):
            response = requests_cffi.get(photo_url, headers=headers, stream=True, impersonate="chrome124")
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
    text_with_single_image = len(photo_urls) == 1 and not attachment_urls and len(msg) <= 1024

    # 发送图片组
    for i, photo_url in enumerate(photo_urls):
        file_path = download_image(photo_url)
        if file_path:
            with open(file_path, "rb") as f:
                if text_with_single_image and i == 0:  # 如果是单图且满足条件，将文字作为caption
                    caption = f"<b>{msg.split('\n')[0]}</b>{msg[len(msg.split('\n')[0]):]}"
                    media.append(telegram.InputMediaPhoto(media=f, caption=caption, parse_mode='HTML'))
                else:
                    media.append(telegram.InputMediaPhoto(media=f))
            os.remove(file_path)
        else:
            if text_with_single_image and i == 0:
                caption = f"<b>{msg.split('\n')[0]}</b>{msg[len(msg.split('\n')[0]):]}"
                media.append(telegram.InputMediaPhoto(media=photo_url, caption=caption, parse_mode='HTML'))
            else:
                media.append(telegram.InputMediaPhoto(media=photo_url))

    # 如果有多张图片，发送媒体组
    if media:
        await bot.send_media_group(chat_id=CHANNEL_ID, media=media)

    # 发送文字内容（如果未作为图片的 caption 或存在附件）
    if len(photo_urls) == 0 or len(photo_urls) > 1:  # 处理多图时的正文推送
        post_title = msg.split("\n")[0]
        bold_title = f"*{post_title}*"  # 使用Markdown格式加粗标题
        msg = msg.replace(post_title, bold_title, 1)

        if attachment_urls:
            msg += "\n附件链接：\n" + "\n".join(attachment_urls)

        # 拆分正文内容，确保每条消息不超过4096字符
        max_length = 4096
        while len(msg) > max_length:
            part = msg[:max_length]
            await bot.send_message(chat_id=CHANNEL_ID, text=part, parse_mode='Markdown')
            msg = msg[max_length:]  # 剩余部分继续处理

        # 发送剩余部分（如果有）
        if msg:
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

                    message = f"{post_title}\n{post_link}\n{post_content}"

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
