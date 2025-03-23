from serpapi import GoogleSearch
import os

params = {
    "q": "latest news",
    "hl": "en",
    "gl": "us",
    "api_key": os.getenv("SERPAPI_KEY")
}

search = GoogleSearch(params)
results = search.get_dict()
print(results)

