import os
from app.parser import parse_github_trending_html

def test_parse_html01():
    html_path = os.path.join(os.path.dirname(__file__), "..", "docs", "html01.html")
    assert os.path.exists(html_path)
    
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    repos = parse_github_trending_html(html_content, since="monthly")
    assert len(repos) > 0
    print(f"Parsed {len(repos)} repositories.")
    
    first = repos[0]
    assert first["full_name"] == "tt-a1i/archify"
    assert first["owner"] == "tt-a1i"
    assert first["name"] == "archify"
    assert "architecture" in first["description"].lower()
    assert first["language"] == "JavaScript"
    assert first["stars"] > 50000
    assert first["forks"] > 1000
    assert "stars this month" in first["period_stars_text"]
    assert first["period_stars_count"] > 0
    assert len(first["built_by"]) > 0
