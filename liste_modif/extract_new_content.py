from bs4 import BeautifulSoup
import re, html

def _find_marker(haystack: str, marker: str) -> int:
    if not marker: return -1
    i = haystack.find(marker)
    if i != -1: return i
    n = html.unescape(marker)
    pattern = re.sub(r"\s+", r"\\s+", re.escape(n))
    m = re.search(pattern, haystack, flags=re.IGNORECASE | re.DOTALL)
    return m.start() if m else -1

def _pick_section_html_for_source(analysis_html: str, source_article: str | None) -> str:
    if not source_article:
        return analysis_html
    m = re.search(r'(\d+(?:\.\d+)*)', source_article)
    wanted = m.group(1) if m else source_article.strip()
    soup = BeautifulSoup(analysis_html, "html.parser")
    for sec in soup.find_all("section"):
        title_text = " ".join(sec.get_text(" ", strip=True).split())
        if re.search(rf'\b{re.escape(wanted)}\b', title_text, flags=re.IGNORECASE):
            return str(sec)
    return analysis_html

def _rehydrate_images(fragment_html: str, img_map: dict) -> str:
    if not img_map:
        return fragment_html
    soup = BeautifulSoup(fragment_html, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and src in img_map:
            img["src"] = img_map[src]
    return str(soup)

def remplacer_new_content(analysis_html: str, img_map: dict, source_article: str | None, start_marker: str | None, end_marker: str | None) -> str | None:
    if not start_marker:
        return None
    scope_html = _pick_section_html_for_source(analysis_html, source_article)
    working_html = scope_html
    start_idx = _find_marker(working_html, start_marker)
    if start_idx == -1:
        working_html = analysis_html
        start_idx = _find_marker(working_html, start_marker)
        if start_idx == -1:
            return None
    end_idx = -1
    if end_marker:
        end_idx = _find_marker(working_html, end_marker)
        if end_idx != -1:
            end_idx = end_idx + len(end_marker)
    if end_idx != -1:
        fragment = working_html[start_idx:end_idx]
        return _rehydrate_images(fragment, img_map).strip()
    soup_scope = BeautifulSoup(working_html, "html.parser")
    for tag_name in ["blockquote", "table", "p", "div", "section"]:
        for tag in soup_scope.find_all(tag_name):
            tag_html = str(tag)
            if _find_marker(tag_html, start_marker) != -1:
                return _rehydrate_images(tag_html, img_map).strip()
    window = 2000
    fragment = working_html[start_idx:start_idx + window]
    return _rehydrate_images(fragment, img_map).strip() if fragment else None