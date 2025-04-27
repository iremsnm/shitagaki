from flask import Flask, render_template, request, redirect, url_for, session
import feedparser
import requests
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key"

# YouTube Data APIキー
YOUTUBE_API_KEY = 'AIzaSyAU8HfqaS6DcKSpw2udauKTJKeegz1SCUk'

# 記事を要約する関数
def fetch_article_summary(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        soup = BeautifulSoup(response.content, "html.parser")

        paragraphs = soup.find_all("p")
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 50:
                return text
        return "（本文の要約は発見されませんでした）"
    except Exception as e:
        return f"（要約取得失敗: {e}）"

# タグとYouTubeチャンネルIDの対応
TAG_YOUTUBE_CHANNELS = {
    "fromsoftware": "UCCkxMbfZ80VFwwiRlIG5P5g",
    "koeitecmo": "UCl8iNF8pssHi5sS84XIP8-g",
    "marvelous": "UCRWGKdyjOZE9zeerOPYb1qQ",
    "squareenix": "UC6SmH9mR82nj28_NNg_rZvA",
    "任天堂": "UCkH3CcMfqww9RsZvPRPkAJA",
    # 他のタグをここに追加
}

# Google News RSS URLを生成する関数
def generate_google_news_rss_url(site, keyword):
    encoded_site = urllib.parse.quote(site)
    encoded_keyword = urllib.parse.quote(keyword)
    return f"https://news.google.com/rss/search?q=site:{encoded_site}+{encoded_keyword}&hl=ja"

# YouTubeの最新動画3件を取得する関数
def get_latest_youtube_videos(channel_id):
    youtube_api_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&order=date&maxResults=3&key={YOUTUBE_API_KEY}"
    response = requests.get(youtube_api_url)
    videos = response.json().get('items', [])
    video_data = []
    for video in videos:
        video_data.append({
            'title': video['snippet']['title'],
            'url': f"https://www.youtube.com/watch?v={video['id']['videoId']}",
            'thumbnail': video['snippet']['thumbnails']['high']['url']
        })
    return video_data

@app.route("/", methods=["GET", "POST"])
def index():
    if "keywords" not in session:
        session["keywords"] = []
    if "favorites" not in session:
        session["favorites"] = []

    if request.method == "POST":
        new_keyword = request.form.get("keyword")
        if new_keyword and new_keyword not in session["keywords"]:
            session["keywords"].append(new_keyword)
            session.modified = True

    if "delete_tag" in request.args:
        tag_to_delete = request.args.get("delete_tag")
        if tag_to_delete in session["keywords"]:
            session["keywords"].remove(tag_to_delete)
            session.modified = True

    articles_by_tag = {}
    one_month_ago = datetime.now() - timedelta(weeks=12)

    for keyword in session["keywords"]:
        tag_articles = []
        for site in ["jp.ign.com", "automaton-media.com"]:
            rss_url = generate_google_news_rss_url(site, keyword)
            feed = feedparser.parse(rss_url)

            for entry in feed.entries:
                published = datetime(*entry.published_parsed[:6])
                if published >= one_month_ago:
                    title_lower = entry.title.lower()
                    if ("アーカイブ" in title_lower or "ページ目" in title_lower or
                        keyword.lower() not in title_lower):
                        continue

                    summary = fetch_article_summary(entry.link)
                    tag_articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "summary": summary,
                        "published": published.strftime("%Y年%m月%d日（%a） %H時%M分"),
                        "published_dt": published
                    })

        tag_articles.sort(key=lambda x: x["published_dt"], reverse=True)
        for article in tag_articles:
            del article["published_dt"]
        articles_by_tag[keyword] = tag_articles

    favorite_links = [f["link"] for f in session.get("favorites", [])]

    # YouTube動画情報を取得
    tag_youtube_videos = {}
    for keyword in session["keywords"]:
        if keyword.lower() in TAG_YOUTUBE_CHANNELS:
            channel_id = TAG_YOUTUBE_CHANNELS[keyword.lower()]
            tag_youtube_videos[keyword] = get_latest_youtube_videos(channel_id)

    return render_template("index.html", articles_by_tag=articles_by_tag,
                           favorite_links=favorite_links,
                           tag_youtube_videos=tag_youtube_videos)

@app.route("/toggle_favorite", methods=["POST"])
def toggle_favorite():
    link = request.form["link"]
    title = request.form["title"]
    summary = request.form["summary"]
    published = request.form["published"]

    favorite = {
        "link": link,
        "title": title,
        "summary": summary,
        "published": published
    }

    if "favorites" not in session:
        session["favorites"] = []

    favorites = session["favorites"]
    existing = next((item for item in favorites if item["link"] == link), None)

    if existing:
        favorites.remove(existing)
    else:
        favorites.append(favorite)

    session["favorites"] = favorites
    return redirect(request.referrer or url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
