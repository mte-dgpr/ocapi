from dataclasses import dataclass
import re
import unicodedata

from bs4 import BeautifulSoup

from ocapi.types import ArreteFile, ArreteId


@dataclass
class IdCounter:
    value: int = 0


def make_id(counter: IdCounter) -> str:
    counter.value += 1
    return str(counter.value)

def minify_html_fragment(html: str) -> str:
    """
    Minification légère et normalisation Unicode pour un fragment HTML.
    - supprime <script>/<style>
    - normalize Unicode
    - enlève espaces entre balises et runs d'espaces
    """
    s = str(html or "")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"(?is)<script.*?>.*?</script>", "", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", "", s)
    s = re.sub(r">\s+<", "><", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def _assert_html_equal(minified_html1: str, minified_html2: str):
    """Compare deux HTML en normalisant les espaces blancs"""
    soup1 = BeautifulSoup(minified_html1, 'html.parser')
    soup2 = BeautifulSoup(minified_html2, 'html.parser')
    assert soup1.prettify() == soup2.prettify()

def from_arrete_id_to_ordered_index(arrete_id: ArreteId, list_arretes:list[ArreteFile]) -> int:
    """Convertit une date au format 'YYYY-MM-DD' en un entier 'YYYYMMDD' pour le tri."""
    for arrete in list_arretes:
        if arrete.id == arrete_id:
            return arrete.ordered_index
    raise ValueError(f"ArreteId {arrete_id} not found in provided list.")