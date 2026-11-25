import os
import json
import datetime
import shutil
import time
import signal
from google import genai
from google.genai import errors as genai_errors

# APIタイムアウト時間（秒）
API_TIMEOUT = 60

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("API呼び出しがタイムアウトしました")

# =============================
# 設定
# =============================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

SIGNS = [
    {"name": "牡羊座", "en": "aries",     "period": "3/21〜4/19", "emoji": "♈"},
    {"name": "牡牛座", "en": "taurus",    "period": "4/20〜5/20", "emoji": "♉"},
    {"name": "双子座", "en": "gemini",    "period": "5/21〜6/21", "emoji": "♊"},
    {"name": "蟹座",   "en": "cancer",    "period": "6/22〜7/22", "emoji": "♋"},
    {"name": "獅子座", "en": "leo",       "period": "7/23〜8/22", "emoji": "♌"},
    {"name": "乙女座", "en": "virgo",     "period": "8/23〜9/22", "emoji": "♍"},
    {"name": "天秤座", "en": "libra",     "period": "9/23〜10/23","emoji": "♎"},
    {"name": "蠍座",   "en": "scorpio",   "period": "10/24〜11/22","emoji":"♏"},
    {"name": "射手座", "en": "sagittarius","period": "11/23〜12/21","emoji":"♐"},
    {"name": "山羊座", "en": "capricorn", "period": "12/22〜1/19", "emoji": "♑"},
    {"name": "水瓶座", "en": "aquarius",  "period": "1/20〜2/18", "emoji": "♒"},
    {"name": "魚座",   "en": "pisces",    "period": "2/19〜3/20", "emoji": "♓"},
]

# 日本時間（JST = UTC+9）を明示的に設定
JST = datetime.timezone(datetime.timedelta(hours=9))

def get_today():
    """
    GitHub ActionsはUTC動作。
    cron '0 18 * * *' = UTC 18:00 = JST 翌3:00 のため、
    UTCの日付ではなくJSTの日付を明示的に取得する。
    例: UTC 2026-11-21 18:00 → JST 2026-11-22 03:00 → 11月22日として生成
    """
    return datetime.datetime.now(datetime.timezone.utc).astimezone(JST)

# 試すモデルの優先順位（上から順に試す、すべて無料枠対応）
MODELS = [
    "gemini-3.8-flash",       # メイン
    "gemini-3.6-flash",       # フォールバック1
    "gemini-3.5-flash-lite",  # フォールバック2
]

def generate_horoscope(date_str, max_retries=3, retry_wait=20):
    """Gemini APIで12星座分の占いをまとめて生成（503エラー時はリトライ）"""
    sign_list = "、".join([s["name"] for s in SIGNS])
    prompt = f"""
あなたはプロの占い師です。
{date_str}の12星座（{sign_list}）それぞれの恋愛運・総合運・ラッキーアイテムをJSON形式で出力してください。

以下のJSON形式のみで出力してください（説明文・マークダウン不要）:
{{
  "牡羊座": {{
    "love": "恋愛運の文章（100文字程度、具体的なアドバイスを含む）",
    "general": "総合運の文章（60文字程度）",
    "lucky_item": "ラッキーアイテム（10文字以内）",
    "lucky_color": "ラッキーカラー（5文字以内）",
    "score": 恋愛運スコア（1〜5の整数）
  }},
  ... 残り11星座も同様 ...
}}

ポイント：
- 恋愛運は片思い・カップル両方に使えるアドバイスを含める
- 毎日異なる内容になるよう、今日の日付({date_str})を意識する
- 神秘的で前向きなトーンにする
"""
    for model in MODELS:
        print(f"[INFO] モデル: {model} を試します")
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[INFO] API呼び出し試行 {attempt}/{max_retries}")

                # タイムアウト設定（60秒で強制中断）
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(API_TIMEOUT)

                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                finally:
                    signal.alarm(0)  # タイムアウト解除

                text = response.text.strip()
                # コードブロックがあれば除去
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                print(f"[INFO] モデル {model} で成功しました")
                return json.loads(text.strip())

            except TimeoutError:
                print(f"[WARN] タイムアウト（{API_TIMEOUT}秒超過）")
                if attempt < max_retries:
                    print(f"[INFO] {retry_wait}秒後にリトライします...")
                    time.sleep(retry_wait)

            except genai_errors.ServerError as e:
                print(f"[WARN] 503エラー（混雑中）: {e}")
                if attempt < max_retries:
                    print(f"[INFO] {retry_wait}秒後にリトライします...")
                    time.sleep(retry_wait)

            except Exception as e:
                print(f"[WARN] モデル {model} でエラー: {e}")
                break  # このモデルは諦めて次へ

        print(f"[WARN] モデル {model} は失敗しました。次のモデルへ...")

    raise RuntimeError("全モデルで失敗しました。時間をおいて再実行してください。")

def stars(score):
    """スコアを星HTMLに変換"""
    filled = "★" * score
    empty  = "☆" * (5 - score)
    return f'<span class="stars">{filled}{empty}</span>'

def render_index(today, horoscope_data):
    """index.htmlを生成"""
    date_str = today.strftime("%Y年%m月%d日")
    date_id  = today.strftime("%Y-%m-%d")

    cards = ""
    for sign in SIGNS:
        data = horoscope_data.get(sign["name"], {})
        love    = data.get("love",    "占い生成中...")
        general = data.get("general", "")
        lucky_item  = data.get("lucky_item",  "")
        lucky_color = data.get("lucky_color", "")
        score   = data.get("score", 3)
        cards += f"""
        <article class="card" id="{sign['en']}">
          <div class="card-header">
            <span class="emoji">{sign['emoji']}</span>
            <div>
              <h2 class="sign-name">{sign['name']}</h2>
              <p class="period">{sign['period']}</p>
            </div>
            {stars(score)}
          </div>
          <div class="card-body">
            <div class="section love-section">
              <h3>💕 恋愛運</h3>
              <p>{love}</p>
            </div>
            <div class="section general-section">
              <h3>🌟 総合運</h3>
              <p>{general}</p>
            </div>
            <div class="lucky-row">
              <span class="lucky-badge">🎁 {lucky_item}</span>
              <span class="lucky-badge">🎨 {lucky_color}</span>
            </div>
          </div>
        </article>
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{date_str}の12星座恋愛占い。今日のあなたの恋愛運・総合運・ラッキーアイテムを毎日更新でお届けします。">
  <meta property="og:title" content="{date_str}の星恋占い | 12星座恋愛運">
  <meta property="og:description" content="今日の恋愛運を星の導きでチェック。毎日更新の無料占いサイト。">
  <title>{date_str}の星恋占い ✨ 12星座恋愛運</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&family=Cinzel:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="stars-bg"></div>

  <header>
    <div class="header-inner">
      <p class="site-subtitle">星の導きで紡ぐ愛のメッセージ</p>
      <h1 class="site-title">✦ 星恋占い ✦</h1>
      <p class="today-date">{date_str}</p>
    </div>
  </header>

  <nav class="sign-nav">
    {"".join([f'<a href="#{s["en"]}">{s["emoji"]}{s["name"]}</a>' for s in SIGNS])}
  </nav>

  <main>
    <section class="intro">
      <p>星々はあなたの恋を見守っています。<br>今日の星の導きに耳を傾けてみましょう。</p>
    </section>

    <div class="cards-grid">
{cards}
    </div>

    <section class="note-link" style="margin-bottom:16px;">
      <p>✨ さらに詳しい恋愛占いはこちら ✨</p>
      <a href="https://note.com/lucky_godwit6515" target="_blank" class="note-btn">
        noteで詳細な占いを読む →
      </a>
    </section>

    <section class="note-link">
      <p>💫 あなたの恋愛スタイルを16タイプで解き明かす 💫</p>
      <a href="mbti/index.html" class="note-btn" style="background:linear-gradient(135deg,#ec4899,#8b5cf6);">
        MBTI恋愛診断を試す →
      </a>
    </section>

    <section class="archive-link">
      <a href="archive.html">📅 過去の占いを見る</a>
    </section>
  </main>

  <footer>
    <p>© 星恋占い — 毎日更新の無料恋愛占いサイト</p>
    <p class="footer-note">占いは参考程度にお楽しみください</p>
  </footer>
</body>
</html>
"""
    return html

def render_archive(entries):
    """archive.htmlを生成"""
    rows = ""
    for e in entries:
        rows += f'<li><a href="horoscope/{e}.html">📅 {e} の占い</a></li>\n'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>過去の占い一覧 | 星恋占い</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&family=Cinzel:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="stars-bg"></div>
  <header>
    <div class="header-inner">
      <p class="site-subtitle">星の導きで紡ぐ愛のメッセージ</p>
      <h1 class="site-title">✦ 星恋占い ✦</h1>
    </div>
  </header>
  <main>
    <h2 class="archive-title">📅 過去の占い一覧</h2>
    <ul class="archive-list">
{rows}
    </ul>
    <p><a href="index.html" class="back-link">← 今日の占いに戻る</a></p>
  </main>
  <footer>
    <p>© 星恋占い</p>
  </footer>
</body>
</html>
"""

def render_daily_page(today, horoscope_data):
    """日付別アーカイブページを生成"""
    date_str = today.strftime("%Y年%m月%d日")
    # index.htmlとほぼ同じ内容でアーカイブ保存
    html = render_index(today, horoscope_data)
    # タイトルをアーカイブ用に調整
    html = html.replace(
        f"<title>{date_str}の星恋占い ✨ 12星座恋愛運</title>",
        f"<title>[アーカイブ] {date_str}の星恋占い | 星恋占い</title>"
    )
    # horoscope/配下に置くためCSSパスを1階層上に修正
    html = html.replace(
        '<link rel="stylesheet" href="style.css">',
        '<link rel="stylesheet" href="../style.css">'
    )
    # archive.htmlへのリンクも修正
    html = html.replace(
        '<a href="archive.html">📅 過去の占いを見る</a>',
        '<a href="../archive.html">📅 過去の占いを見る</a>'
    )
    return html

def get_archive_list(docs_dir):
    """既存のアーカイブファイル一覧を取得（新しい順）"""
    horoscope_dir = os.path.join(docs_dir, "horoscope")
    if not os.path.exists(horoscope_dir):
        return []
    files = [f.replace(".html", "") for f in os.listdir(horoscope_dir) if f.endswith(".html")]
    return sorted(files, reverse=True)

def main():
    today    = get_today()
    date_str = today.strftime("%Y年%m月%d日")
    date_id  = today.strftime("%Y-%m-%d")
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")

    print(f"[INFO] 生成開始: {date_str}")

    # 占い生成
    print("[INFO] Gemini APIで占い生成中...")
    horoscope_data = generate_horoscope(date_str)
    print("[INFO] 占い生成完了")

    # index.html 更新
    index_html = render_index(today, horoscope_data)
    with open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print("[INFO] index.html を更新しました")

    # 日付別アーカイブページ生成
    horoscope_dir = os.path.join(docs_dir, "horoscope")
    os.makedirs(horoscope_dir, exist_ok=True)
    daily_html = render_daily_page(today, horoscope_data)
    with open(os.path.join(horoscope_dir, f"{date_id}.html"), "w", encoding="utf-8") as f:
        f.write(daily_html)
    print(f"[INFO] horoscope/{date_id}.html を生成しました")

    # archive.html 更新
    archive_list = get_archive_list(docs_dir)
    archive_html = render_archive(archive_list)
    with open(os.path.join(docs_dir, "archive.html"), "w", encoding="utf-8") as f:
        f.write(archive_html)
    print("[INFO] archive.html を更新しました")

    print("[INFO] 全処理完了 ✨")

if __name__ == "__main__":
    main()
