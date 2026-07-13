"""YouTube research/monitoring engine for the YouTube MCP server.

Zero external dependencies — talks to the official YouTube Data API v3 over HTTPS
with the standard library only. Set YOUTUBE_API_KEY in the environment (get one
free at https://console.cloud.google.com → enable "YouTube Data API v3").

Every function returns compact, LLM-friendly dicts (not raw API payloads) so an
AI agent can use the result directly. Quota cost per call is noted in each
docstring — YouTube gives 10,000 free units/day.
"""
import os
import json
import urllib.parse
import urllib.request
import urllib.error

API = "https://www.googleapis.com/youtube/v3/"


class YouTubeError(Exception):
    pass


def _key():
    k = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not k:
        raise YouTubeError(
            "YOUTUBE_API_KEY is not set. Get a free key at "
            "https://console.cloud.google.com (enable 'YouTube Data API v3'), "
            "then export YOUTUBE_API_KEY=your_key")
    return k


def _api(endpoint, params):
    q = dict(params)
    q["key"] = _key()
    url = API + endpoint + "?" + urllib.parse.urlencode(q, doseq=True)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        msg = body
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            pass
        raise YouTubeError("YouTube API error %s: %s" % (e.code, msg))
    except urllib.error.URLError as e:
        raise YouTubeError("network error reaching YouTube API: %s" % e.reason)


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _idlist(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x).strip() for x in v if str(x).strip()]


def _watch(vid):
    return "https://www.youtube.com/watch?v=" + (vid or "")


def _channel_selector(channel):
    """Build the channels.list selector param for a channel ID (UC…) or @handle."""
    channel = (channel or "").strip()
    if not channel:
        raise YouTubeError("channel is required (channel ID like 'UC…' or a @handle)")
    if channel.startswith("UC") and len(channel) >= 20:
        return {"id": channel}
    if channel.startswith("@"):
        return {"forHandle": channel}
    return {"forHandle": "@" + channel}


# ---- tools ----
def search(query, max_results=10, order="relevance", published_after=None, region=None):
    """Search YouTube videos by keyword. Quota: 100 units.

    order: relevance | date | viewCount | rating | title
    published_after: ISO8601 UTC, e.g. '2026-01-01T00:00:00Z' (only newer videos).
    region: ISO 3166-1 alpha-2 country code (e.g. 'US', 'KR')."""
    if not (query or "").strip():
        raise YouTubeError("query is required")
    max_results = max(1, min(int(max_results or 10), 50))
    p = {"part": "snippet", "q": query, "type": "video",
         "maxResults": max_results, "order": order or "relevance"}
    if published_after:
        p["publishedAfter"] = published_after
    if region:
        p["regionCode"] = region
    d = _api("search", p)
    out = []
    for it in d.get("items", []):
        sn = it.get("snippet", {})
        vid = it.get("id", {}).get("videoId")
        out.append({
            "video_id": vid,
            "title": sn.get("title"),
            "channel": sn.get("channelTitle"),
            "channel_id": sn.get("channelId"),
            "published_at": sn.get("publishedAt"),
            "description": sn.get("description"),
            "url": _watch(vid),
        })
    return {"query": query, "count": len(out), "results": out}


def video_stats(video_ids):
    """Stats for one or more videos (views/likes/comments/duration/tags). Quota: 1 unit.

    video_ids: a list or comma-separated string of video IDs, up to 50."""
    ids = _idlist(video_ids)
    if not ids:
        raise YouTubeError("video_ids is required (list or comma-separated string)")
    d = _api("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids[:50])})
    out = []
    for it in d.get("items", []):
        sn = it.get("snippet", {})
        st = it.get("statistics", {})
        cd = it.get("contentDetails", {})
        vid = it.get("id")
        out.append({
            "video_id": vid,
            "title": sn.get("title"),
            "channel": sn.get("channelTitle"),
            "channel_id": sn.get("channelId"),
            "published_at": sn.get("publishedAt"),
            "views": _int(st.get("viewCount")),
            "likes": _int(st.get("likeCount")),
            "comments": _int(st.get("commentCount")),
            "duration": cd.get("duration"),
            "tags": sn.get("tags", []),
            "url": _watch(vid),
        })
    return {"count": len(out), "videos": out}


def channel_stats(channel):
    """Channel stats (subscribers/video count/total views). Quota: 1 unit.

    channel: channel ID (starts 'UC…') or a @handle."""
    p = {"part": "snippet,statistics"}
    p.update(_channel_selector(channel))
    d = _api("channels", p)
    items = d.get("items", [])
    if not items:
        raise YouTubeError("channel not found: %s" % channel)
    it = items[0]
    sn = it.get("snippet", {})
    st = it.get("statistics", {})
    return {
        "channel_id": it.get("id"),
        "title": sn.get("title"),
        "description": sn.get("description"),
        "published_at": sn.get("publishedAt"),
        "subscribers": _int(st.get("subscriberCount")),
        "videos": _int(st.get("videoCount")),
        "total_views": _int(st.get("viewCount")),
        "url": "https://www.youtube.com/channel/" + (it.get("id") or ""),
    }


def channel_videos(channel, max_results=10):
    """Most recent uploads from a channel. Quota: ~2 units.

    channel: channel ID (starts 'UC…') or a @handle."""
    max_results = max(1, min(int(max_results or 10), 50))
    p = {"part": "contentDetails"}
    p.update(_channel_selector(channel))
    d = _api("channels", p)
    items = d.get("items", [])
    if not items:
        raise YouTubeError("channel not found: %s" % channel)
    uploads = (items[0].get("contentDetails", {})
               .get("relatedPlaylists", {}).get("uploads"))
    if not uploads:
        raise YouTubeError("no uploads playlist for channel: %s" % channel)
    pl = _api("playlistItems", {"part": "snippet,contentDetails",
                                "playlistId": uploads, "maxResults": max_results})
    out = []
    for it in pl.get("items", []):
        sn = it.get("snippet", {})
        cd = it.get("contentDetails", {})
        vid = cd.get("videoId")
        out.append({
            "video_id": vid,
            "title": sn.get("title"),
            "published_at": cd.get("videoPublishedAt") or sn.get("publishedAt"),
            "description": sn.get("description"),
            "url": _watch(vid),
        })
    return {"channel": channel, "count": len(out), "videos": out}


def comments(video_id, max_results=20, order="relevance"):
    """Top-level comments on a video. Quota: 1 unit.

    order: relevance | time. (Fails if the video has comments disabled.)"""
    video_id = (video_id or "").strip()
    if not video_id:
        raise YouTubeError("video_id is required")
    max_results = max(1, min(int(max_results or 20), 100))
    d = _api("commentThreads", {"part": "snippet", "videoId": video_id,
                                "maxResults": max_results, "order": order or "relevance",
                                "textFormat": "plainText"})
    out = []
    for it in d.get("items", []):
        c = (it.get("snippet", {}).get("topLevelComment", {}).get("snippet", {}))
        out.append({
            "author": c.get("authorDisplayName"),
            "text": c.get("textDisplay"),
            "likes": _int(c.get("likeCount")),
            "published_at": c.get("publishedAt"),
        })
    return {"video_id": video_id, "count": len(out), "comments": out}


def trending(region="US", category_id=None, max_results=10):
    """Most popular (trending) videos in a region. Quota: 1 unit.

    region: ISO 3166-1 alpha-2 country code (e.g. 'US', 'KR').
    category_id: optional YouTube category ID to narrow the chart."""
    max_results = max(1, min(int(max_results or 10), 50))
    p = {"part": "snippet,statistics", "chart": "mostPopular",
         "regionCode": (region or "US"), "maxResults": max_results}
    if category_id:
        p["videoCategoryId"] = str(category_id)
    d = _api("videos", p)
    out = []
    for it in d.get("items", []):
        sn = it.get("snippet", {})
        st = it.get("statistics", {})
        vid = it.get("id")
        out.append({
            "video_id": vid,
            "title": sn.get("title"),
            "channel": sn.get("channelTitle"),
            "published_at": sn.get("publishedAt"),
            "views": _int(st.get("viewCount")),
            "likes": _int(st.get("likeCount")),
            "url": _watch(vid),
        })
    return {"region": region or "US", "count": len(out), "videos": out}
