from duckduckgo_search import DDGS

# Minimal search function
def search(query, max_results=10):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(r)
    return results

# Example usage
for i, r in enumerate(search("python web scraping tutorial", 5), 1):
    print(f"   {r['body']}\n")