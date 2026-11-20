import sqlite3
import time
import requests
from bs4 import BeautifulSoup


def find_repo_card(link_tag):
    """リポジトリリンクを含む1件分のカード要素（他のリポジトリを含まない最大の親要素）を取得"""
    current = link_tag.parent
    while current and current.name not in ("body", "html", "[document]"):
        # この親要素の中に含まれる別のリポジトリリンク（/google/xxx）の数を確認
        repo_links = set()
        for a in current.find_all("a", href=True):
            parts = a["href"].strip("/").split("/")
            if len(parts) == 2 and parts[0] == "google":
                repo_links.add(parts[1])
        # 他のリポジトリまで含んでしまったら、1つ手前の要素を返す
        if len(repo_links) > 1:
            return prev
        prev = current
        current = current.parent
    return link_tag.parent


def scrape_google_repos():
    base_url = "https://github.com/orgs/google/repositories"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    repos_data = []
    seen_repos = set()
    page = 1

    while True:
        url = f"{base_url}?page={page}"
        print(f"取得中: {url}")

        response = requests.get(url, headers=headers)
        # サーバーへの負荷軽減のため1秒待機
        time.sleep(1)

        if response.status_code != 200:
            print(f"ページの取得に失敗しました (Status: {response.status_code})")
            break

        soup = BeautifulSoup(response.text, "html.parser")

        # '/google/リポジトリ名' の形式を持つリンクをすべて探す
        page_repo_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0].split("#")[0]
            parts = href.strip("/").split("/")
            if len(parts) == 2 and parts[0] == "google":
                repo_name = parts[1]
                if repo_name not in seen_repos:
                    seen_repos.add(repo_name)
                    page_repo_links.append((repo_name, a))

        # 新しいリポジトリが1件も見つからなければ全ページ終了
        if not page_repo_links:
            print("全ページの取得が完了しました。")
            break

        for repo_name, link_tag in page_repo_links:
            card = find_repo_card(link_tag)

            # 1. 主要な言語の取得
            language = "None"
            lang_tag = card.select_one("span[itemprop='programmingLanguage']")
            if lang_tag:
                language = lang_tag.get_text(strip=True)
            else:
                # 言語カラーアイコン（丸印のspan）の隣にあるテキストを探す
                for span in card.find_all("span"):
                    style = span.get("style", "")
                    classes = " ".join(span.get("class", []))
                    if "background-color" in style or "repo-language-color" in classes:
                        next_span = span.find_next_sibling("span")
                        if next_span and next_span.get_text(strip=True):
                            language = next_span.get_text(strip=True)
                            break

            # 2. スター数の取得
            star_tag = card.select_one(f"a[href='/{'google'}/{repo_name}/stargazers']") or card.select_one("a[href$='/stargazers']")
            stars = star_tag.get_text(strip=True) if star_tag else "0"

            repos_data.append((repo_name, language, stars))

        print(f"  -> {len(page_repo_links)} 件取得（累計: {len(repos_data)} 件）")

        # 次ページへのリンクがあるか確認
        next_page_num = page + 1
        has_next = (
            soup.select_one("a[rel='next']")
            or soup.select_one("a.next_page")
            or soup.select_one(f"a[href*='page={next_page_num}']")
        )
        if not has_next:
            print("最終ページに到達しました。")
            break

        page += 1

    return repos_data


def save_and_show_db(repos_data, db_name="google_repos.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS repositories")
    cursor.execute("""
        CREATE TABLE repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            language TEXT,
            stars TEXT
        )
    """)

    cursor.executemany(
        "INSERT INTO repositories (name, language, stars) VALUES (?, ?, ?)",
        repos_data
    )
    conn.commit()
    print(f"\nデータベース '{db_name}' に {len(repos_data)} 件のデータを保存しました。\n")

    print("=== 保存されたデータ一覧（SELECT結果） ===")
    cursor.execute("SELECT id, name, language, stars FROM repositories")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]} | リポジトリ名: {row[1]} | 主要言語: {row[2]} | スター数: {row[3]}")

    conn.close()


if __name__ == "__main__":
    data = scrape_google_repos()
    save_and_show_db(data)