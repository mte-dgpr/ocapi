from bs4 import BeautifulSoup, Tag


def list_top_sections(soup: BeautifulSoup | Tag) -> list[Tag]:
    """
    Itère sur les sections de plus haut niveau dans le document (sans parent section).
    """
    return [sec for sec in soup.find_all("section") if sec.find_parent("section") is None]