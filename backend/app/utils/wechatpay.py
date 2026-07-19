"""
微信支付 V3 工具函数
- JSAPI 下单
- 签名 / 验签
- 回调解密
"""
import base64
import json
import os
import uuid
from typing import Optional

import httpx


def _ensure_cryptography():
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return hashes, serialization, padding, AESGCM
    except Exception as exc:
        raise RuntimeError(
            "微信支付需要 'cryptography' 依赖，请安装: pip install cryptography"
        ) from exc


def _load_private_key(pem_str: str):
    _, serialization, _, _ = _ensure_cryptography()
    return serialization.load_pem_private_key(pem_str.encode("utf-8"), password=None)


def _load_public_key(pem_str: str):
    _, serialization, _, _ = _ensure_cryptography()
    return serialization.load_pem_public_key(pem_str.encode("utf-8"))


# ── 签名 ─────────────────────────────────────────────
def generate_sign(method: str, url_path: str, body: str, timestamp: str, nonce: str, private_key_str: str) -> str:
    """商户请求签名 (RSA-SHA256)"""
    _, _, padding_mod, _ = _ensure_cryptography()
    message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"
    private_key = _load_private_key(private_key_str)
    signature = private_key.sign(
        message.encode("utf-8"),
        padding_mod.PKCS1v15(),
        _ensure_cryptography()[0](),
    )
    return base64.b64encode(signature).decode("utf-8")


def jsapi_pay_sign(app_id: str, time_stamp: str, nonce_str: str, package: str, private_key_str: str) -> str:
    """JSAPI 调起支付签名 (RSA-SHA256)"""
    _, _, padding_mod, _ = _ensure_cryptography()
    message = f"{app_id}\n{time_stamp}\n{nonce_str}\n{package}\n"
    private_key = _load_private_key(private_key_str)
    signature = private_key.sign(
        message.encode("utf-8"),
        padding_mod.PKCS1v15(),
        _ensure_cryptography()[0](),
    )
    return base64.b64encode(signature).decode("utf-8")


# ── 验签 ─────────────────────────────────────────────
def verify_notify_sign(headers: dict, body: str, platform_pub_key_str: Optional[str] = None) -> bool:
    """验证微信支付回调签名。未提供平台公钥时返回 True（跳过验签，框架就绪期）"""
    if not platform_pub_key_str:
        return True

    try:
        _, _, padding_mod, _ = _ensure_cryptography()
        timestamp = headers.get("Wechatpay-Timestamp", "")
        nonce = headers.get("Wechatpay-Nonce", "")
        signature_b64 = headers.get("Wechatpay-Signature", "")
        if not signature_b64:
            return False

        message = f"{timestamp}\n{nonce}\n{body}\n"
        public_key = _load_public_key(platform_pub_key_str)
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            message.encode("utf-8"),
            padding_mod.PKCS1v15(),
            _ensure_cryptography()[0](),
        )
        return True
    except Exception:
        return False


# ── 解密 ─────────────────────────────────────────────
def decrypt_notify_resource(ciphertext_b64: str, nonce: str, associated_data: str, api_v3_key: str) -> str:
    """AES-256-GCM 解密回调资源"""
    _, _, _, AESGCM = _ensure_cryptography()
    key = api_v3_key.encode("utf-8") if isinstance(api_v3_key, str) else api_v3_key
    nonce_bytes = nonce.encode("utf-8") if isinstance(nonce, str) else nonce
    ad_bytes = associated_data.encode("utf-8") if isinstance(associated_data, str) else associated_data

    data = base64.b64decode(ciphertext_b64)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce_bytes, data, ad_bytes)
    return plaintext.decode("utf-8")


# ── JSAPI 下单 ───────────────────────────────────────
async def create_jsapi_order(
    appid: str,
    mchid: str,
    serial_no: str,
    private_key_str: str,
    openid: str,
    order_no: str,
    amount_yuan: float,
    description: str,
    notify_url: str,
    attach: str = "",
) -> dict:
    """
    调用微信 V3 JSAPI 下单，返回 prepay_id 等原始响应。
    金额单位为元，内部自动转分。
    """
    url_path = "/v3/pay/transactions/jsapi"
    url = f"https://api.mch.weixin.qq.com{url_path}"
    nonce = uuid.uuid4().hex[:16]
    timestamp = str(int(__import__("time").time()))

    amount_cents = int(round(amount_yuan * 100))
    payload = {
        "appid": appid,
        "mchid": mchid,
        "description": description,
        "out_trade_no": order_no,
        "notify_url": notify_url,
        "attach": attach,
        "amount": {"total": amount_cents, "currency": "CNY"},
        "payer": {"openid": openid},
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    signature = generate_sign("POST", url_path, body, timestamp, nonce, private_key_str)

    headers = {
        "Authorization": f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",nonce_str="{nonce}",signature="{signature}",timestamp="{timestamp}",serial_no="{serial_no}"',
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, content=body.encode("utf-8"), headers=headers)
        result = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(f"微信下单失败 [{resp.status_code}]: {result}")
        return result


# ── 辅助：读取私钥文件 ───────────────────────────────
def load_private_key_from_path(path: str) -> str:
    """从文件读取私钥 PEM 文本"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
