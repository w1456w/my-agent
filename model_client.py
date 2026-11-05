"""教师接入层：仅支持 Bearer 鉴权的 chat/completions 兼容接口。"""
import json
import math
from http.client import HTTPException
from urllib import request, error
from urllib.parse import urlsplit


class ModelError(RuntimeError):
    pass


def validate_endpoint(endpoint, label):
    if not isinstance(endpoint, str) or not endpoint:
        raise ModelError(f"{label} 须填写完整的 HTTPS 接口地址。")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in endpoint):
        raise ModelError(f"{label} 不能包含空白或控制字符。")
    try:
        endpoint.encode("ascii")
    except UnicodeError:
        raise ModelError(f"{label} 请使用已编码的完整 HTTPS 地址，不要包含未编码字符。") from None
    try:
        u = urlsplit(endpoint)
        port = u.port
        hostname = u.hostname
    except ValueError:
        raise ModelError(f"{label} 的地址或端口格式不正确。") from None
    if (u.scheme != "https" or not u.netloc or not hostname
            or u.username is not None or u.password is not None
            or "?" in endpoint or "#" in endpoint or "\\" in endpoint):
        raise ModelError(f"{label} 须为 HTTPS 地址，且不能包含账号、查询串或片段标记。")
    if u.netloc.endswith(":") or (port is not None and not 1 <= port <= 65535):
        raise ModelError(f"{label} 的端口须为 1 至 65535 的整数。")


def _reject_constant(value):
    raise ValueError("JSON不能包含非有限数值。")


def _parse_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON数值超出范围。")
    return number


def _is_finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and (isinstance(value, int) or math.isfinite(value)))


def _validate_generation_options(cfg):
    temperature = cfg.get("temperature")
    if temperature is not None and (not _is_finite_number(temperature) or temperature < 0):
        raise ModelError("temperature 须为 null 或非负有限数值。")
    max_tokens = cfg.get("max_tokens")
    if max_tokens is not None and (not isinstance(max_tokens, int)
                                   or isinstance(max_tokens, bool) or max_tokens < 1):
        raise ModelError("max_tokens 须为 null 或正整数。")


def load_config(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            cfg = json.load(f, parse_constant=_reject_constant, parse_float=_parse_float)
    except (OSError, ValueError):
        raise ModelError("请先创建有效的 config.json，按教师给定值填写。") from None
    if not isinstance(cfg, dict):
        raise ModelError("config.json 顶层必须是包含 endpoint 与 model 的对象。")
    endpoint = cfg.get("endpoint", "")
    model = cfg.get("model", "")
    validate_endpoint(endpoint, "endpoint")
    if not isinstance(model, str) or not model.strip():
        raise ModelError("model 须填写非空的模型名称。")
    timeout = cfg.get("timeout_seconds", 45)
    if not _is_finite_number(timeout) or not 1 <= timeout <= 120:
        raise ModelError("timeout_seconds 应为 1 至 120 的数值。")
    _validate_generation_options(cfg)
    return cfg


def make_payload(cfg, messages):
    _validate_generation_options(cfg)
    data = {"model": cfg["model"], "messages": messages, "stream": False}
    # 参数为 null 时不发送，避免假设所有学校模型支持相同采样参数。
    for key in ("temperature", "max_tokens"):
        if cfg.get(key) is not None:
            data[key] = cfg[key]
    return data


def parse_reply(data):
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ModelError("接口响应结构不符，请教师核对接入层。") from None
    if not isinstance(text, str) or not text.strip():
        raise ModelError("未收到非空文本回答，请教师核对模型及响应格式。")
    return text, data.get("usage")


def call_model(cfg, api_key, messages):
    validate_endpoint(cfg.get("endpoint", ""), "endpoint")
    if (not isinstance(api_key, str) or not api_key
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in api_key)):
        raise ModelError("API 密钥不能为空或包含空白、控制字符。")
    try:
        api_key.encode("ascii")
        payload = json.dumps(make_payload(cfg, messages), ensure_ascii=False,
                             allow_nan=False).encode("utf-8")
        req = request.Request(cfg["endpoint"], data=payload, method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + api_key})
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise ModelError("请求配置、消息或密钥格式不正确，请核对后重试。") from None
    # 不跟随重定向，避免把鉴权信息带到其他地址；不打印服务器原始报错。
    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=cfg.get("timeout_seconds", 45)) as resp:
            raw = resp.read()
    except error.HTTPError as exc:
        raise ModelError(f"HTTP {exc.code}，请按手册排查；本次未加入会话历史。") from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        raise ModelError("连接失败或超时；本次未加入会话历史。") from None
    except (TypeError, ValueError, UnicodeError):
        raise ModelError("请求地址或密钥格式不正确，请核对配置。") from None
    try:
        data = json.loads(raw.decode("utf-8-sig"), parse_constant=_reject_constant,
                          parse_float=_parse_float)
    except (ValueError, UnicodeError):
        raise ModelError("返回内容不是有效 JSON，请教师检查接口。") from None
    return parse_reply(data)
