"""
大象群消息发送模块 - 通过机器人 API 发送群消息
支持 AI Eric / 天天助理 / 灰灰情报官 三个机器人
"""
import json
import time
import base64
import hmac
import hashlib
import urllib.request
import urllib.parse

# 机器人配置
ROBOTS = {
    "ai_eric": {
        "client_id": "65a6eb395a",
        "client_secret": "af11f08569d34d4a93a25f06688c74ef",
    },
    "tiantian": {
        "client_id": "190b655731",
        "client_secret": "020b1ee49a6146dea3e9806dc0e142f5",
    },
    "huihui": {
        "client_id": "737a74cd12",
        "client_secret": "34d82b3ef8c14b06ba1dbfff097e7a29",
    },
}

DEFAULT_GROUP = "70415285284"  # SP Metropolitan CM


def _make_jwt(client_id, client_secret):
    """Generate client_secret_jwt (HS256) for SSO authentication."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": "https://ssosv.sankuai.com/oauth/token",
        "exp": now + 300,
        "iat": now,
        "jti": str(now),
    }

    def b64url(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    h = b64url(header)
    p = b64url(payload)
    signing_input = f"{h}.{p}".encode()
    sig = base64.urlsafe_b64encode(
        hmac.new(client_secret.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{h}.{p}.{sig}"


def get_dx_token(robot="ai_eric"):
    """Get access token via client_credentials + token exchange."""
    cfg = ROBOTS[robot]
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]

    # Step 1: client_credentials
    jwt = _make_jwt(client_id, client_secret)
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": jwt,
        "scope": "openid",
    }).encode()

    req = urllib.request.Request(
        "https://ssosv.sankuai.com/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_resp = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()[:500]}")
        raise
    access_token = token_resp.get("access_token")
    if not access_token:
        print(f"Token response: {token_resp}")
        raise ValueError("No access_token in response")

    # Step 2: Token exchange for xm-xai audience
    exchange_data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "client_id": client_id,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": jwt,
        "subject_token": access_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": "xm-xai",
    }).encode()

    req2 = urllib.request.Request(
        "https://ssosv.sankuai.com/oauth/token",
        data=exchange_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            exchange_resp = json.loads(resp2.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()[:500]}")
        raise
    return exchange_resp.get("access_token")


def send_group_msg(content, group_id=None, robot="ai_eric"):
    """Send text message to group via robot API."""
    if group_id is None:
        group_id = DEFAULT_GROUP

    token = get_dx_token(robot)
    body = json.dumps({
        "gid": group_id,
        "msgType": "text",
        "body": {"text": content},
    }).encode()

    req = urllib.request.Request(
        "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()[:500]}")
        raise
    return result


def send_group_image(image_url, group_id=None, robot="ai_eric"):
    """Send image message to group via robot API."""
    if group_id is None:
        group_id = DEFAULT_GROUP

    token = get_dx_token(robot)
    body = json.dumps({
        "gid": group_id,
        "msgType": "image",
        "body": {
            "url": image_url,
            "thumbnail": image_url,
            "normal": image_url,
            "original": image_url,
        },
    }).encode()

    req = urllib.request.Request(
        "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()[:500]}")
        raise
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python cap001_dx_group_msg.py <message> [group_id] [robot]")
        sys.exit(1)

    msg = sys.argv[1]
    gid = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_GROUP
    bot = sys.argv[3] if len(sys.argv) > 3 else "ai_eric"

    result = send_group_msg(msg, gid, bot)
    print(json.dumps(result, indent=2))
