# SEO Automator

This directory contains a suite of scripts for automating SEO content creation and publishing to a Basehub CMS.

## Scripts

- `seo_content_automation.py`: The main script that orchestrates content generation. It uses Gemini AI to generate blog topics and articles, DALL-E 3 for image generation, and uploads images to AWS S3.
- `basehub_test_post.py`: A script for testing the creation of a new blog post in Basehub.
- `basehub_test_read.py`: A script for testing the reading of blog posts from Basehub.
- `generate_trends_csv.py`: A simple script to generate a `trends.csv` file with a list of keywords.

## Setup

1.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Create a `.env` file** in this directory with the following secrets:
    ```
    GEMINI_API_KEY=your_gemini_api_key
    OPENAI_IMAGE_API_KEY=your_openai_api_key
    S3_BUCKET_NAME=your_s3_bucket_name
    AWS_ACCESS_KEY_ID=your_aws_access_key
    AWS_SECRET_ACCESS_KEY=your_aws_secret_key
    AWS_REGION=your_aws_region
    BASEHUB_API_URL=https://api.basehub.com/graphql
    BASEHUB_TOKEN=your_basehub_token
    ```

## Usage

- To run the main content automation script:
  ```bash
  python seo_automator/seo_content_automation.py
  ```
- To test posting to Basehub:
  ```bash
  python seo_automator/basehub_test_post.py
  ```
- To test reading from Basehub:
  ```bash
  python seo_automator/basehub_test_read.py
  ```
- To generate a sample `trends.csv` file:
  ```bash
  python seo_automator/generate_trends_csv.py
  ```
