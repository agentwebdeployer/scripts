import os
from dotenv import load_dotenv
import requests
import json
import re
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import NoCredentialsError
import time
import uuid
import google.generativeai as genai

load_dotenv()

def slugify(text):
    """
    Convert a string to a URL-friendly slug.
    """
    text = text.lower()
    text = re.sub(r'[\\s_]+', '-', text)  # Replace spaces and underscores with hyphens
    text = re.sub(r'[^\\w-]', '', text)   # Remove all non-word chars except hyphens
    text = text.strip('-')
    return text

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
OPENAI_IMAGE_API_KEY = os.environ.get('OPENAI_IMAGE_API_KEY', '')

# This is the image generation endpoint from the original script
IMAGE_API_URL = 'https://api.openai.com/v1/images/generations'

# --- AWS S3 Configuration ---
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1') # Default to a common region

# ==============================================================================
# 2. GEMINI AI & IMAGE GENERATION & S3 UPLOAD
# ==============================================================================

class GeminiAI:
    """A simple client to interact with the Gemini AI API."""
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')

    def generate_content(self, prompt, max_tokens=4000):
        """Generic content generation with Gemini AI."""
        try:
            # The 'max_tokens' parameter is not directly supported in the same way.
            # Gemini's output length is controlled by other factors and safety settings.
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ An error occurred while communicating with the Gemini API: {e}")
            return None

    def generate_blog_topics(self, business_context, num_topics=100):
        print(f"🧠 Generating {num_topics} blog topics based on business context...")
        prompt = f"""
        Based on the following website copy for 'AgentWeb', an AI marketing agency, please generate a list of {num_topics} unique, SEO-optimized blog post titles.

        The target audience is early-stage founders (pre-seed to Series A) who are focused on product development but need to validate their GTM strategy and drive growth.

        The titles should be engaging, relevant, and cover topics like:
        - Go-to-market (GTM) strategy for startups
        - AI in marketing and automation
        - Practical growth hacking tips
        - SEO and content marketing for early-stage companies
        - Founder branding and thought leadership on platforms like LinkedIn
        - Validating digital marketing channels without a large budget or team
        - Weekly marketing workflows and campaign execution

        Business Context:
        ---
        {business_context}
        ---

        Please return ONLY a valid JSON object with a single key "titles" which contains an array of the {num_topics} generated string titles. Do not include any other text, explanations, or markdown formatting in your response.

        Example Format:
        {{
          "titles": [
            "10 AI-Powered Marketing Tools to Scale Your Startup in 2025",
            "The Founder's Guide to Building a GTM Strategy from Scratch",
            "How to Use LinkedIn for B2B Lead Generation: A Step-by-Step Plan"
          ]
        }}
        """
        response_text = self.generate_content(prompt)
        if not response_text:
            print("❌ Failed to generate blog topics.")
            return []

        try:
            # Clean the response to find the JSON block, even with markdown backticks
            match = re.search(r'```(json)?(.*)```', response_text, re.DOTALL)
            if match:
                # If markdown is found, extract the content within
                json_str = match.group(2).strip()
            else:
                # Otherwise, assume the whole response is the JSON string
                json_str = response_text.strip()

            data = json.loads(json_str)
            return data.get("titles", [])
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON from AI response. Error: {e}")
            print(f"Raw response was: {response_text}")
            return []

    def generate_image_prompt(self, title, article_extract):
        """Generates a descriptive image prompt from the article content."""
        print("🎨 Generating image prompt...")
        prompt = f"""
        Based on the blog post title and a text extract, create a highly descriptive and creative image generation prompt.
        The blog post is for AgentWeb, a cutting-edge AI marketing agency.
        The image should be professional, visually appealing, and relevant to themes like marketing, automation, data, business strategy, or AI. It should be abstract or conceptual rather than literal. Avoid text in the image.

        Title: {title}
        
        Extract: "{article_extract}"

        Return ONLY the image prompt text with no additional commentary or explanations.
        """
        return self.generate_content(prompt)


def upload_image_to_s3(image_data, object_name):
    """Uploads image data to an S3 bucket and returns the public URL."""
    if not all([S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]):
        print("❌ ERROR: S3 bucket credentials are not fully configured in .env file. Cannot upload.")
        return None

    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    
    try:
        # We need to determine the content type for the upload
        content_type = 'image/png' # The API seems to return PNGs
        
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=object_name,
            Body=image_data,
            ContentType=content_type
        )
        
        # Construct the public URL
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{object_name}"
        print(f"✅ Successfully uploaded image to S3: {s3_url}")
        return s3_url

    except NoCredentialsError:
        print("❌ ERROR: AWS credentials not found. Please check your .env file.")
        return None
    except Exception as e:
        print(f"❌ An error occurred during S3 upload: {e}")
        return None


def generate_and_upload_image(prompt):
    """Generates an image using DALL-E 3, downloads it, and uploads it to S3."""
    if not prompt:
        print("⚠️ No prompt provided for image generation. Skipping.")
        return None, None

    if not OPENAI_IMAGE_API_KEY:
        print("❌ ERROR: OPENAI_IMAGE_API_KEY is not set. Cannot generate image.")
        return None, None

    print(f"🖼️  Requesting image from DALL-E 3 with prompt: '{prompt[:70]}...'")
    
    headers = {
        "Authorization": f"Bearer {OPENAI_IMAGE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024" # or "1792x1024" or "1024x1792"
    }

    try:
        # Step 1: Get the image URL from the DALL-E 3 API
        response = requests.post(IMAGE_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        source_image_url = data['data'][0]['url']
        
        if not source_image_url:
            print(f"❌ Failed to get source_image_url from DALL-E 3 API response: {data}")
            return None, None
        
        print(f"✅ Image generation successful. Source URL: {source_image_url}")
        
        # Step 2: Download the image content from the source URL
        print(f"⬇️  Downloading image from {source_image_url}...")
        image_response = requests.get(source_image_url)
        image_response.raise_for_status()
        image_data = image_response.content

        # Step 3: Upload the downloaded data to our S3 bucket
        # Create a unique name for the file in S3, following the specified structure.
        task_id = str(int(time.time() * 1000))
        unique_filename = f"{uuid.uuid4()}.png"
        object_name = f"tasks/{task_id}/attachments/{unique_filename}"
        s3_url = upload_image_to_s3(image_data, object_name)

        return s3_url, unique_filename

    except requests.exceptions.RequestException as e:
        print(f"❌ An error occurred while generating the image: {e}")
        # Log the full error response for debugging if possible
        if e.response is not None:
            print(f"Error response: {e.response.text}")
        return None, None

def generate_pillar_page(ai_client, pillar_title, linked_articles):
    """Generates a pillar page that links to other articles."""
    print(f"🏛️  Generating pillar page: '{pillar_title}'...")

    # Create a markdown list of the article titles to link to
    links_markdown = ""
    for title, slug in linked_articles:
        links_markdown += f"- [{title}](/{slug})\\n"

    prompt = f"""
    You are an expert SEO content writer and marketing strategist for 'AgentWeb', an AI marketing agency. Your persona is modeled after a seasoned YC founder who gives direct, actionable advice. Your audience is early-stage (pre-seed to Series A) B2B SaaS founders who are technical and product-focused.

    Your task is to write a comprehensive, foundational pillar page with the title: "{pillar_title}". This article will serve as a central hub for a topic and must be at least 2500 words.

    **Content Rules:**
    1.  **Structure and Formatting:**
        - Use Markdown for formatting.
        - IMPORTANT: Use ONLY H2 and H3 headings for section titles. Never use H4 or lower.
        - NEVER prefix headings with "H2:" or "H3:". They should appear as natural titles.
        - Ensure all sections are complete and provide deep, practical value.

    2.  **Pillar Content and Interlinking:**
        - The pillar page must provide a comprehensive overview of the main topic.
        - You MUST naturally and contextually link to the following related blog posts. Weave them into the body of the text where they add the most value and feel like a natural next step for the reader.
        - **Blog posts to link to:**
          {links_markdown}

    3.  **Internal Linking Strategy (Homepage, Build, Pricing):**
        - You MUST include **exactly one** link to our homepage, `https://www.agentweb.pro`, within a natural, relevant sentence about the value of a 'done-for-you' marketing service for busy founders.
        - If the topic discusses different ways to implement marketing solutions, you MAY link to our self-service platform page, `https://www.agentweb.pro/build`, for founders who prefer a hands-on approach.
        - If the topic touches on cost or investment, you MAY link to our pricing page, `https://www.agentweb.pro/pricing`.

    4.  **Call-to-Action (CTA):**
        - The article MUST conclude with the following call-to-action as the final paragraph:
        "Ready to put your marketing on autopilot? [Book a call with Harsha](https://calendly.com/harsha-agentweb/30min) to walk through your current marketing workflow and see how AgentWeb can help you scale."

    **Output Format:**
    You must return ONLY a valid JSON object with two keys: "description" and "article_body".
    - "description": A short, compelling summary of the pillar page for a meta description (1-2 sentences, no markdown).
    - "article_body": The full pillar page content, following all the rules above.

    Now, generate the pillar page content for the title: "{pillar_title}"
    """
    response_text = ai_client.generate_content(prompt)
    if not response_text:
        print("❌ Failed to generate pillar page content.")
        return None, None, None, None, None

    try:
        content_json = json.loads(response_text)
        description = content_json.get("description", "")
        article_body = content_json.get("article_body", "")
    except json.JSONDecodeError:
        print("❌ Failed to parse pillar page JSON response. Using fallback.")
        description = "A comprehensive guide from AgentWeb."
        article_body = response_text

    image_prompt = ai_client.generate_image_prompt(pillar_title, article_body[:500])
    image_url, image_filename = generate_and_upload_image(image_prompt)

    slug = slugify(pillar_title)
    output_filename = f"seo_automator/generated_content/pillar_{slug}.md"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(f"# {pillar_title}\\n\\n")
        f.write(f"**Description:** {description}\\n\\n")
        if image_url:
            f.write(f"![Generated Image]({image_url})\\n\\n")
        f.write(article_body)

    # Add structured data
    add_structured_data(output_filename, pillar_title, description, image_url, datetime.now().isoformat())
    print(f"✅ Pillar page saved to '{output_filename}'")

    return pillar_title, description, article_body, image_url, image_filename

def add_structured_data(file_path, title, description, image_url, published_date):
    """Appends JSON-LD structured data to a markdown file."""
    schema = {
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": title,
      "description": description,
      "image": image_url,
      "author": {
        "@type": "Organization",
        "name": "AgentWeb"
      },
      "publisher": {
        "@type": "Organization",
        "name": "AgentWeb",
        "logo": {
          "@type": "ImageObject",
          "url": "https://www.agentweb.pro/logo.png" # Replace with your actual logo URL
        }
      },
      "datePublished": published_date,
      "mainEntityOfPage": {
          "@type": "WebPage",
          "@id": f"https://www.agentweb.pro/blog/{slugify(title)}"
      }
    }

    # Wrap in a script tag and append to the file
    script_tag = f'\\n\\n<script type="application/ld+json">\\n{json.dumps(schema, indent=2)}\\n</script>'

    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(script_tag)

def generate_full_article_and_image(ai_client, article_title):
    """Generates one article, an image for it, saves it, and returns all data."""
    print(f"🤖 Starting content generation for: '{article_title}'...")

    prompt = f"""
    You are an expert SEO content writer and marketing strategist for 'AgentWeb', an AI marketing agency. Your persona is modeled after a seasoned YC founder who gives direct, actionable advice. Your audience is early-stage (pre-seed to Series A) B2B SaaS founders who are technical and product-focused.

    Your task is to write a high-quality, comprehensive, and SEO-optimized article with the title: "{article_title}".

    **Content Rules:**
    1.  **Structure and Formatting:**
        - The article must be at least 1500 words.
        - Use Markdown for formatting.
        - IMPORTANT: Use ONLY H2 and H3 headings for section titles. Never use H4 or lower.
        - NEVER prefix headings with "H2:" or "H3:". They should appear as natural titles.
        - Ensure all sections are complete. Do not use placeholders like "[Insert example here]" or leave sections with empty examples.

    2.  **Internal Linking Strategy (Crucial for SEO):**
        - You MUST include **exactly one** link to our homepage, `https://www.agentweb.pro`, within a natural, relevant sentence about the value of a 'done-for-you' marketing service for busy founders.
        - If the topic discusses different ways to implement marketing solutions, you MAY link to our self-service platform page, `https://www.agentweb.pro/build`, for founders who prefer a hands-on approach.
        - If the topic touches on cost or investment, you MAY link to our pricing page, `https://www.agentweb.pro/pricing`.

    3.  **Call-to-Action (CTA):**
        - The article MUST conclude with the following call-to-action as the final paragraph:
        "Ready to put your marketing on autopilot? [Book a call with Harsha](https://calendly.com/harsha-agentweb/30min) to walk through your current marketing workflow and see how AgentWeb can help you scale."

    **Output Format:**
    You must return ONLY a valid JSON object with two keys: "description" and "article_body".
    - "description": A short, compelling, plain-text summary of the article for a meta description (1-2 sentences, no markdown).
    - "article_body": The full article content, following all the rules above.

    Now, generate the content for the title: "{article_title}"
    """

    response_text = ai_client.generate_content(prompt)

    if not response_text:
        print("❌ Failed to generate article content. Aborting.")
        return None, None, None, None, None

    print(f"📄 Raw AI Response: {response_text}") # Log the raw response

    # Clean the response to remove markdown code blocks if they exist
    if response_text.strip().startswith("```json"):
        # Find the first { and the last } to extract the JSON object
        start_index = response_text.find('{')
        end_index = response_text.rfind('}')
        if start_index != -1 and end_index != -1:
            response_text = response_text[start_index:end_index+1]

    try:
        content_json = json.loads(response_text)
        description = content_json.get("description", "")
        article_body = content_json.get("article_body", "")
        if not description or not article_body:
            raise ValueError("Missing description or article_body in AI response.")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ Failed to parse AI response as valid JSON. Error: {e}")
        print("Falling back to using the full response as the article body.")
        description = ' '.join(response_text.strip().split()[:30]) + "..." # Fallback description
        article_body = response_text

    print("✅ Article content and description generated.")
    
    # Generate an image prompt from an extract of the article
    extract = ' '.join(article_body.strip().split()[:100])
    image_prompt = ai_client.generate_image_prompt(article_title, extract)
    
    # Generate the actual image URL by uploading to S3
    image_url, image_filename = generate_and_upload_image(image_prompt)

    # Save the local file
    slug = slugify(article_title)
    output_filename = f"seo_automator/generated_content/{slug}.md"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(f"# {article_title}\\n\\n")
        f.write(f"**Description:** {description}\\n\\n")
        if image_url:
            f.write(f"![Generated Image]({image_url})\\n\\n")
        f.write(article_body)

    # Add structured data to the file
    add_structured_data(output_filename, article_title, description, image_url, datetime.now().isoformat())

    print(f"✅ Article and image data saved to '{output_filename}'")
    
    return article_title, description, article_body, image_url, image_filename, slug


# ==============================================================================
# 3. BASEHUB ARTICLE POSTING
# ==============================================================================

def post_article_to_basehub(title, description, content, image_url, image_filename, published_at):
    """Posts the generated article and image to Basehub."""
    print("\\n🚀 Posting generated article to Basehub...")

    BASEHUB_API_URL = os.environ.get('BASEHUB_API_URL', 'https://api.basehub.com/graphql')
    BASEHUB_TOKEN = os.environ.get('BASEHUB_TOKEN', '')
    POSTS_COLLECTION_ID = 'dKrosxXlaGpnZCrAbHxlX'

    if not BASEHUB_TOKEN:
        print("❌ ERROR: BASEHUB_TOKEN is not set. Cannot publish.")
        return

    # This structure exactly matches the working basehub_test_post.py
    transaction_data = {
        "type": "create",
        "parentId": POSTS_COLLECTION_ID,
        "data": {
            "title": title, # Use the generated title
            "type": "instance",
            "value": {
                "description": {
                    "type": "text",
                    "value": description
                },
                "publishedAt": {
                    "type": "date",
                    "value": published_at.isoformat()
                },
                "body": {
                    "type": "rich-text",
                    "value": {
                        "format": "markdown",
                        "value": content # Use the generated content
                    }
                },
                "authors": {
                    "type": "reference",
                    "value": [
                        "PCMhesaHZ237t05iG8ms6"
                    ]
                }
            }
        }
    }

    if image_url and image_filename:
        transaction_data["data"]["value"]["image"] = {
            "type": "instance",
            "mainComponentId": "AAzuzbz0jSbfwGJYvtMu3",
            "value": {
                "light": {
                    "type": "media",
                    "value": {
                        "url": image_url,
                        "fileName": image_filename
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

    try:
        response = requests.post(
            BASEHUB_API_URL,
            json={"query": mutation, "variables": variables},
            headers=headers
        )
        response.raise_for_status()
        print("Status Code:", response.status_code)
        print("Response:", response.text)
    except requests.exceptions.RequestException as e:
        print(f"❌ An error occurred while publishing to Basehub: {e}")

# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    website_context = """
    Build Your Own Our Story Blog Pricing Log In Get Started Your Marketing on Autopilot We run your marketing to prove whether digital can actually drive leads, before you waste time or budget. Get Started Start Self-Serve › Hero image Video Only have a couple of minutes? Watch this
    How It Works How AgentWeb Runs Your Marketing From kickoff to launch, here's how we drive growth without making you manage a team.
    1 Kickoff Strategy Call We meet 1:1 to understand your product, goals, and where you are in your GTM journey. You’ll get a draft roadmap after this session.
    2 Build Your 3-Month Plan We map the channels, content, and weekly deliverables you’ll need to hit your growth goals, based on your stage and audience,
    3 Launch Weekly Campaigns We write, design, and schedule content across your core channels. You approve. We ship. No babysitting required.
    4 Review, Learn, Iterate Each week, we review what worked, what didn’t, and make adjustments. You’ll always know what’s moving the needle.
    What You Get What You’ll Get in Your First 3 Months A complete, repeatable GTM system, built and tested for your business.
    A custom GTM plan tailored to your product, ICP, and goals
    Weekly campaign execution across SEO, social, paid, or email
    Up to 20 content assets per month (video, blog, social, or ad formats)
    Founder positioning + ghostwritten content (LinkedIn, launches, etc.)
    Branded templates and workflows you can reuse post-engagement
    Full access to performance insights + recommendations
    A dedicated async feedback loop via Slack or portal
    3-month delivery sprint designed to scale or hand off seamlessly
    Transition path to AgentWeb’s self-serve platform (optional)
    Is AgentWeb Right for You? We built AgentWeb for founders who want traction without the overhead. If you’re not sure which path fits, here’s a quick guide.
    ✅ You’re a great fit if… You want to grow without managing a team, a stack, or a mess of freelancers. You’re pre-seed to Series A and focused on building product You want campaigns shipped weekly, not strategy decks You’ve tried doing it yourself but need more consistency You want to validate whether digital can actually work for your business You want marketing to move faster than hiring allows Get Started ➡️ You might be better off with our platform if… You want to run things yourself and just need the tools to do it faster. You prefer hands-on control and like building workflows You already have a marketing team or internal execution support You’re an agency, consultant, or operator managing multiple brands You want access to specific campaign templates, not full service You’re exploring AI agents to run parts of your GTM stack Start Self-Serve
    """
    try:
        ai_client = GeminiAI(api_key=GEMINI_API_KEY)
    except ValueError as e:
        print(f"❌ {e}")
        exit()

    blog_titles = ai_client.generate_blog_topics(website_context, num_topics=100)
    if not blog_titles:
        print("❌ Could not generate blog titles. Aborting.")
        exit()

    print(f"✅ Successfully generated {len(blog_titles)} blog titles. Starting article generation...")

    start_date = datetime.now()
    generated_articles = []

    for i, title in enumerate(blog_titles):
        print(f"--- Generating article {i+1}/{len(blog_titles)}: '{title}' ---")
        try:
            # Pass the ai_client and title to the generation function
            article_title, description, article_content, image_url, image_filename, slug = generate_full_article_and_image(ai_client, title)

            if article_title and article_content:
                generated_articles.append({"title": article_title, "slug": slug})
                print(f"✅ Successfully generated and saved article for '{title}'.")
                publish_date = start_date - timedelta(days=i)
                post_article_to_basehub(article_title, description, article_content, image_url, image_filename, publish_date)
            else:
                print(f"⚠️ Failed to generate article for '{title}'. Skipping.")
        except TypeError:
            print(f"⚠️ An error occurred during generation for '{title}'. Skipping.")
        except Exception as e:
            print(f"❌ An unexpected error occurred for title '{title}': {e}. Skipping.")

    print("\\n✅ Bulk content generation complete.")
    print("\\n🏛️  Now generating pillar pages...")

    pillar_page_titles = [
        "The Founder's Complete Guide to Go-To-Market Strategy",
        "AI-Powered Marketing: The Ultimate Playbook for Startups",
        "From Zero to Hero: A Founder's Guide to Building a Powerful Personal Brand",
        "The Scrappy Startup's Guide to SEO and Content Marketing",
        "The Art of the Weekly Marketing Sprint: A System for Consistent Growth"
    ]

    # Split the generated articles into chunks for each pillar page
    chunk_size = len(generated_articles) // len(pillar_page_titles)
    article_chunks = [generated_articles[i:i + chunk_size] for i in range(0, len(generated_articles), chunk_size)]

    for i, p_title in enumerate(pillar_page_titles):
        if i < len(article_chunks):
            pillar_title, p_desc, p_content, p_img_url, p_img_filename = generate_pillar_page(ai_client, p_title, article_chunks[i])
            if pillar_title:
                publish_date = start_date - timedelta(days=len(blog_titles) + i)
                post_article_to_basehub(pillar_title, p_desc, p_content, p_img_url, p_img_filename, publish_date)

    print("\\n✅ Pillar page generation complete.") 