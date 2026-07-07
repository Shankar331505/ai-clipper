"""
Publish finished clips to Buffer using Buffer's current GraphQL API.

Buffer moved from a classic REST API to GraphQL - single endpoint,
Bearer token auth. Docs: https://developers.buffer.com

IMPORTANT: Buffer's createPost mutation needs the video at a public URL
(assets.videos[].url) - it does not accept direct file uploads. You must
host final_*.mp4 somewhere public first (e.g. a GitHub Release asset,
Cloudflare R2, S3) and pass that URL to this script instead of a local path.

Usage: python publish.py <metadata_json>
Expects each metadata entry to have a "video_url" field (public URL) -
add this after uploading final_path somewhere public.
"""
import sys
import os
import json
import requests

BUFFER_ACCESS_TOKEN = os.environ["BUFFER_ACCESS_TOKEN"]
BUFFER_API_URL = "https://api.buffer.com"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
}


def graphql_request(query: str, variables: dict = None) -> dict:
    resp = requests.post(
        BUFFER_API_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Buffer API error: {data['errors']}")
    return data["data"]


def get_organization_id() -> str:
    query = """
    query GetOrganizations {
      account {
        organizations {
          id
          name
        }
      }
    }
    """
    data = graphql_request(query)
    orgs = data["account"]["organizations"]
    if not orgs:
        raise RuntimeError("No Buffer organizations found for this account.")
    print(f"Using organization: {orgs[0]['name']} ({orgs[0]['id']})")
    return orgs[0]["id"]


def get_channel_ids(organization_id: str) -> list:
    query = """
    query GetChannels($organizationId: OrganizationId!) {
      channels(input: { organizationId: $organizationId }) {
        id
        name
        service
      }
    }
    """
    data = graphql_request(query, {"organizationId": organization_id})
    channels = data["channels"]
    for ch in channels:
        print(f"Found channel: {ch['name']} ({ch['service']}) -> {ch['id']}")
    return channels


def create_video_post(channel_id: str, service: str, title: str, text: str, video_url: str, thumbnail_url: str = None):
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id text }
        }
        ... on MutationError {
          message
        }
      }
    }
    """
    video_asset = {"url": video_url}
    if thumbnail_url:
        video_asset["thumbnailUrl"] = thumbnail_url

    variables = {
        "input": {
            "text": text,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [
                {
                    "video": video_asset
                }
            ],
        }
    }

    # Add service-specific metadata required by Buffer
    if service == "instagram":
        variables["input"]["metadata"] = {
            "instagram": {
                "type": "reel",
                "shouldShareToFeed": True
            }
        }
    elif service == "youtube":
        variables["input"]["metadata"] = {
            "youtube": {
                "title": title[:100],  # YouTube title limit is 100 characters
                "privacy": "public"
            }
        }

    data = graphql_request(mutation, variables)
    result = data["createPost"]
    if "message" in result:
        print(f"  FAILED: {result['message']}")
    else:
        print(f"  Created post {result['post']['id']}")


def main(metadata_path: str):
    with open(metadata_path) as f:
        metadata = json.load(f)

    org_id = get_organization_id()
    channels = get_channel_ids(org_id)

    if not channels:
        print("No connected channels found - connect a channel in Buffer first.")
        return

    for meta in metadata:
        if "video_url" not in meta:
            print(f"Skipping {meta['clip_id']}: no public video_url set. "
                  f"Upload {meta.get('final_path')} somewhere public first.")
            continue

        caption = f"{meta['title']}\n\n{' '.join(meta['hashtags'])}"
        print(f"Publishing clip {meta['clip_id']}: {meta['title']}")

        for ch in channels:
            create_video_post(
                channel_id=ch["id"],
                service=ch["service"],
                title=meta["title"],
                text=caption,
                video_url=meta["video_url"]
            )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python publish.py <metadata_json>")
        sys.exit(1)
    main(sys.argv[1])
