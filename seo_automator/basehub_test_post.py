import os
from dotenv import load_dotenv
load_dotenv()
import requests
import json
from datetime import datetime

BASEHUB_API_URL = os.environ.get('BASEHUB_API_URL', 'https://api.basehub.com/graphql')
BASEHUB_TOKEN = os.environ.get('BASEHUB_TOKEN', '')
POSTS_COLLECTION_ID = 'dKrosxXlaGpnZCrAbHxlX'

# This is the correct structure based on the working mutation from the Basehub team.
transaction_data = {
    "type": "create",
    "parentId": POSTS_COLLECTION_ID,
    "data": {
        "title": "This is a test post from Python",
        "type": "instance",
        "value": {
            "description": {
                "type": "text",
                "value": "This is a test description from the Python script."
            },
            "publishedAt": {
                "type": "date",
                "value": datetime.now().isoformat()
            },
            "body": {
                "type": "rich-text",
                "value": {
                    "format": "markdown",
                    "value": "# Python Test Works!\n\nThis post was successfully created by the Python test script."
                }
            },
            "authors": {
                "type": "reference",
                "value": [
                    "PCMhesaHZ237t05iG8ms6"
                ]
            },
            "image": {
                "type": "instance",
                "mainComponentId": "AAzuzbz0jSbfwGJYvtMu3",
                "value": {
                    "light": {
                        "type": "media",
                        "value": {
                            "url": "https://agentweb-user-files.s3.us-west-2.amazonaws.com/tasks/1752798032367/attachments/5c4e2eb2-b6c4-4597-9c84-f50b561425d1.png",
                            "fileName": "image.png"
                        }
                    }
                }
            }
        }
    }
}

mutation = '''
mutation CreateBlogPost($data: String!) {
  transaction(data: $data)
}
'''

variables = {"data": json.dumps(transaction_data)}
headers = {
    "Authorization": f"Bearer {BASEHUB_TOKEN}",
    "Content-Type": "application/json"
}

response = requests.post(
    BASEHUB_API_URL,
    json={"query": mutation, "variables": variables},
    headers=headers
)

print("Status Code:", response.status_code)
print("Response:", response.text) 