import os
from dotenv import load_dotenv
load_dotenv()
import requests

BASEHUB_API_URL = os.environ.get('BASEHUB_API_URL', 'https://api.basehub.com/graphql')
BASEHUB_TOKEN = os.environ.get('BASEHUB_TOKEN', '')

# GraphQL query to fetch latest blog posts (adjust the query if your schema differs)
query = '''
query BlogPosts {
  site {
    blog {
      posts {
        items {
          _title
          _slug
          publishedAt
          authors {
            _id
            _title
          }
        }
      }
    }
  }
}
'''

headers = {
    "Authorization": f"Bearer {BASEHUB_TOKEN}",
    "Content-Type": "application/json"
}

response = requests.post(
    BASEHUB_API_URL,
    json={"query": query},
    headers=headers
)

print("Status Code:", response.status_code)
print("Response:", response.text)

if response.status_code == 200:
    data = response.json()
    try:
        posts = data['data']['site']['blog']['posts']['items']
        print("\nLatest Blog Posts:")
        for post in posts:
            print(f"- {post['_title']} (slug: {post['_slug']}, published: {post['publishedAt']}), authors: {post['authors']}")
    except Exception as e:
        print("Could not parse posts from response.", e) 