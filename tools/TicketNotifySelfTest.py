"""gotify 推送自检：发一条测试消息 + 用 client token 回读确认

用法（在 lobeai 目录下）：
    /root/miniforge3/envs/lobe/bin/python -m tools.TicketNotifySelfTest            # 发送并回读
    /root/miniforge3/envs/lobe/bin/python -m tools.TicketNotifySelfTest --level high
    /root/miniforge3/envs/lobe/bin/python -m tools.TicketNotifySelfTest --read-only # 只看最近消息

说明：
- app token / client token 都从 config.yaml 解密密文读取，脚本内不写任何明文。
- 服务端本地（server a）用 127.0.0.1:25800；在代码服务器上验证会走公网 url（见 config_dev.yaml）。
"""
from __future__ import annotations

import argparse
import datetime
import sys

import requests

from tools.ConfigManager import get_env
from tools.TicketNotifier import PRIORITY, _base_url, _client_token, _token, enabled


def _read_recent(client: str, limit: int = 1) -> list:
    resp = requests.get(
        f"{_base_url()}/message",
        params={"token": client, "limit": limit},
        timeout=8,
    )
    resp.raise_for_status()
    return resp.json().get("messages", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="normal", choices=list(PRIORITY))
    ap.add_argument("--read-only", action="store_true", help="只回读，不发送")
    ap.add_argument("--client", default="", help="指定 client 名（默认取第一个）")
    args = ap.parse_args()

    print(f"ENV            = {get_env('ENV', '(prod)')}")
    print(f"gotify.url     = {_base_url()}")
    print(f"gotify.enabled = {enabled()}")

    client = _client_token(args.client)
    print(f"client token   = {'已解密(' + str(len(client)) + '字符)' if client else '缺失'}")

    if not args.read_only:
        app = _token()
        print(f"app token      = {'已解密(' + str(len(app)) + '字符)' if app else '缺失'}")
        if not app:
            print("❌ 没有 app token，无法发送")
            return 1
        title = f"【自检】工单通知链路 {datetime.datetime.now():%m-%d %H:%M:%S}"
        body = f"level={args.level} priority={PRIORITY[args.level]}\n如果你在 gotify 里看到这条，说明推送链路通。"
        if not enabled():
            print("⚠️  gotify.enabled=false，_send 会直接跳过；这里强制发送一次")
        resp = requests.post(
            f"{_base_url()}/message",
            headers={"X-Gotify-Key": app},
            json={"title": title, "message": body, "priority": PRIORITY[args.level]},
            timeout=8,
        )
        print(f"POST /message  = {resp.status_code} {resp.text[:120]}")
        if resp.status_code >= 300:
            return 1

    if not client:
        print("⚠️  没有 client token，跳过回读")
        return 0
    try:
        msgs = _read_recent(client, 1)
    except requests.RequestException as e:
        print(f"❌ 回读失败: {e}")
        return 1
    if not msgs:
        print("❌ 回读为空：消息没进服务器（检查 app token 权限/是否被删）")
        return 1
    m = msgs[0]
    print(f"回调最近消息   = id={m.get('id')} priority={m.get('priority')} title={m.get('title')}")
    print("✅ 推送链路正常" if m.get("title", "").startswith("【自检】") or args.read_only else "⚠️  最近一条不是本次自检消息")
    return 0


if __name__ == "__main__":
    sys.exit(main())
