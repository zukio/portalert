import os
import requests
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
        # ユーザーテーブルの作成
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                webhook_url TEXT NOT NULL
            )
        ''')
        # ポート登録テーブルの作成
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_ports (
                user_id TEXT,
                port_id TEXT,
                PRIMARY KEY (user_id, port_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        conn.commit()


# シェアサイクルAPIからデータを取得
from geopy.distance import geodesic

# ポートデータを取得
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

# ポートの在庫データを取得
def fetch_station_status():
    try:
        response = requests.get('https://api-public.odpt.org/api/v4/gbfs/docomo-cycle-tokyo/station_status.json')
        data = response.json()
        return data['data']['stations']
    except Exception as e:
        logger.error(f"APIリクエストエラー: {e}")
        return []

# 在庫チェックと通知
def check_and_notify():
    stations = fetch_station_status()
    with sqlite3.connect('sharecycle.db') as conn:
        c = conn.cursor()
        c.execute('SELECT users.user_id, users.webhook_url, user_ports.port_id FROM users JOIN user_ports ON users.user_id = user_ports.user_id')
        user_ports = c.fetchall()

        for user_id, webhook_url, port_id in user_ports:
            station = next((s for s in stations if s['station_id'] == port_id), None)
            if station and station['num_bikes_available'] == 1:
                send_webhook_notification(user_id, port_id, webhook_url)

# Webhook URLにPOSTリクエストを送信
def send_webhook_notification(user_id, port_id, webhook_url):
    payload = {
        'user_id': user_id,
        'port_id': port_id,
        'message': f"ポート {port_id} に自転車が1台あります！"
    }
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 200:
            logger.info(f"Webhook通知成功: {webhook_url}")
        else:
            logger.error(f"Webhook通知失敗: {response.status_code}, {response.text}")
    except Exception as e:
        logger.error(f"Webhook送信エラー: {e}")

# スケジューラーの設定
scheduler = BackgroundScheduler()
scheduler.add_job(check_and_notify, 'interval', minutes=5)
scheduler.start()

@app.route('/status')
def status():
    stations = fetch_station_status()
    available_stations = [station for station in stations if station['num_bikes_available'] > 0]
    return render_template('status.html', stations=available_stations)


@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            selected_port_id = int(request.form['port'])
            notification_method = request.form['notification-method']
            user_id = request.form.get('user_id')  # ユーザーIDの取得を追加
            
            with sqlite3.connect('sharecycle.db') as conn:
                c = conn.cursor()
                # ユーザーが存在しなければ追加
                c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
								# ポートとWebhook URLを登録
                c.execute('''
                    INSERT INTO user_ports (user_id, port_id, notification_type) 
                    VALUES (?, ?, ?)
                ''', (user_id, selected_port_id, notification_method))
                conn.commit()
            # return jsonify({'status': 'success'})
            return redirect(url_for('index'))
        
        # GETリクエストの処理
        ports = fetch_port_data()  # グローバル変数を使用せず直接取得
        return render_template('index.html', ports=ports)
        
    except Exception as e:
        logger.error(f"インデックスページ処理エラー: {e}")
        return render_template('error.html', message="エラーが発生しました"), 500


@app.route('/set_port', methods=['POST'])
def set_port():
    data = request.json
    user_id = data.get('user_id')  # 必須
    port_id = data.get('port_id')  # 必須
    webhook_url = data.get('webhook_url')  # 必須（初回登録時のみ必要）

    try:
        with sqlite3.connect('sharecycle.db') as conn:
            c = conn.cursor()
            # ユーザーを登録（すでに存在する場合は無視）
            c.execute('INSERT OR IGNORE INTO users (user_id, webhook_url) VALUES (?, ?)',
                      (user_id, webhook_url))
            # ポートを登録
            c.execute('INSERT OR IGNORE INTO user_ports (user_id, port_id) VALUES (?, ?)',
                      (user_id, port_id))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"データベース更新エラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/unset_port', methods=['POST'])
def unset_port():
    data = request.json
    user_id = data.get('user_id')  # 必須
    port_id = data.get('port_id')  # 必須

    try:
        with sqlite3.connect('sharecycle.db') as conn:
            c = conn.cursor()
            c.execute('DELETE FROM user_ports WHERE user_id = ? AND port_id = ?', (user_id, port_id))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"データベース削除エラー: {e}")
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
