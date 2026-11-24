"""
Buscador y extractor automatizado de bases de datos abiertas (Zenodo, Figshare, GitHub, Dataverse)
para concreto autocurativo bacteriano (CAB) y difusión de cloruros en concreto marino.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path


def fetch_json(url: str, headers: dict | None = None) -> dict | list:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "BioCrete-Research/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    print("=== 1. ZENODO (API oficial - tipo dataset) ===")
    for q in ['"self-healing concrete"', 'bacterial concrete crack', 'concrete chloride diffusion marine']:
        try:
            url = "https://zenodo.org/api/records?" + urllib.parse.urlencode({"q": q, "type": "dataset", "size": 6})
            data = fetch_json(url)
            hits = data.get("hits", {}).get("hits", [])
            print(f"\nQuery: {q} -> total={data.get('hits', {}).get('total', 0)}")
            for h in hits:
                meta = h.get("metadata", {})
                files = [(f["key"], round(f.get("size", 0) / 1024, 1), f["links"]["self"]) for f in h.get("files", [])[:4]]
                print(f"  [Zenodo {h['id']}] {meta.get('title', '')[:95]}")
                print(f"     DOI: {meta.get('doi', 'N/A')}")
                for fname, kb, flink in files:
                    print(f"     Archivo: {fname} ({kb} KB) -> {flink}")
        except Exception as e:
            print(f"  Error Zenodo ({q}): {e}")

    print("\n=== 2. FIGSHARE (API oficial - datasets) ===")
    for q in ["self-healing concrete bacteria", "chloride diffusion concrete marine"]:
        try:
            url = "https://api.figshare.com/v2/articles/search"
            payload = json.dumps({"search_for": q, "item_type": 3, "page_size": 5}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "BioCrete-Research/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                items = json.loads(r.read().decode("utf-8"))
            print(f"\nQuery: {q} -> {len(items)} resultados")
            for it in items:
                print(f"  [Figshare {it.get('id')}] {it.get('title', '')[:95]} | DOI: {it.get('doi', '')} | {it.get('url_public_html', '')}")
        except Exception as e:
            print(f"  Error Figshare ({q}): {e}")

    print("\n=== 3. GITHUB (API oficial - repositorios con datasets) ===")
    for q in ["self-healing concrete", "bacterial concrete", "chloride diffusion concrete dataset", "chloride ingress concrete"]:
        try:
            url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": q, "per_page": 5})
            d = fetch_json(url, {"User-Agent": "BioCrete-Research/1.0", "Accept": "application/vnd.github+json"})
            print(f"\nQuery: {q} -> total={d.get('total_count', 0)}")
            for it in d.get("items", []):
                print(f"  {it['full_name']} (stars={it['stargazers_count']}) | {(it.get('description') or '')[:85]}")
        except Exception as e:
            print(f"  Error GitHub ({q}): {e}")


if __name__ == "__main__":
    main()
