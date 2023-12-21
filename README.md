借助ChatGPT开发的hostloc新帖图文推送  
⚠️注意
- 本代码无需登录hostloc账号，但同时无法抓取需要登录后才能获取的信息（例如权限、上传方式的图片附件等）；图床等本身无需登录就可以获取的内容可以抓取
- 代码预留了获取上传内容功能，有兴趣的可以自行参考
- 若hostloc开启了反爬，则代码失效
### 使用方法
#### 一、新建`.env`文件，编辑以下内容并保存
```bash
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ
CHANNEL_ID=-10000000000
KEYWORDS_WHITELIST=甲骨文,mjj
KEYWORDS_BLACKLIST=出,收
BLOCKED_POSTERS=5K,HOH
```
`BOT_TOKEN`是你的电报机器人API TOKEN，`CHANNEL_ID`是你的电报频道ID（机器人需在频道内并具有发送消息权限）  
🐼`KEYWORDS`（白名单和黑名单）为可选配置，可以删除，默认推送全部新帖，若设置了关键字（可同时设置），则只推送/不推送包含关键字的新帖，设置多个关键字时，匹配到任一关键字都会推送/不推送，关键字以英文逗号分隔  
❗`BLOCKED_POSTERS`同为可选配置，可以删除，可屏蔽指定人的发帖，以英文逗号分隔
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
![image](https://github.com/slippersheepig/hostloc2tg/assets/58287293/18f6866b-856f-4ac6-b1ac-f5b211c120af)
