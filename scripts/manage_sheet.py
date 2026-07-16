#!/usr/bin/env python3
"""
manage_sheet.py

Two subcommands, sharing one Google Sheets auth setup:

  prepare      Pick N site names from the "Pages Names" tab (or a manual
               comma-separated list), skip ones already used, write a JSON
               array to GITHUB_OUTPUT as `matrix` for a workflow matrix job.

  append-url   Append one [site name, url, timestamp] row to "Pages Urls".

Auth (the script tries these in order, using whichever secret is set):

  1. GOOGLE_SERVICE_ACCOUNT_JSON
     A real service-account key file's contents (has "client_email" and
     "private_key" fields).

  2. GOOGLE_OAUTH_JSON
     One combined JSON secret shaped like:
       {
         "refresh_token": "...",
         "client_id": "...",
         "client_secret": "...",
         "token_uri": "https://oauth2.googleapis.com/token"  (optional)
       }
     ("token"/"expiry"/"scopes"/"account"/"universe_domain" fields, if present,
     are ignored -- only refresh_token/client_id/client_secret/token_uri matter,
     since the access token itself is re-derived from the refresh token.)

  3. GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REFRESH_TOKEN
     The same OAuth credential, split across three separate secrets instead of
     one JSON blob.
"""

import argparse
import datetime
import json
import os
import re
import sys

from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request as AuthRequest
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
NAMES_TAB = "Pages Names"
URLS_TAB = "Pages Urls"


def _oauth_creds_from_parts(client_id, client_secret, refresh_token, token_uri=None):
    creds = OAuthCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=token_uri or "https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(AuthRequest())
    return creds


def get_sheets_service():
    sa_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    oauth_json_raw = os.environ.get("GOOGLE_OAUTH_JSON")
    oauth_client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    oauth_client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    oauth_refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")

    if sa_raw:
        info = json.loads(sa_raw)
        if "client_email" not in info or "private_key" not in info:
            sys.exit(
                "GOOGLE_SERVICE_ACCOUNT_JSON doesn't look like a service account key "
                "(missing client_email/private_key). If this is actually an OAuth "
                "user credential, put it in GOOGLE_OAUTH_JSON instead."
            )
        creds = ServiceAccountCredentials.from_service_account_info(info, scopes=SCOPES)

    elif oauth_json_raw:
        info = json.loads(oauth_json_raw)
        missing = [k for k in ("client_id", "client_secret", "refresh_token") if not info.get(k)]
        if missing:
            sys.exit(f"GOOGLE_OAUTH_JSON is missing required field(s): {', '.join(missing)}")
        creds = _oauth_creds_from_parts(
            client_id=info["client_id"],
            client_secret=info["client_secret"],
            refresh_token=info["refresh_token"],
            token_uri=info.get("token_uri"),
        )

    elif oauth_client_id and oauth_client_secret and oauth_refresh_token:
        creds = _oauth_creds_from_parts(oauth_client_id, oauth_client_secret, oauth_refresh_token)

    else:
        sys.exit(
            "No Google credentials found. Set one of: GOOGLE_SERVICE_ACCOUNT_JSON, "
            "GOOGLE_OAUTH_JSON (combined blob), or the three GOOGLE_OAUTH_CLIENT_ID / "
            "GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REFRESH_TOKEN secrets."
        )

    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def slugify(name, fallback_index):
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "").strip().lower())
    slug = slug.strip("-")
    return slug or f"site-{fallback_index}"


def read_column_a(service, spreadsheet_id, tab_name):
    try:
        resp = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{tab_name}!A:A")
            .execute()
        )
    except Exception:
        return []
    values = resp.get("values", [])
    return [row[0].strip() for row in values if row and row[0].strip()]


def cmd_prepare(args):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    num_pages = int(os.environ.get("NUM_PAGES", "1"))
    name_source = os.environ.get("NAME_SOURCE", "from_sheet")
    manual_names = [s.strip() for s in os.environ.get("MANUAL_NAMES", "").split(",") if s.strip()]
    base_site_name = os.environ.get("BASE_SITE_NAME", "site")

    if num_pages < 1:
        sys.exit("NUM_PAGES must be >= 1")

    service = get_sheets_service()

    if name_source == "manual":
        candidates = manual_names
    else:
        all_names = read_column_a(service, spreadsheet_id, NAMES_TAB)
        if all_names and re.search(r"name", all_names[0], re.IGNORECASE):
            all_names = all_names[1:]
        used_names = set(read_column_a(service, spreadsheet_id, URLS_TAB))
        candidates = [n for n in all_names if n not in used_names]

    picked = []
    for i in range(num_pages):
        if i < len(candidates):
            picked.append(candidates[i])
        else:
            picked.append(f"{base_site_name}-{int(datetime.datetime.now().timestamp())}-{i}")

    slugs = [slugify(n, i) for i, n in enumerate(picked)]

    print("Picked names:", picked)
    print("Slugs:", slugs)

    matrix = json.dumps(slugs)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"matrix={matrix}\n")
    else:
        print(f"matrix={matrix}")


def cmd_append_url(args):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    site_name = os.environ["SITE_NAME"]
    site_url = os.environ["SITE_URL"]

    service = get_sheets_service()
    row = [[site_name, site_url, datetime.datetime.utcnow().isoformat() + "Z"]]

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{URLS_TAB}!A:C",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": row},
    ).execute()

    print(f'Appended {site_name} -> {site_url} to "{URLS_TAB}"')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("append-url")
    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "append-url":
        cmd_append_url(args)


if __name__ == "__main__":
    main()
