import requests
import time
import random
from datetime import datetime, timedelta
import schedule
import telegram
from pathlib import Path
from dotenv import dotenv_values

parent_dir = Path(__file__).resolve().parent
config = dotenv_values(f"/opt/h2tg/.env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]
# 上次检查的时间戳，初始设为当前时间
last_check = int(time.time())

# 发送消息到 Telegram Channel
def send_message(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    bot.send_message(chat_id=CHANNEL_ID, text=msg)

# 检查 hostloc.com 的新帖子
def check_hostloc():
    global last_check
    # 获取当前时间
    current_time = int(time.time())
    # 计算上次检查到当前时间之间的时间差
    time_diff = current_time - last_check
    # 设置一个时间阈值，例如每隔5分钟检查一次
    time_threshold = timedelta(minutes=5).seconds

    # 如果距离上次检查的时间超过时间阈值，则进行检查
    if time_diff > time_threshold:
        # 更新上次检查的时间为当前时间
        last_check = current_time

        # 对 hostloc.com 发起请求，获取最新的帖子标题
        response = requests.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread")
        html_content = response.text

        # 解析网页内容，获取帖子标题
        # 这里使用的是 BeautifulSoup 库进行网页解析，需要提前安装
        # 可以使用 pip install beautifulsoup4 命令进行安装
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        # 获取最新的帖子标题
        latest_post_title = soup.select(".xst")[0].string

        # 发送最新的帖子标题到 Telegram Channel
        send_message(f"Hostloc 新帖子：{latest_post_title}")

# 使用 schedule 库来定时执行检查
def run_scheduler():
    # 每隔1-2分钟钟执行一次检查
    schedule.every(random.uniform(60, 120)).seconds.do(check_hostloc)

    while True:
        schedule.run_pending()
        time.sleep(1)

# 启动定时任务
run_scheduler()
