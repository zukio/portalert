# PORT ALERT

このプロジェクトは、指定したシェアサイクルポートの在庫が残１になった際にユーザーに通知するシステムです。ユーザーはUIを使ってポートを選択し、通知設定を行うことができます。

## 機能

- シェアサイクルポートの在庫状況を監視
- 在庫が1台以上になった際に、LINE、IFTTT、Zapierなどのサービスを通じてユーザーに通知
- ユーザーごとに通知設定をカスタマイズ可能
- 複数ユーザーの同時利用をサポート

## 技術スタック

- **バックエンド**: Flask / FastAPI
- **フロントエンド**: HTML, CSS, JavaScript
- **データベース**: SQLite
- **スケジューリング**: APScheduler
- **外部API**:
    - [シェアサイクルAPI](https://ckan.odpt.org/dataset/c_bikeshare_gbfs-d-bikeshare)
    - LINE Messaging API
    - IFTTT Webhooks
    - Zapier Webhooks

## 開発環境のセットアップ

1. **Clone the repository:** 
    ```
    git clone https://github.com/your-username/sharecycle-notifier.git
    ```
2. **Install dependencies:**  
    ```
    pip install -r requirements.txt
    ```
3. **Configure database:**  
    Initialize the SQLite database and create necessary tables.
4. **Run the application:** 
    ```
    python main.py
    ```

### Libraries

The project utilizes the following libraries:
* Flask/FastAPI: Backend framework.
* Requests: For making HTTP requests to the ShareCycle API.
* SQLite: For storing user data.
* APScheduler: For scheduling tasks.

### ローカルで実行する

`python main.py`を実行して開発サーバーを起動します。 Web ブラウザを通じて「http://localhost:5000」にある UI にアクセスします。

### ngrok を使用した Webhook のテスト

ngrok を使用してローカル開発サーバーをインターネットに公開し、Webhook 統合をテストできるようにします。
1. ngrok をインストールします: `brew install ngrok` (または ngrok.com からダウンロード)
2. ngrok を起動します: `ngrok http 5000`
3. 統合内の Webhook URL を ngrok 転送アドレスに更新します。

## Deployment

アプリケーションは、Render や Heroku などのプラットフォームにデプロイできます。 
* **レンダリング:** Flask/FastAPI アプリケーションをデプロイするためのシンプルかつ効率的な方法を提供します。
* **Heraku:** Web アプリケーションをデプロイするためのもう 1 つの人気のあるプラットフォームであり、さまざまなデプロイ オプションを提供します。

## Contributing

Contributions are welcome! Please fork the repository and submit pull requests for bug fixes, features, or improvements.

## License

This project is licensed under the MIT License.

   
