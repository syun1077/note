# 📝 note.com 完全自動投稿ツール

AI（Gemini）で記事を自動生成し、note.comに完全自動で投稿するツールです。
GitHub Actionsで毎日自動実行できます（PC不要）。

## 🏗️ 仕組み

```
Gemini AI → 記事生成（タイトル・本文・ハッシュタグ）
     ↓
SEOスコアチェック → 品質確認
     ↓
Gemini Imagen → サムネイル自動生成（Pillow フォールバック）
     ↓
Playwright → note.comにログイン → 記事作成 → 公開
     ↓
Discord / LINE → 投稿結果を通知
     ↓
投稿履歴管理 → テーマ重複防止 → 統計記録
     ↓
GitHub Actions → 毎日自動実行（スケジュール）→ 履歴自動コミット
```

## 📂 ファイル構成

```
note/
├── main.py                  # メインスクリプト（これを実行）
├── article_generator.py     # AI記事生成モジュール
├── note_poster.py           # note.com投稿モジュール（Playwright）
├── post_history.py          # 投稿履歴管理モジュール
├── seo_checker.py           # SEOスコアチェックモジュール
├── thumbnail_generator.py   # サムネイル自動生成モジュール
├── notifier.py              # Discord/LINE通知モジュール
├── config.py                # 設定ファイル（テーマ・スケジュール等）
├── test_post.py             # 投稿テスト用スクリプト
├── requirements.txt         # Pythonパッケージ
├── post_history.json        # 投稿履歴データ（自動生成）
├── thumbnails/              # 生成されたサムネイル画像
├── .env.example             # 環境変数テンプレート
├── .gitignore
├── .github/
│   └── workflows/
│       └── auto_post.yml  # GitHub Actions定義
└── README.md
```

## ✨ 主な機能

- 🤖 **AI記事自動生成** — Gemini APIで高品質な記事を自動生成
- 🔍 **SEOスコアチェック** — タイトル・文字数・見出し・キーワード密度を自動分析
- 🖼️ **サムネイル自動生成** — Gemini Imagen → Pillow で記事ごとに画像を自動作成
- 📤 **自動投稿** — Playwrightでnote.comに自動ログイン＆投稿
- 💰 **有料記事対応** — 価格設定・無料プレビュー比率の自動設定
- 👥 **複数アカウント対応** — 複数のnoteアカウントへ同時投稿
- 📢 **Discord / LINE通知** — 投稿成功・失敗をリアルタイム通知
- 📊 **投稿履歴管理** — テーマの重複防止・成功/失敗の記録
- 🔄 **完全自動運用** — GitHub Actionsで毎日自動実行（PC不要）

## 🚀 セットアップ手順

### 1. `.env` ファイルを作成

```bash
cp .env.example .env
```

`.env` を開いて以下を設定：

```env
NOTE_EMAIL=あなたのnoteメールアドレス
NOTE_PASSWORD=あなたのnoteパスワード
GEMINI_API_KEY=あなたのGemini APIキー

# 通知（任意）
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
LINE_NOTIFY_TOKEN=your-line-notify-token
```

### 2. Gemini APIキーの取得

1. [Google AI Studio](https://aistudio.google.com/apikey) にアクセス
2. 「APIキーを作成」をクリック
3. 生成されたキーを `.env` の `GEMINI_API_KEY` に設定

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. ローカルでテスト実行

```bash
# 下書きモードでテスト（安全）
python main.py --draft

# テーマを指定して実行
python main.py --draft --theme "プログラミング入門"

# サムネイルなし・通知なしで軽量テスト
python main.py --draft --no-thumbnail --no-notify

# 投稿統計を表示
python main.py --stats

# 本番: 記事を公開
python main.py
```

### 5. GitHub Actionsで完全自動化（PC不要）

1. このフォルダをGitHubリポジトリにプッシュ
2. リポジトリの **Settings → Secrets and variables → Actions** で以下を追加:

   **必須:**
   - `NOTE_EMAIL`: noteのメールアドレス
   - `NOTE_PASSWORD`: noteのパスワード
   - `GEMINI_API_KEY`: Gemini APIキー

   **任意（複数アカウント）:**
   - `NOTE_EMAIL_1` / `NOTE_PASSWORD_1`: 2つ目のアカウント
   - `NOTE_EMAIL_2` / `NOTE_PASSWORD_2`: 3つ目のアカウント

   **任意（通知）:**
   - `DISCORD_WEBHOOK_URL`: Discord Webhook URL
   - `LINE_NOTIFY_TOKEN`: LINE Notify トークン

3. 毎日午前8時（JST）に自動実行されます
4. 投稿履歴とサムネイルも自動でコミットされます

## ⚙️ カスタマイズ

`config.py` を編集して以下を変更できます：

- **記事テーマ**: `ARTICLE_THEMES` リストを編集
- **記事スタイル**: `ARTICLE_STYLE` を編集
- **ハッシュタグ**: `DEFAULT_HASHTAGS` を編集
- **投稿時間**: `CRON_SCHEDULE` を編集
- **有料記事**: `ENABLE_PAID_ARTICLE`, `ARTICLE_PRICE` を編集
- **サムネイル**: `ENABLE_THUMBNAIL` を編集
- **下書きモード**: `.env` で `POST_AS_DRAFT=true` に設定

## 🔔 通知設定

### Discord
1. Discordサーバーの **設定 → 連携サービス → Webhook** でURLを作成
2. `.env` の `DISCORD_WEBHOOK_URL` に設定

### LINE Notify
1. [LINE Notify](https://notify-bot.line.me/my/) でトークンを発行
2. `.env` の `LINE_NOTIFY_TOKEN` に設定

## 👥 複数アカウントへの同時投稿

`.env` に以下のように追加するだけで自動的に複数アカウントへ投稿されます：

```env
NOTE_EMAIL_1=account1@example.com
NOTE_PASSWORD_1=password1
NOTE_EMAIL_2=account2@example.com
NOTE_PASSWORD_2=password2
```

## ⚠️ 注意事項

- note.comの公式APIではなくブラウザ自動化を使用しています
- note.comのUI変更により動作しなくなる可能性があります
- 利用は自己責任でお願いします
- サーバーに過度な負荷をかけないようにしてください
