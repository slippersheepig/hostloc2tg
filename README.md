借助ChatGPT开发的hostloc新帖推送
### 使用方法
#### 一、新建`.env`文件，编辑以下内容并保存
```bash
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ
CHANNEL_ID=-10000000000
KEYWORDS=甲骨文,mjj
```
`BOT_TOKEN`是你的电报机器人API TOKEN，`CHANNEL_ID`是你的电报频道ID（机器人需在频道内并具有发送消息权限）  
🐼`KEYWORDS`为可选配置，可以删除，默认推送全部新帖，若设置了关键字，则只推送包含关键字的新帖，设置多个关键字时，匹配到任一关键字都会推送，关键字以英文逗号分隔
#### 二、新建`docker-compose.yml`，编辑以下内容并保存
```bash
services:
  h2tg:
    image: sheepgreen/h2tg
    container_name: h2tg
    volumes:
      - ./.env:/opt/h2tg/.env
    restart: always
```
#### 三、输入`docker-comopse up -d`即启动成功
#### 四、效果图
![image](https://github.com/slippersheepig/hostloc2tg/assets/58287293/7a9c060f-7077-4045-9485-5f8d9ab280aa)
