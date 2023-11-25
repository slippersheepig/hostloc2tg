import requests
import time
import random
import asyncio
import telegram
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 从.env文件中读取配置
config = dotenv_values("/opt/h2tg/.env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]
# 关键字过滤
KEYWORDS_WHITELIST = config.get("KEYWORDS_WHITELIST").split(',') if config.get("KEYWORDS_WHITELIST") else []
KEYWORDS_BLACKLIST = config.get("KEYWORDS_BLACKLIST").split(',') if config.get("KEYWORDS_BLACKLIST") else []
# 发帖人屏蔽名单
BLOCKED_POSTERS = config.get("BLOCKED_POSTERS").split(',') if config.get("BLOCKED_POSTERS") else []

# 上次检查的时间戳，初始设为当前时间 - 3分钟
last_check = int(time.time()) - 180
# 保存已推送过的新贴链接
pushed_posts = set()
# 保存登录后的cookie
cookies = None

# 登录hostloc.com账号并获取cookie
def login_hostloc():
    global cookies
    # 使用requests库发送登录请求
    login_data = {
        "username": config["HOSTLOC_USERNAME"],
        "password": config["HOSTLOC_PASSWORD"],
        "fastloginfield": "login",
        "quickforward": "yes",
        "handlekey": "ls"
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.66 Mobile Safari/537.36'
    }
    response = requests.post("https://www.hostloc.com/member.php?mod=logging&action=login&loginsubmit=yes&infloat=yes&lssubmit=yes&inajax=1", data=login_data, headers=headers)

    # 检查登录是否成功
    if "您已经顺利登录" in response.text:
        cookies = response.cookies
        return True
    else:
        return False

# 发送消息到 Telegram Channel
async def send_message(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHANNEL_ID, text=msg)

def parse_relative_time(relative_time_str):
    if "分钟前" in relative_time_str:
        minutes_ago = int(relative_time_str.split()[0])
        return int(time.time()) - minutes_ago * 60
    else:
        return None

# 检查 hostloc.com 的新贴子
async def check_hostloc():
    global last_check, cookies
    # 对hostloc.com发起请求，获取最新的帖子链接和标题
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.66 Mobile Safari/537.36'
    }

    # 登录hostloc.com账号
    if login_hostloc():
        response = requests.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers, cookies=cookies)
        html_content = response.text

        # 解析HTML内容，提取最新的帖子链接和标题
        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select("li.xi1 a[href^='thread-']")

        # 遍历最新的帖子链接
        for link in reversed(post_links):  # 遍历最新的帖子链接，从后往前
            post_link = "https://www.hostloc.com/" + link['href']
            post_title = link.string
            post_poster = link.parent.find_next_sibling('span', class_='byuser').a.string.strip()

            # 获取帖子发布时间
            post_time_str = link.find_previous_sibling('em').text
            post_time = parse_relative_time(post_time_str)

            # 如果没有发布人屏蔽，且没有指定关键字或```python
            # 如果没有发布人屏蔽，且没有指定关键字或帖子链接不在已推送过的新贴集合中，
            # 并且发布时间在上次检查时间之后，并且标题包含白名单关键字，
            # 并且标题不包含黑名单关键字，发送到Telegram Channel并将链接加入已推送集合
            if post_poster not in BLOCKED_POSTERS and post_link not in pushed_posts and post_time is not None and post_time > last_check:
                if (not KEYWORDS_WHITELIST or any(keyword in post_title for keyword in KEYWORDS_WHITELIST)) and not any(keyword in post_title for keyword in KEYWORDS_BLACKLIST):
                    pushed_posts.add(post_link)
                    await send_message(f"{post_title}\n{post_link}")

        # 更新上次检查的时间为当前时间
        last_check = int(time.time())

# 使用 asyncio.create_task() 来运行 check_hostloc() 作为异步任务
async def run_scheduler():
    # 每隔1-2分钟执行一次检查
    while True:
        await asyncio.sleep(random.uniform(60, 120))
        asyncio.create_task(check_hostloc())

# 启动定时任务
if __name__ == "__main__":
    asyncio.run(run_scheduler())
