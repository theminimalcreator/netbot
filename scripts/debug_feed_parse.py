#!/usr/bin/env python3
"""
Diagnose why _parse_feed_post returns None for all posts.
Reads the debug HTML snapshot and generates a CSV with parse details.
"""
import sys, os, re, csv
from pathlib import Path

# Find the latest debug snapshot
files = sorted(Path(".").glob("debug_feed_snapshot_*.html"), reverse=True)
if not files:
    print("❌ No debug_feed_snapshot_*.html found!")
    sys.exit(1)

html_file = files[0]
print(f"📄 Analyzing: {html_file}")

# We need to parse with a real browser to get the same DOM as Playwright
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Load the saved HTML
    abs_path = str(html_file.resolve())
    page.goto(f"file://{abs_path}")
    page.wait_for_load_state("domcontentloaded")
    
    # Find all feed-full-update elements
    posts = page.query_selector_all('[data-view-name="feed-full-update"]')
    print(f"Found {len(posts)} feed-full-update elements\n")
    
    rows = []
    
    for i, post in enumerate(posts[:90]):
        row = {
            "index": i,
            "has_urn": False,
            "urn": "",
            "urn_method": "",
            "has_author_link": False,
            "author_url": "",
            "author_aria": "",
            "author_text": "",
            "has_content": False,
            "content_preview": "",
            "is_sponsored": False,
            "parse_result": "UNKNOWN",
            "fail_reason": "",
        }
        
        # 1. Check URN
        urn = post.get_attribute("data-urn")
        if urn:
            row["has_urn"] = True
            row["urn"] = urn
            row["urn_method"] = "data-urn"
        
        if not urn:
            # Try data-id
            data_id = post.get_attribute("data-id")
            if data_id and data_id.isdigit():
                urn = f"urn:li:activity:{data_id}"
                row["has_urn"] = True
                row["urn"] = urn
                row["urn_method"] = "data-id"
        
        if not urn:
            # Try Buffer decode from parent
            try:
                decoded = post.evaluate("""(el) => {
                    let current = el.parentElement;
                    while (current && current !== document.body) {
                        const scope = current.getAttribute('data-view-tracking-scope');
                        if (scope) {
                            try {
                                const parsed = JSON.parse(scope);
                                for (const item of parsed) {
                                    if (item.breadcrumb && item.breadcrumb.content && item.breadcrumb.content.data) {
                                        const bytes = item.breadcrumb.content.data;
                                        const decoded = String.fromCharCode(...bytes);
                                        const match = decoded.match(/urn:li:activity:(\\d+)/);
                                        if (match) return { urn: match[0], method: 'buffer-decode' };
                                    }
                                }
                            } catch(e) {}
                        }
                        current = current.parentElement;
                    }
                    return null;
                }""")
                if decoded:
                    urn = decoded["urn"]
                    row["has_urn"] = True
                    row["urn"] = urn
                    row["urn_method"] = decoded["method"]
            except: pass
        
        if not urn:
            # Try link with urn
            try:
                link = post.query_selector('a[href*="urn:li:activity:"]')
                if link:
                    href = link.get_attribute("href")
                    match = re.search(r'urn:li:activity:(\d+)', href)
                    if match:
                        urn = f"urn:li:activity:{match.group(1)}"
                        row["has_urn"] = True
                        row["urn"] = urn
                        row["urn_method"] = "link-href"
            except: pass
        
        if not urn:
            # regex in outerHTML
            try:
                html = post.evaluate("el => el.outerHTML")
                match = re.search(r'urn:li:activity:(\d+)', html)
                if match:
                    urn = f"urn:li:activity:{match.group(1)}"
                    row["has_urn"] = True
                    row["urn"] = urn
                    row["urn_method"] = "regex-html"
            except: pass
        
        # Check sponsored
        try:
            html_snippet = post.evaluate("el => el.outerHTML.substring(0, 2000)")
            if '"isSponsored":true' in html_snippet or 'Promoted' in html_snippet:
                row["is_sponsored"] = True
        except: pass
        
        # 2. Author check
        author_link = post.query_selector('[data-view-name="feed-actor-image"]')
        if author_link:
            row["has_author_link"] = True
            href = author_link.get_attribute("href") or ""
            row["author_url"] = href.split("?")[0]
            row["author_aria"] = author_link.get_attribute("aria-label") or ""
        
        # Try legacy author
        actor = post.query_selector('.update-components-actor__name, span[dir="ltr"] > span[aria-hidden="true"]')
        if actor:
            try:
                row["author_text"] = actor.inner_text().split('\n')[0].strip()[:50]
            except: pass
        
        # 3. Content check
        commentary = post.query_selector('[data-view-name="feed-commentary"]')
        if commentary:
            try:
                text = commentary.inner_text().strip()
                row["has_content"] = bool(text)
                row["content_preview"] = text[:80].replace('\n', ' ')
            except: pass
        else:
            text_el = post.query_selector('.feed-shared-text, .update-components-text')
            if text_el:
                try:
                    text = text_el.inner_text().strip()
                    row["has_content"] = bool(text)
                    row["content_preview"] = text[:80].replace('\n', ' ')
                except: pass
        
        # Determine parse result
        if not row["has_urn"]:
            row["parse_result"] = "FAIL"
            row["fail_reason"] = "no_urn"
        elif "urn:li:activity" not in row["urn"]:
            row["parse_result"] = "FAIL" 
            row["fail_reason"] = "invalid_urn"
        elif row["is_sponsored"]:
            row["parse_result"] = "SKIP"
            row["fail_reason"] = "sponsored"
        elif not row["has_content"]:
            row["parse_result"] = "FAIL"
            row["fail_reason"] = "no_content"
        else:
            row["parse_result"] = "OK"
            row["fail_reason"] = ""
        
        rows.append(row)
    
    browser.close()

# Write CSV
csv_file = "debug_post_analysis.csv"
with open(csv_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

# Print summary
print(f"{'='*60}")
print(f"📊 ANALYSIS OF {len(rows)} POSTS")
print(f"{'='*60}")

ok = sum(1 for r in rows if r["parse_result"] == "OK")
fail = sum(1 for r in rows if r["parse_result"] == "FAIL")
skip = sum(1 for r in rows if r["parse_result"] == "SKIP")

print(f"\n  ✅ OK (would parse):  {ok}")
print(f"  ❌ FAIL:             {fail}")
print(f"  ⏭️  SKIP (sponsored): {skip}")

# Breakdown of failures
reasons = {}
for r in rows:
    if r["fail_reason"]:
        reasons[r["fail_reason"]] = reasons.get(r["fail_reason"], 0) + 1

print(f"\n  Failure reasons:")
for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f"    {reason}: {count}")

# Show first 5 OK posts
ok_posts = [r for r in rows if r["parse_result"] == "OK"]
if ok_posts:
    print(f"\n  First 5 OK posts:")
    for r in ok_posts[:5]:
        print(f"    [{r['index']}] {r['urn_method']} | {r['author_url'][:40]} | {r['content_preview'][:50]}")

# Show first 5 failed posts
fail_posts = [r for r in rows if r["parse_result"] == "FAIL"]
if fail_posts:
    print(f"\n  First 5 FAILED posts:")
    for r in fail_posts[:5]:
        print(f"    [{r['index']}] reason={r['fail_reason']} | urn_method={r['urn_method']} | urn={r['urn'][:40]} | content={r['content_preview'][:30]}")

print(f"\n📄 Full CSV: {csv_file}")
