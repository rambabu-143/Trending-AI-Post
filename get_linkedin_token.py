"""One-time helper: exchange a LinkedIn OAuth code for an access token + your author URN.

Usage:
    python get_linkedin_token.py

Prompts for your Client ID/Secret, prints an authorization URL to open in your
browser, then exchanges the code you get back for an access token and URN.
"""
import urllib.parse
import requests

REDIRECT_URI = "http://localhost:8080/callback"

client_id = input("LinkedIn Client ID: ").strip()
client_secret = input("LinkedIn Client Secret: ").strip()

auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
    "response_type": "code",
    "client_id": client_id,
    "redirect_uri": REDIRECT_URI,
    "scope": "openid profile w_member_social",
})
print(f"\n1. Open this URL, log in, and click Allow:\n{auth_url}\n")
print("2. You'll land on a broken localhost page — that's fine, copy the 'code' value from the URL bar.")
code = input("\nPaste the code here: ").strip()

token_resp = requests.post(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    },
    timeout=15,
)
token_resp.raise_for_status()
access_token = token_resp.json()["access_token"]

userinfo = requests.get(
    "https://api.linkedin.com/v2/userinfo",
    headers={"Authorization": f"Bearer {access_token}"},
    timeout=15,
).json()
urn = f"urn:li:person:{userinfo['sub']}"

print("\nDone. Add these as GitHub repo secrets:")
print(f"LINKEDIN_ACCESS_TOKEN = {access_token}")
print(f"LINKEDIN_AUTHOR_URN = {urn}")
print("\n(Token expires in ~60 days — rerun this script to refresh it.)")
