import os
import requests
import json
import logging
import sqlite3
import time
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi
from linebot.v3.messaging.models import TextMessage
from geopy.distance import geodesic


# .envファイルを読み込む
load_dotenv()

# 環境変数の設定
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv(
    'LINE_CHANNEL_ACCESS_TOKEN')

# グローバル変数の初期化
ports = []
notification_settings = []

app = Flask(__name__)
# Messaging APIクライアントの初期化
line_bot_api = MessagingApi(LINE_CHANNEL_ACCESS_TOKEN)
# 旧　line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
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
                notification_type TEXT,
                last_notified INTEGER DEFAULT 0,
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
import time

def check_and_notify():
    stations = fetch_station_status()
    current_time = int(time.time())  # 現在時刻をUnixタイムスタンプで取得

    with sqlite3.connect('sharecycle.db') as conn:
        c = conn.cursor()
        c.execute('PRAGMA table_info(user_ports)')
        columns = [col[1] for col in c.fetchall()]
        if 'last_notified' not in columns:
            c.execute('ALTER TABLE user_ports ADD COLUMN last_notified INTEGER DEFAULT 0')
            conn.commit()
        c.execute('SELECT user_id, port_id, last_notified FROM user_ports')
        user_ports = c.fetchall()
        
        updates = []
        for user_id, port_id, last_notified in user_ports:
            station = next((s for s in stations if s['station_id'] == port_id), None)
            # 通知の間隔を確認 (例: 3600秒 = 1時間)
            if station and station['num_bikes_available'] == 1:
                if current_time - last_notified >= 3600:
                    send_notification(user_id, port_id)
                    updates.append((current_time, user_id, port_id))

        # 一括でデータベースを更新
        if updates:
            c.executemany('UPDATE user_ports SET last_notified = ? WHERE user_id = ? AND port_id = ?', updates)
            conn.commit()


# LINEとWebhook通知を統合
def send_notification(user_id, port_id):
    message = f"ポート {port_id} に自転車が1台あります！"

    # LINE通知を送信
    try:
        send_line_notification(user_id, message)
    except Exception as e:
        logger.error(f"LINE通知エラー: {e}")

    # Webhook通知を送信
    try:
        send_webhook_notification(user_id, port_id, message)
    except Exception as e:
        logger.error(f"Webhook通知エラー: {e}")


# Webhook URLにPOSTリクエストを送信
def send_webhook_notification(user_id, port_id, message):
    # Webhook URLをデータベースから取得
    with sqlite3.connect('sharecycle.db') as conn:
        c = conn.cursor()
        c.execute('SELECT webhook_url FROM users WHERE user_id = ?', (user_id,))
        webhook_url = c.fetchone()
        if webhook_url:
            try:
                requests.post(webhook_url[0], json={'port_id': port_id, 'message': message})
            except Exception as e:
                logger.error(f"Webhook通知エラー: {e}")

# LINEユーザーに通知
def send_line_notification(user_id, message):
    try:
        line_bot_api.push_message(
            to=user_id,
            messages=[TextMessage(text=message)]
        )
    except Exception as e:
        logger.error(f"LINE通知エラー: {e}")


# スケジューラーの設定
scheduler = BackgroundScheduler()
scheduler.add_job(check_and_notify, 'interval', minutes=5)
scheduler.start()

@app.route('/status')
def status():
    stations = fetch_station_status()
    available_stations = [station for station in stations if station['num_bikes_available'] > 0]
    return render_template('status.html', stations=available_stations)

# 非LINEユーザーの場合、ブラウザUIから Webhook URLを登録
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

# 非LINEユーザーのためのAPIエンドポイントで、フロントエンド（static/script.js）から呼び出されています。
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

# LINE Webhookの設定
@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        # Webhookデータの処理
        handle_message(body, signature)
    except Exception as e:
        logger.error(f"Webhook処理エラー: {e}")
        return f"Error: {str(e)}", 400

    return 'OK'

def handle_message(body, signature):
    # LINEイベントデータを解析
    data = json.loads(body)  # JSONデータを辞書に変換
    # 旧 event = MessageEvent.from_dict(body)
    events = data.get('events', [])  # イベントリストを取得
    for event in events:
      if event['type'] == 'message' and event['message']['type'] == 'text':
          user_id = event['source']['userId']  # ユーザーIDを取得
          message_text = event['message']['text']  # メッセージ内容を取得

          # メッセージ処理
          if message_text.isdigit():  # 数字（ポートID）である場合
              port_id = message_text
              with sqlite3.connect('sharecycle.db') as conn:
                  c = conn.cursor()
                  c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
                  c.execute('INSERT OR IGNORE INTO user_ports (user_id, port_id) VALUES (?, ?)', (user_id, port_id))
                  conn.commit()
              logger.info(f"ポート {port_id} がユーザー {user_id} に登録されました。")
              send_line_notification(user_id, "ポート登録が完了しました！")
          else:
              logger.info(f"ユーザー {user_id} から無効なメッセージ: {message_text}")

    

# アプリケーションのインポート時にデータベースを初期化
init_db()

if __name__ == '__main__':
    app.run(debug=True)
