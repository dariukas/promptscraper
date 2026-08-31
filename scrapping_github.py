import os
import time
import requests
import json

# Fetch the secret securely from the GitHub environment
API_KEY = os.environ.get('BRIGHTDATA_API_KEY')

if not API_KEY:
    raise ValueError("❌ Action required: Add 'BRIGHTDATA_API_KEY' to your GitHub Repository Secrets!")
else:
    print("✅ Bright Data credential initialized securely.")

# Configuration Settings
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
POSTS_DATASET_ID = "gd_lkaxegm826bjpoo9m5"
COMMENTS_DATASET_ID = "gd_lkay758p1eanlolqw8"
TARGET_URL = "https://www.facebook.com/profile.php?id=61576977390696"

max_posts_count = 1209
max_comments_count = 20


def fetch_dataset_results(snapshot_id):
    """
    Monitor Progress API implementation:
    Polls Bright Data API until the scraping job status returns 'ready'.
    """
    status_url = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
    print(f"   📊 Monitoring Progress (Snapshot ID: {snapshot_id})...")

    while True:
        response = requests.get(status_url, headers=HEADERS)

        if response.status_code != 200:
            print(f"   ❌ Progress Check Failed. HTTP Code: {response.status_code} - Body: {response.text}")
            return []

        try:
            status_res = response.json()
        except Exception:
            print("   ❌ Monitor Progress API returned unparseable data.")
            return []

        status = status_res.get("status")
        print(f"   Current Job Status: [{status}]")

        if status == "ready":
            print("   ✨ Scrape complete! Downloading payload...")
            download_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
            download_res = requests.get(download_url, headers=HEADERS)
            try:
                return download_res.json()
            except Exception:
                print("   ❌ Failed to parse final data payload.")
                return []

        elif status in ["failed", "cancelled"]:
            print(f"   ❌ Scraping execution stopped by server with status: {status}")
            return []

        # Wait 60 seconds before pinging the Monitor Progress API again to avoid rate limiting
        time.sleep(60)

def collect_profile_posts(profile_url, max_posts=5):
    """Triggers dataset job and fetches the profile posts payload data structure."""
    print(f"\n🚀 Phase 1: Gathering posts from profile: {profile_url}")
    trigger_url = "https://api.brightdata.com/datasets/v3/trigger"
    params = {
        "dataset_id": POSTS_DATASET_ID,
        "include_errors": "true"
    }
    payload = [{"url": profile_url, "num_of_posts": 1209, "start_date": "", "end_date": ""}]

    response = requests.post(trigger_url, headers=HEADERS, params=params, json=payload)

    if response.status_code != 200:
        print(f"❌ Phase 1 Trigger failed! HTTP Code: {response.status_code}")
        print(f"📋 Raw text body received: {response.text}")
        return []

    try:
        res_data = response.json()
        # Bright Data returns either a list with dict info or a single dict object
        if isinstance(res_data, list) and len(res_data) > 0:
            snapshot_id = res_data[0].get("snapshot_id")
        else:
            snapshot_id = res_data.get("snapshot_id")
    except Exception:
        print(f"❌ Phase 1 returned bad JSON string format: {response.text}")
        return []

    if not snapshot_id:
        print("❌ Trigger worked, but no 'snapshot_id' found in response body:", res_data)
        return []

    return fetch_dataset_results(snapshot_id)


def collect_post_comments(post_url, max_comments=20):
    """Triggers dataset job and fetches comments payload data structures."""
    print(f"\n💬 Phase 2: Analyzing comments on post URL -> {post_url}")
    trigger_url = "https://api.brightdata.com/datasets/v3/trigger"
    params = {
        "dataset_id": COMMENTS_DATASET_ID,
        "include_errors": "true"
    }
    payload = [{"url": post_url, "get_all_replies": True, "limit_records": max_comments, "comments_sort": ""}]

    response = requests.post(trigger_url, headers=HEADERS, params=params, json=payload)

    if response.status_code != 200:
        print(f"❌ Phase 2 Trigger failed! HTTP Code: {response.status_code}")
        return []

    try:
        res_data = response.json()
        if isinstance(res_data, list) and len(res_data) > 0:
            snapshot_id = res_data[0].get("snapshot_id")
        else:
            snapshot_id = res_data.get("snapshot_id")
    except Exception:
        return []

    if not snapshot_id:
        return []

    return fetch_dataset_results(snapshot_id)

if __name__ == "__main__":
    final_output = []

    # Pull the initial post items array
    scraped_posts = collect_profile_posts(TARGET_URL, max_posts_count)

    if scraped_posts and isinstance(scraped_posts, list):
        for post in scraped_posts:
            p_url = post.get("url")
            p_image = post.get("post_image")

            # Extract nested attachment images layout securely
            attachments = post.get("attachments")
            if not p_image and attachments:
                if isinstance(attachments, list) and len(attachments) > 0:
                    first_attach = attachments[0]
                    if isinstance(first_attach, dict):
                        p_image = first_attach.get("thumbnail_url")
                elif isinstance(attachments, dict):
                    p_image = attachments.get("thumbnail_url")

            if not p_url:
                continue

            # Pull raw comment streams for this specific post mapping item
            raw_comments = collect_post_comments(p_url, max_comments_count)
            
            # Use a list to maintain order and a set to prevent duplicate comments
            filtered_comments = []
            seen_comments = set()

            if isinstance(raw_comments, list):
                for item in raw_comments:
                    comment_text = item.get("comment_text", "")
                    if comment_text and isinstance(comment_text, str):
                        cleaned_comment = comment_text.strip()
                        
                        # Filter text > 25 words AND check for duplicates
                        if len(cleaned_comment.split()) > 25 and cleaned_comment not in seen_comments:
                            filtered_comments.append(cleaned_comment)
                            seen_comments.add(cleaned_comment)

            # Build the custom aggregated payload result
            final_output.append({
                "post_url": p_url,
                "post_image_url": p_image,
                "comments": filtered_comments
            })

        print("\n🏆 Processing complete! Saving data to repository...")
        
        # Standard Python file saving (Works perfectly on GitHub cloud servers)
        filename = "scraped_results.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Successfully saved to {filename}")
        
    else:
        print("\n🛑 Execution paused. No posts collected. Check log details.")
