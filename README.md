# PORT ALERT

このプロジェクトは、指定したシェアサイクルポートの在庫が残１になった際にユーザーに通知するシステムです。ユーザーはUIを使ってポートを選択し、通知設定を行うことができます。

## 機能

- シェアサイクルポートの在庫状況を監視
- ポートの停車台数が1台になった場合にWebhookへ通知します。
  - Webhook通知により、LINEやIFTTT、Zapierなど柔軟な通知先に対応します。
- 複数ユーザーの同時利用をサポート
  - ユーザーごとに通知設定をカスタマイズ可能

## 技術スタック

- **バックエンド**: Flask / FastAPI
- **フロントエンド**: HTML, CSS, JavaScript
- **データベース**: SQLite
- **スケジューリング**: APScheduler
- **外部API**:
  - [シェアサイクルAPI](https://ckan.odpt.org/dataset/c_bikeshare_gbfs-d-bikeshare)  

## 開発環境のセットアップ

1. **Clone the repository:**

    ```git
    git clone https://github.com/your-username/sharecycle-notifier.git
    ```

2. **Install dependencies:**  

    ```python
    pip install -r requirements.txt
    ```

3. **Configure database:**  
    Initialize the SQLite database and create necessary tables.

4. **Run the application:**  

    ```python
    python main.py
    ```

### Libraries

The project utilizes the following libraries:

- Flask/FastAPI: Backend framework.
- Requests: For making HTTP requests to the ShareCycle API.
- SQLite: For storing user data.
- APScheduler: For scheduling tasks.

### **データ構造の設計**

`user_id`を含むデータベーステーブルを設計し、ユーザーとポート、Webhookを関連付けます。

#### **テーブル構造**

1. **usersテーブル**  

   | フィールド       | 型          | 説明                      |
   |------------------|-------------|---------------------------|
   | `user_id`        | TEXT        | ユーザーを一意に識別するID |
   | `webhook_url`    | TEXT        | ユーザーのWebhook URL     |

2. **user_portsテーブル**  
  
   | フィールド       | 型          | 説明                           |
   |------------------|-------------|--------------------------------|
   | `user_id`        | TEXT        | ユーザーID（usersテーブル参照） |
   | `port_id`        | TEXT        | 登録ポートのID                 |

#### **ポート登録エンドポイント**

`user_id`と`port_id`を受け取り、データベースに保存します。

#### **ポート解除エンドポイント**

特定のユーザーが登録したポートを解除します。

#### **通知ロジック（Webhook通知）**

登録された全ユーザーのポートを監視し、条件を満たした場合に対応するユーザーごとのWebhookに通知を送信します。

1. **1つのWebhookで複数ポート対応**  
   Webhookリクエストに`user_id`と`port_id`を含めることで、受け取った側でポートごとに処理可能。
2. **Webhookの一元化**  
   ユーザーがWebhook URLを自由にカスタマイズ可能（例: LINE Bot、IFTTT、Slack）。

### ローカルで実行する

`python main.py`を実行して開発サーバーを起動します。 Web ブラウザを通じて「<http://localhost:5000>」にある UI にアクセスします。

### ngrok を使用した Webhook のテスト

ngrok を使用してローカル開発サーバーをインターネットに公開し、Webhook 統合をテストできるようにします。

1. ngrok をインストールします: `brew install ngrok` (または ngrok.com からダウンロード)
2. ngrok を起動します: `ngrok http 5000`
3. 統合内の Webhook URL を ngrok 転送アドレスに更新します。

## Deployment

アプリケーションは、Render や Heroku などのプラットフォームにデプロイできます。  

- **レンダリング:** Flask/FastAPI アプリケーションをデプロイするためのシンプルかつ効率的な方法を提供します。
- **Heraku:** Web アプリケーションをデプロイするためのもう 1 つの人気のあるプラットフォームであり、さまざまなデプロイ オプションを提供します。

## Contributing

Contributions are welcome! Please fork the repository and submit pull requests for bug fixes, features, or improvements.

## License

This project is licensed under the MIT License.
