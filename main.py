import os
from flask import Flask, request, render_template, jsonify, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import sqlite3
from datetime import datetime
import logging
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from geopy.distance import geodesic

# 環境変数の設定
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'your-channel-secret')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv(
    'LINE_CHANNEL_ACCESS_TOKEN', 'your-channel-access-token')

# グローバル変数の初期化
ports = []
notification_settings = []

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# データベースの初期化
def init_db():
    with sqlite3.connect('sharecycle.db') as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_ports (
                user_id TEXT,
                port_id TEXT,
                notification_type TEXT,
                webhook_url TEXT,
                PRIMARY KEY (user_id, port_id)
            )
        ''')
        conn.commit()

# シェアサイクルAPIからデータを取得
from geopy.distance import geodesic

def fetch_port_data():
    try:
        # APIからデータを取得
        response = requests.get('https://api-public.odpt.org/api/v4/gbfs/docomo-cycle-tokyo/station_information.json')
        data = response.json()
        stations = data['data']['stations']

        # 地域で絞り込み (例: region_idが1のポートのみ)
        region_filtered = [station for station in stations if station['region_id'] == '1']

        # 距離で絞り込み (例: 東京駅から半径1km以内)
        current_location = (35.681236, 139.767125)  # 東京駅
        nearby_filtered = [
            station for station in region_filtered
            if geodesic((station['lat'], station['lon']), current_location).km <= 1
        ]

        # 容量でさらに絞り込み (例: capacityが10以上)
        final_filtered = [station for station in nearby_filtered if station['capacity'] >= 10]

        return final_filtered

    except Exception as e:
        logger.error(f"APIリクエストエラー: {e}")
        return []


# 在庫チェックと通知
def check_and_notify():
    port_data = fetch_port_data()
    if not port_data:
        return

    with sqlite3.connect('sharecycle.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM user_ports')
        user_ports = c.fetchall()

        for user_port in user_ports:
            user_id, port_id, notification_type, webhook_url = user_port
            port = next((p for p in port_data if p['id'] == port_id), None)

            if port and port['bikes_available'] > 0:
                if notification_type == 'line':
                    try:
                        message = f"ポート{port_id}に自転車が{port['bikes_available']}台あります！"
                        line_bot_api.push_message(
                            user_id, TextSendMessage(text=message))
                    except Exception as e:
                        logger.error(f"LINE通知エラー: {e}")

                elif notification_type == 'webhook' and webhook_url:
                    try:
                        requests.post(webhook_url, json={
                            'port_id': port_id,
                            'bikes_available': port['bikes_available']
                        })
                    except Exception as e:
                        logger.error(f"Webhook通知エラー: {e}")


# スケジューラーの設定
scheduler = BackgroundScheduler()
scheduler.add_job(check_and_notify, 'interval', minutes=5)
scheduler.start()


@app.route('/', methods=['GET', 'POST'])
def index():
    global ports
    if request.method == 'POST':
        selected_port_id = int(request.form['port'])
        notification_method = request.form['notification-method']
        with sqlite3.connect('sharecycle.db') as conn:
            c = conn.cursor()
            c.execute('INSERT INTO user_ports (port_id, notification_type) VALUES (?, ?)',
                      (selected_port_id, notification_method))
            conn.commit()
        return redirect(url_for('index'))
    else:
        if not ports:
            ports = fetch_port_data()
        return render_template('index.html', ports=ports)
        # return send_file('index.html', ports=ports)


@app.route('/set_port', methods=['POST'])
def set_port():
    data = request.json
    user_id = data.get('user_id')
    port_id = data.get('port_id')
    notification_type = data.get('notification_type', 'line')
    webhook_url = data.get('webhook_url')

    try:
        with sqlite3.connect('sharecycle.db') as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO user_ports (user_id, port_id, notification_type, webhook_url)
                VALUES (?, ?, ?, ?)
            ''', (user_id, port_id, notification_type, webhook_url))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"データベース更新エラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        port_id = event.message.text
        user_id = event.source.user_id

        with sqlite3.connect('sharecycle.db') as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO user_ports (user_id, port_id, notification_type)
                VALUES (?, ?, ?)
            ''', (user_id, port_id, 'line'))
            conn.commit()

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"ポート{port_id}の監視を開始します。")
        )
    except Exception as e:
        logger.error(f"メッセージ処理エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="エラーが発生しました。")
        )


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
