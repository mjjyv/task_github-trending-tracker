import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup


def parse_github_trending_html(html_content: str, since: str = "daily") -> List[Dict[str, Any]]:
    """
    Parse HTML của trang GitHub Trending (hoặc fragment HTML).
    Trả về danh sách dict chứa thông tin từng repository.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    articles = soup.find_all("article", class_="Box-row")
    
    repositories: List[Dict[str, Any]] = []
    
    for rank, article in enumerate(articles, start=1):
        # 1. Tên repo & URL
        h2 = article.find("h2", class_=lambda c: c and "h3" in c)
        if not h2:
            # Fallback nếu không có class h3
            h2 = article.find("h2")
        
        a_tag = h2.find("a") if h2 else None
        if not a_tag or not a_tag.get("href"):
            continue
            
        href = a_tag["href"].strip()
        # href thường có dạng '/owner/repo'
        parts = [p for p in href.strip("/").split("/") if p]
        if len(parts) >= 2:
            owner = parts[0]
            repo_name = parts[1]
            full_name = f"{owner}/{repo_name}"
        else:
            full_name = href.strip("/")
            owner = full_name.split("/")[0] if "/" in full_name else ""
            repo_name = full_name.split("/")[1] if "/" in full_name else full_name
            
        repo_url = f"https://github.com/{full_name}"
        
        # 2. Description
        # Repo description thường là thẻ <p> đứng ngay sau <h2> hoặc có class col-9
        desc_p = None
        if h2:
            desc_p = h2.find_next_sibling("p")
        if not desc_p:
            desc_p = article.find("p", class_=lambda c: c and "col-9" in c)
            
        description = desc_p.get_text(strip=True) if desc_p else ""
        
        # 3. Ngôn ngữ & mã màu
        lang_elem = article.find(attrs={"itemprop": "programmingLanguage"})
        language = lang_elem.get_text(strip=True) if lang_elem else None
        
        color_elem = article.find("span", class_="repo-language-color")
        language_color = None
        if color_elem and color_elem.get("style"):
            style = color_elem["style"]
            match = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,6}|[a-zA-Z]+)", style)
            if match:
                language_color = match.group(1)
        
        # 4. Total Stars & Forks
        stargazers_a = article.find("a", href=re.compile(r"/stargazers$"))
        stars = 0
        if stargazers_a:
            stars_text = stargazers_a.get_text(strip=True).replace(",", "")
            try:
                stars = int(stars_text)
            except ValueError:
                stars = 0
                
        forks_a = article.find("a", href=re.compile(r"/forks$|/network/members$"))
        forks = 0
        if forks_a:
            forks_text = forks_a.get_text(strip=True).replace(",", "")
            try:
                forks = int(forks_text)
            except ValueError:
                forks = 0
                
        # 5. Stars gained in period (ví dụ: '52,955 stars this month', '1,200 stars today')
        period_stars_text = ""
        period_stars_count = 0
        
        for span in article.find_all("span"):
            text = span.get_text(strip=True)
            if "stars today" in text or "stars this week" in text or "stars this month" in text:
                period_stars_text = text
                # Extract number
                num_match = re.search(r"([\d,]+)\s+stars", text)
                if num_match:
                    try:
                        period_stars_count = int(num_match.group(1).replace(",", ""))
                    except ValueError:
                        period_stars_count = 0
                break
                
        # 6. Avatars (Built by)
        built_by: List[Dict[str, str]] = []
        for img in article.find_all("img", class_=lambda c: c and "avatar" in c):
            user_a = img.find_parent("a")
            username = user_a["href"].strip("/") if user_a and user_a.get("href") else ""
            avatar_url = img.get("src", "")
            if username:
                built_by.append({"username": username, "avatar_url": avatar_url})
                
        repositories.append({
            "rank": rank,
            "owner": owner,
            "name": repo_name,
            "full_name": full_name,
            "url": repo_url,
            "description": description,
            "language": language,
            "language_color": language_color,
            "stars": stars,
            "forks": forks,
            "period_stars_text": period_stars_text,
            "period_stars_count": period_stars_count,
            "since": since,
            "built_by": built_by,
        })
        
    return repositories
