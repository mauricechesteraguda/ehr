"""Run the human-approved SMART PKCE demo exchange against a local deployment."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand, CommandError


def _post(url: str, values: dict[str, str]) -> dict[str, object]:
    """Exchange form data without logging credentials, tokens, or clinical payloads."""
    request = urllib.request.Request(url, data=urllib.parse.urlencode(values).encode(), method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except Exception as exc:
        raise CommandError(f"SMART demo request failed: {type(exc).__name__}") from exc


class Command(BaseCommand):
    help = "Complete a local SMART PKCE exchange and bounded synthetic Patient read."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--base-url", default="https://localhost:8000")
        parser.add_argument("--client-id", required=True)
        parser.add_argument("--client-secret", required=True)
        parser.add_argument("--code", required=True)
        parser.add_argument("--verifier", required=True)
        parser.add_argument("--redirect-uri", default="https://localhost/callback")
        parser.add_argument("--patient", default="P001")

    def handle(self, *args: object, **options: str) -> None:
        """Run the documented demo while retaining tokens only in memory."""
        token = _post(f"{options['base_url']}/oauth/token/", {"grant_type": "authorization_code", "client_id": options["client_id"], "client_secret": options["client_secret"], "code": options["code"], "redirect_uri": options["redirect_uri"], "code_verifier": options["verifier"]})
        self.stdout.write("authorization-code exchange: success; access and refresh tokens held in memory")
        rotated = _post(f"{options['base_url']}/oauth/token/", {"grant_type": "refresh_token", "client_id": options["client_id"], "client_secret": options["client_secret"], "refresh_token": str(token["refresh_token"])})
        request = urllib.request.Request(f"{options['base_url']}/fhir/R4/Patient/{urllib.parse.quote(options['patient'])}")
        request.add_header("Authorization", f"Bearer {rotated['access_token']}")
        try:
            with urllib.request.urlopen(request) as response:
                body = json.load(response)
        except Exception as exc:
            raise CommandError(f"SMART Patient read failed: {type(exc).__name__}") from exc
        self.stdout.write(f"refresh: success; FHIR Patient read: {body.get('resourceType')} {body.get('id', options['patient'])}")
