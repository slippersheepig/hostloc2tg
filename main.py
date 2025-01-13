from curl_cffi import requests as requests_cffi
import time
import random
import asyncio
import telegram
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os

# 从.env文件中读取配置
config = dotenv_values("/opt/h2tg/.env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]
# 关键字过滤
KEYWORDS_WHITELIST = config.get("KEYWORDS_WHITELIST").split(',') if config.get("KEYWORDS_WHITELIST") else []
KEYWORDS_BLACKLIST = config.get("KEYWORDS_BLACKLIST").split(',') if config.get("KEYWORDS_BLACKLIST") else []

# 创建 Telegram Bot 实例
bot = telegram.Bot(token=BOT_TOKEN)

# 上次检查的时间戳，初始设为当前时间 - 3分钟
last_check = int(time.time()) - 180
# 保存已推送过的新贴链接
pushed_posts = set()

# 检查图片链接是否有效且尺寸大于1x1像素
def is_valid_image(url):
    try:
        response = requests_cffi.get(url, stream=True, headers={"Referer": "https://www.hostloc.com", "User-Agent": "Mozilla/5.0"})
        if response.status_code == 200 and "image" in response.headers["Content-Type"]:
            response.raw.decode_content = True
            return int(response.headers.get('Content-Length', 0)) > 100  # 简单检查内容长度是否大于100字节
        return False
    except Exception as e:
        print(f"检查图片链接时发生错误: {e}")
        return False

# 下载图片并返回文件路径
def download_image(photo_url):
    try:
        response = requests_cffi.get(photo_url, headers={"Referer": "https://www.hostloc.com", "User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            file_path = "temp_image.jpg"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        return None
    except Exception as e:
        print(f"下载图片时发生错误: {e}")
        return None

# 发送消息到 Telegram Channel
async def send_message(msg, photo_urls=[], attachment_urls=[]):
    # 过滤无效图片链接
    valid_photo_urls = [url for url in photo_urls if is_valid_image(url)]

    # 如果有有效的图片链接，发送带图片的消息
    if valid_photo_urls:
        media = []
        for photo_url in valid_photo_urls:
            file_path = download_image(photo_url)
            if file_path:
                with open(file_path, "rb") as f:
                    media.append(telegram.InputMediaPhoto(media=f))
                os.remove(file_path)
            else:
                media.append(telegram.InputMediaPhoto(media=photo_url))  # 使用原始URL作为备份
        
        # 发送图片
        await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
    
    # 发送文本消息和附件
    if attachment_urls:
        msg += "\n附件链接:\n" + "\n".join(attachment_urls)
    await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode='Markdown')


# 解析帖子内容（含文字和多张图片）
def parse_post_content(post_link):
    try:
        response = requests_cffi.get(post_link)  # 使用 curl_cffi 请求
        response.raise_for_status()  # 检查请求是否成功
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        post_content_tag = soup.select_one(".t_fsz")

        # 提取发帖内容
        content = ""
        photo_urls = []
        attachment_urls = []  # 新增附件链接列表

        if post_content_tag:
            content = post_content_tag.get_text("\n", strip=True)
            # 提取所有图片链接
            photo_tags = post_content_tag.find_all("img")
            photo_urls = [tag["src"] if tag["src"].startswith("http") else urljoin(post_link, tag['src']) for tag in photo_tags if "src" in tag.attrs]

            # 提取所有附件链接
            attachment_tags = post_content_tag.select("a[href*='forum.php?mod=attachment']")
            attachment_urls = [urljoin(post_link, tag['href']) for tag in attachment_tags]

        return content, photo_urls, attachment_urls

    except Exception as e:
        print(f"发生错误: {e}")
        return "", [], []

def parse_relative_time(relative_time_str):
    if "分钟前" in relative_time_str:
        minutes_ago = int(relative_time_str.split()[0])
        return int(time.time()) - minutes_ago * 60
    else:
        return None

# 检查 hostloc.com 的新贴子
async def check_hostloc():
    global last_check
    try:
        # 发送请求，获取最新的帖子链接和标题
        headers = {
            'Host': 'hostloc.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'Priority': 'u=0, i',
            'Sec-Ch-Ua': '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate', 
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }
        response = requests_cffi.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers, impersonate="chrome110")  # 使用 curl_cffi 请求
        response.raise_for_status()  # 检查请求是否成功
        html_content = response.text

        # 解析HTML内容，提取最新的帖子链接和标题
        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select(".xst")

        # 遍历最新的帖子链接
        for link in reversed(post_links):
            post_link = "https://www.hostloc.com/" + link['href']
            post_title = link.string

            # 获取帖子发布时间
            post_time_str = link.parent.find_next('em').text
            post_time = parse_relative_time(post_time_str)

            # 如果没有指定关键字或帖子链接不在已推送过的新贴集合中，发送到Telegram Channel并将链接加入已推送集合
            if post_link not in pushed_posts and post_time is not None and post_time > last_check:
                if (not KEYWORDS_WHITELIST or any(keyword in post_title for keyword in KEYWORDS_WHITELIST)) and not any(keyword in post_title for keyword in KEYWORDS_BLACKLIST):
                    content, photo_urls, attachment_urls = parse_post_content(post_link)
                    msg = f"新帖子: [{post_title}]({post_link})\n\n{content}"
                    await send_message(msg, photo_urls, attachment_urls)
                    pushed_posts.add(post_link)

        last_check = int(time.time())

    except Exception as e:
        print(f"发生错误: {e}")

# 每隔5秒检查一次
while True:
    asyncio.run(check_hostloc())
    time.sleep(random.randint(1, 5))
