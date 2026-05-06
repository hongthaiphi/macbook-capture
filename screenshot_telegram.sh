#!/bin/bash

BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
CHAT_ID="YOUR_CHAT_ID_HERE"

# Kiểm tra xem có người đang login không
CURRENT_USER=$(who | grep "console" | awk '{print $1}' | head -1)

if [ -z "$CURRENT_USER" ]; then
    echo "$(date): Không có người login → Bỏ qua chụp ảnh" >> /tmp/screenshot.log
    exit 0
fi

echo "$(date): Người dùng $CURRENT_USER đang login → Tiến hành chụp" >> /tmp/screenshot.log

SCREENSHOT="/tmp/screenshot_$(date +%s).png"

# Chụp màn hình
screencapture -x -C -t png "$SCREENSHOT"

# Gửi Telegram
curl -s -F chat_id="$CHAT_ID" \
     -F caption="📸 $(hostname) - $CURRENT_USER - $(date +'%Y-%m-%d %H:%M:%S')" \
     -F photo=@"$SCREENSHOT" \
     "https://api.telegram.org/bot$BOT_TOKEN/sendPhoto"

rm -f "$SCREENSHOT"