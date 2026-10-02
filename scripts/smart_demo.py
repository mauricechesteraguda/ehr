#!/usr/bin/env python3
"""Minimal dependency-free SMART client: exchange PKCE code, refresh, and read FHIR Patient.

The browser consent step is intentionally human-controlled. Pass values printed by the
local demo walkthrough; this client never prints token material or response payloads.
"""
import argparse
import json
import urllib.parse
import urllib.request


def post(url, values):
    request = urllib.request.Request(url, data=urllib.parse.urlencode(values).encode(), method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://localhost:8000")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--verifier", required=True)
    parser.add_argument("--redirect-uri", default="https://localhost/callback")
    parser.add_argument("--patient", default="P001")
    args = parser.parse_args()
    token = post(f"{args.base_url}/oauth/token/", {"grant_type": "authorization_code", "client_id": args.client_id, "client_secret": args.client_secret, "code": args.code, "redirect_uri": args.redirect_uri, "code_verifier": args.verifier})
    print("authorization-code exchange: success; access and refresh tokens held in memory")
    rotated = post(f"{args.base_url}/oauth/token/", {"grant_type": "refresh_token", "client_id": args.client_id, "client_secret": args.client_secret, "refresh_token": token["refresh_token"]})
    request = urllib.request.Request(f"{args.base_url}/fhir/R4/Patient/{urllib.parse.quote(args.patient)}")
    request.add_header("Authorization", f"Bearer {rotated['access_token']}")
    with urllib.request.urlopen(request) as response:
        body = json.load(response)
    print(f"refresh: success; FHIR Patient read: {body.get('resourceType')} {body.get('id', args.patient)}")


if __name__ == "__main__":
    main()
