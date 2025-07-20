from exa_py import Exa
import json
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("EXA_API_KEY")

if not api_key:
    print("API key not found")
    exit(1)

exa = Exa(api_key=api_key)

result = exa.search(
    "private colleges universities United States STEM programs under 10000 students not on CommonApp or Niche in non-coastal underserved regions",
    type="auto",
    num_results=50,
    include_domains=[".edu"]
)

with open("exa_results.txt", "w") as f:
    f.write(str(result)) 