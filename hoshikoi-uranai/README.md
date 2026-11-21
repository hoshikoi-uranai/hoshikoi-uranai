# ✦ 星恋占い

12星座の恋愛運・総合運を毎日自動更新する無料占いサイト。  
GitHub Actions + Gemini API で完全自動・完全無料運用。

## 構成

```
.github/workflows/generate.yml  ← 毎日JST9時に自動実行
generator/generate.py           ← 占いHTML生成スクリプト
docs/                           ← GitHub Pages 公開フォルダ
  index.html                    ← 今日の占い（毎日自動更新）
  archive.html                  ← 過去記事一覧
  horoscope/YYYY-MM-DD.html     ← 日付別アーカイブ
  style.css                     ← デザイン
```

## セットアップ

### 1. シークレット登録
GitHub リポジトリの Settings > Secrets and variables > Actions に登録：

| シークレット名 | 内容 |
|---|---|
| `GEMINI_API_KEY` | Gemini API キー |

### 2. GitHub Pages の設定
Settings > Pages > Source を **Deploy from a branch** に設定。  
Branch: `main` / Folder: `/docs`

### 3. 動作確認
Actions タブから `毎日占い生成 & デプロイ` を手動実行。

## 技術スタック
- Python 3.11
- Gemini API (gemini-2.0-flash-lite) — 完全無料
- GitHub Actions — 完全無料
- GitHub Pages — 完全無料
