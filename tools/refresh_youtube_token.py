"""
YouTube OAuth 토큰 갱신 + GitHub Secret 자동 업데이트
=======================================================
사용법:
  1. pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
  2. python tools/refresh_youtube_token.py

필요 환경변수 (또는 실행 전 직접 입력):
  YOUTUBE_TOKEN   : 현재 token.json 내용 (JSON 문자열)
  GITHUB_TOKEN    : workflow 권한이 있는 GitHub PAT
  GITHUB_REPO     : 저장소 (예: username/AutoNews)
"""

import os
import json
import sys

# ── google-auth ──────────────────────────────────────
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
except ImportError:
    sys.exit("google-auth 미설치: pip install google-auth google-auth-httplib2 google-api-python-client")

# ── requests ─────────────────────────────────────────
try:
    import requests
except ImportError:
    sys.exit("requests 미설치: pip install requests")


def refresh_token(token_json_str: str) -> tuple[str, bool]:
    """액세스 토큰 갱신. (새 JSON 문자열, 갱신 여부) 반환"""
    creds = Credentials.from_authorized_user_info(json.loads(token_json_str))
    refreshed = False

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("🔑 토큰 만료됨 → 갱신 중...")
            creds.refresh(Request())
            refreshed = True
            print("   ✅ 갱신 완료")
        else:
            raise RuntimeError("refresh_token이 없습니다. OAuth 인증을 처음부터 다시 진행하세요.")
    else:
        print("✅ 토큰이 아직 유효합니다.")

    new_json = json.dumps({
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes) if creds.scopes else [],
        "expiry":        creds.expiry.isoformat() if creds.expiry else None,
    })
    return new_json, refreshed


def update_github_secret(repo: str, token: str, secret_name: str, secret_value: str):
    """GitHub Secret 업데이트 (sodium/libsodium 암호화)"""
    try:
        from base64 import b64encode
        from nacl import encoding, public  # type: ignore
    except ImportError:
        print("⚠️  PyNaCl 미설치 — GitHub Secret 자동 업데이트 건너뜀")
        print("   pip install PyNaCl 후 재실행하거나, 아래 값을 수동으로 붙여넣으세요.")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # 1. 공개키 가져오기
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=headers)
    r.raise_for_status()
    pub = r.json()
    key_id, key_b64 = pub["key_id"], pub["key"]

    # 2. 암호화
    pk = public.PublicKey(key_b64.encode(), encoding.Base64Encoder())
    box = public.SealedBox(pk)
    encrypted = b64encode(box.encrypt(secret_value.encode())).decode()

    # 3. Secret 업데이트
    r2 = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key_id},
    )
    if r2.status_code in (201, 204):
        print(f"   ✅ GitHub Secret '{secret_name}' 업데이트 완료")
        return True
    else:
        print(f"   ⚠️  Secret 업데이트 실패: {r2.status_code} {r2.text}")
        return False


def main():
    # ── 입력 ─────────────────────────────────────────
    token_json = os.environ.get("YOUTUBE_TOKEN") or input("YOUTUBE_TOKEN (token.json 내용 붙여넣기): ").strip()
    github_token = os.environ.get("GITHUB_TOKEN") or input("GitHub PAT (workflow 권한): ").strip()
    repo = os.environ.get("GITHUB_REPO") or input("GitHub 저장소 (예: username/AutoNews): ").strip()

    # ── 갱신 ─────────────────────────────────────────
    new_json, refreshed = refresh_token(token_json)

    if refreshed:
        print("\n📋 새 YOUTUBE_TOKEN 값 (GitHub Secret에 수동 붙여넣기용):")
        print("-" * 60)
        print(new_json)
        print("-" * 60)

        # ── GitHub Secret 자동 업데이트 ─────────────────
        if github_token and repo:
            print("\n🔄 GitHub Secret 자동 업데이트 시도 중...")
            update_github_secret(repo, github_token, "YOUTUBE_TOKEN", new_json)
        else:
            print("\n⚠️  GitHub Token/Repo 미입력 — 위 JSON을 수동으로 Secret에 붙여넣으세요.")
    else:
        print("토큰이 유효하므로 업데이트 불필요합니다.")


if __name__ == "__main__":
    main()
