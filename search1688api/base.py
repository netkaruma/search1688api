"""
Shared logic for sync/async 1688 sessions.
All I/O-independent methods live here.
Operation order is preserved 1:1 with the original working version.
"""

import json
import random
import string
import time
import urllib.parse
from typing import Dict, List

from .utils import (
    generate_sign,
)


class CookieDict(dict):
    """
    Dict that notifies an owner when a key is set manually.

    IMPORTANT:
    - __setitem__ (i.e. d['k'] = v) fires the hook → treated as USER action.
    - set_internal() bypasses the hook → used by the library itself
      (fallback generation, cookie re-collection) so it does NOT rebuild
      the signing token.
    """
    def __init__(self, on_set=None):
        super().__init__()
        self._on_set = on_set

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if self._on_set is not None:
            try:
                self._on_set(key, value)
            except Exception:
                pass

    def set_internal(self, key, value):
        """Write without firing the hook. Used by internal code paths."""
        dict.__setitem__(self, key, value)

    def update(self, *args, **kwargs):
        # Route updates through __setitem__ so user-driven updates fire the hook
        for k, v in dict(*args, **kwargs).items():
            self[k] = v


class Base1688Mixin:
    """
    Mixin with shared code. Contains no HTTP calls.

    Subclasses must implement:
        _collect_cookies_from_jar(url) -> None     # for aiohttp-style
        _collect_cookies_from_session() -> None    # for requests-style
    """

    # ------------------------------------------------------------------ #
    # Shared field initialization                                         #
    # ------------------------------------------------------------------ #
    def _base_init(self, debug: bool = True):
        self._token = None
        self._token_part = None
        # Raw _m_h5_tk that produced the current _token_part.
        self._token_part_source = None
        self.app_key = "12574478"
        self.base_url = (
            "https://h5api.m.1688.com/h5/mtop.relationrecommend."
            "wirelessrecommend.recommend/2.0/"
        )
        self._initialized = False
        # Cookie keys set manually by the user → protected from overwrite.
        self._overridden_cookies = set()
        self.cookies_dict = CookieDict(on_set=self._on_cookie_set)
        self.debug = debug

    # ------------------------------------------------------------------ #
    # Cookie hook                                                         #
    # ------------------------------------------------------------------ #
    def _on_cookie_set(self, key: str, value: str):
        """
        Fires only when cookies_dict[key] = value is written via __setitem__
        (i.e. by the user or by high-level library code that routes through it).

        Internal library code uses cookies_dict.set_internal() instead,
        so it never reaches this hook.
        """
        self._overridden_cookies.add(key)

        if key == "_m_h5_tk":
            if value:
                self._token = value
                self._token_part = value.split("_")[0] if "_" in value else value
                self._token_part_source = value
                self._log(f"Signing token manually set: {self._token_part}...")
            else:
                self._token = None
                self._token_part = None
                self._token_part_source = None
                self._log("Signing token manually cleared")

    # ------------------------------------------------------------------ #
    # Logging and cookie generation                                       #
    # ------------------------------------------------------------------ #
    def _log(self, message: str):
        if self.debug:
            print(message)

    def _generate_random_cookie_value(self, length: int = 16) -> str:
        chars = string.ascii_lowercase + string.digits
        return "".join(random.choice(chars) for _ in range(length))

    def _generate_fallback_cookies(self) -> Dict[str, str]:
        # NOTE: _m_h5_tk / _m_h5_tk_enc / cna are intentionally excluded.
        # They are issued by the API itself; fabricating them breaks signing.
        timestamp = str(int(time.time() * 1000))
        return {
            "t": self._generate_random_cookie_value(32),
            "_tb_token_": self._generate_random_cookie_value(13),
            "cookie2": self._generate_random_cookie_value(32),
        }

    def _use_fallback_cookies(self, missing_cookies):
        """
        Fill missing non-critical cookies with random values.

        - _m_h5_tk / _m_h5_tk_enc / cna are skipped: they MUST come from the server.
        - Uses set_internal() so fallback values are NOT marked as user-overridden
          and do NOT rebuild the signing token.
        """
        fallback_cookies = self._generate_fallback_cookies()
        skip_keys = {"_m_h5_tk", "_m_h5_tk_enc", "cna"}

        for cookie_name in missing_cookies:
            if cookie_name in skip_keys:
                self._log(f"Skipping fallback for {cookie_name} (must come from server)")
                continue
            if cookie_name in fallback_cookies:
                self.cookies_dict.set_internal(cookie_name, fallback_cookies[cookie_name])
                self._log(
                    f"Using generated fallback for {cookie_name}: "
                    f"{fallback_cookies[cookie_name][:30]}..."
                )

    def _reset_state(self):
        self._token = None
        self._token_part = None
        self._token_part_source = None
        self._initialized = False
        self._overridden_cookies = set()
        self.cookies_dict = CookieDict(on_set=self._on_cookie_set)

    # ------------------------------------------------------------------ #
    # Internal cookie write helper                                        #
    # ------------------------------------------------------------------ #
    def _set_cookie_internal(self, key: str, value: str):
        """Library-side cookie write: bypasses hook, not protected from overwrite."""
        self.cookies_dict.set_internal(key, value)

    def _set_token_internal(self, token: str):
        """
        Library-side token write (from server response).
        Does NOT mark _m_h5_tk as overridden, so a later real server token
        can replace it.
        """
        self._token = token
        self._token_part = token.split("_")[0] if "_" in token else token
        self._token_part_source = token
        self.cookies_dict.set_internal("_m_h5_tk", token)

    # ------------------------------------------------------------------ #
    # Token synchronization (safety net)                                  #
    # ------------------------------------------------------------------ #
    def _sync_token_from_cookies(self):
        """
        If cookies_dict['_m_h5_tk'] differs from the value that produced the
        current signature, rebuild _token_part.

        This is the safety net for the case where the user set the token
        before _token_part was initialized (e.g. before start()).
        """
        current = self.cookies_dict.get("_m_h5_tk")

        if current == self._token_part_source:
            return

        if not current:
            self._token = None
            self._token_part = None
            self._token_part_source = None
            self._log("Signing token cleared (no _m_h5_tk in cookies)")
            return

        self._token = current
        self._token_part = current.split("_")[0] if "_" in current else current
        self._token_part_source = current
        self._log(f"Signing token refreshed from _m_h5_tk: {self._token_part}...")

    # ------------------------------------------------------------------ #
    # Public token setter                                                 #
    # ------------------------------------------------------------------ #
    def set_token(self, token: str):
        """
        Explicitly override the signing token.

        - Rebuilds _token / _token_part immediately.
        - Marks _m_h5_tk as overridden so cookie re-collection won't overwrite it.
        - Mirrors into requests.Session.cookies when available.
        """
        if not token:
            raise ValueError("Token must not be empty")

        # Go through __setitem__ on purpose: this is a USER action.
        self.cookies_dict["_m_h5_tk"] = token

        # Mirror into the real requests cookie jar if available
        if hasattr(self, "cookies") and hasattr(self.cookies, "set"):
            try:
                self.cookies.set("_m_h5_tk", token, domain=".1688.com")
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Signature                                                           #
    # ------------------------------------------------------------------ #
    def _compute_sign(self, timestamp: str, data_string: str) -> str:
        """Single source of truth for token/sign selection."""
        # Safety net: pick up manual changes to cookies_dict['_m_h5_tk']
        self._sync_token_from_cookies()

        if self._token_part:
            return generate_sign(self._token_part, timestamp, self.app_key, data_string)

        if "_m_h5_tk" in self.cookies_dict:
            token_from_cookies = self.cookies_dict["_m_h5_tk"]
            token_part = (
                token_from_cookies.split("_")[0]
                if "_" in token_from_cookies
                else token_from_cookies
            )
            sign = generate_sign(token_part, timestamp, self.app_key, data_string)
            self._log("Using token from cookies for signing")
            return sign

        sign = generate_sign("fallback_token", timestamp, self.app_key, data_string)
        self._log("Using fallback token for signing")
        return sign

    # ------------------------------------------------------------------ #
    # Headers                                                             #
    # ------------------------------------------------------------------ #
    def _main_page_headers(self) -> Dict[str, str]:
        return {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "accept-encoding": "gzip, deflate, br",
            "dnt": "1",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "upgrade-insecure-requests": "1",
        }

    def _api_get_headers(self, referer: str, cookies_str: str) -> Dict[str, str]:
        return {
            "authority": "h5api.m.1688.com",
            "method": "GET",
            "scheme": "https",
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": cookies_str,
            "referer": referer,
            "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "script",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
            ),
        }

    def _cookies_str(self) -> str:
        self._sync_token_from_cookies()
        return "; ".join(f"{k}={v}" for k, v in self.cookies_dict.items())

    # ------------------------------------------------------------------ #
    # Request parameter builders                                          #
    # ------------------------------------------------------------------ #
    def _build_start_params(self) -> Dict[str, str]:
        return {
            "jsv": "2.7.2",
            "appKey": self.app_key,
            "t": str(int(time.time() * 1000)),
            "api": "mtop.relationrecommend.WirelessRecommend.recommend",
            "v": "2.0",
            "type": "originaljson",
        }

    def _build_image_upload_params(self, data_string: str):
        timestamp = str(int(time.time() * 1000))
        sign = self._compute_sign(timestamp, data_string)
        params = {
            "jsv": "2.7.2",
            "appKey": self.app_key,
            "t": timestamp,
            "sign": sign,
            "api": "mtop.relationrecommend.WirelessRecommend.recommend",
            "ignoreLogin": "true",
            "prefix": "h5api",
            "v": "2.0",
            "type": "originaljson",
            "dataType": "jsonp",
            "jsonpIncPrefix": "search1688",
            "timeout": "20000",
        }
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://s.1688.com",
            "referer": "https://s.1688.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        return params, headers

    def _build_image_search_request(self, image_id: str):
        params_data = {
            "beginPage": 1,
            "pageSize": 60,
            "method": "imageOfferSearchService",
            "searchScene": "pcImageSearch",
            "appName": "pctusou",
            "tab": "imageSearch",
            "imageId": image_id,
            "imageIdList": image_id,
            "spm": "a26352.13672862.imagesearch.upload",
        }
        request_data = {
            "appId": 32517,
            "params": json.dumps(params_data, ensure_ascii=False),
        }
        data_string = json.dumps(request_data, ensure_ascii=False)

        timestamp = str(int(time.time() * 1000))
        sign = self._compute_sign(timestamp, data_string)

        params = {
            "jsv": "2.7.2",
            "appKey": self.app_key,
            "t": timestamp,
            "sign": sign,
            "api": "mtop.relationrecommend.wirelessrecommend.recommend",
            "v": "2.0",
            "type": "jsonp",
            "dataType": "jsonp",
            "timeout": "20000",
            "jsonpIncPrefix": "reqTppId_32517_getOfferList",
            "callback": f"mtopjsonpreqTppId_32517_getOfferList{int(time.time())}",
            "data": data_string,
        }
        full_url = f"{self.base_url}?{urllib.parse.urlencode(params)}"

        referer = (
            "https://pages-fast.1688.com/wow/cbu/srch_rec/image_search/youyuan/"
            f"index.html?tab=imageSearch&imageId={image_id}&imageIdList={image_id}"
            "&spm=a26352.13672862.imagesearch.upload"
        )
        headers = self._api_get_headers(referer, self._cookies_str())
        return full_url, headers

    def _build_text_search_request(self, keywords: str):
        params_data = {
            "beginPage": 1,
            "pageSize": 60,
            "method": "getOfferList",
            "pageId": "qWJOoeNkRwblv903Iv6KQqPVkYDrgMudKHTRsee9Sjz7N9z1",
            "verticalProductFlag": "pcmarket",
            "searchScene": "pcOfferSearch",
            "charset": "GBK",
            "spm": "a26352.b28411319/2508.searchbox.0",
            "keywords": keywords,
        }
        request_data = {
            "appId": 32517,
            "params": json.dumps(params_data, ensure_ascii=False),
        }
        data_string = json.dumps(request_data, ensure_ascii=False)

        timestamp = str(int(time.time() * 1000))
        sign = self._compute_sign(timestamp, data_string)

        params = {
            "jsv": "2.7.4",
            "appKey": self.app_key,
            "t": timestamp,
            "sign": sign,
            "api": "mtop.relationrecommend.WirelessRecommend.recommend",
            "v": "2.0",
            "jsonpIncPrefix": "reqTppId_32517_getOfferList",
            "excludeKeys": "",
            "type": "jsonp",
            "dataType": "jsonp",
            "callback": f"mtopjsonpreqTppId_32517_getOfferList{int(time.time())}",
            "data": data_string,
        }
        full_url = f"{self.base_url}?{urllib.parse.urlencode(params)}"

        referer = (
            f"https://s.1688.com/selloffer/offer_search.htm?"
            f"keywords={urllib.parse.quote(keywords)}"
            "&spm=a26352.b28411319%2F2508.searchbox.0"
        )
        headers = self._api_get_headers(referer, self._cookies_str())
        return full_url, headers

    # ------------------------------------------------------------------ #
    # Response parsing                                                    #
    # ------------------------------------------------------------------ #
    def _parse_jsonp_response(self, response_text: str) -> List[Dict]:
        if not response_text:
            self._log("Failed to decode response")
            return []

        if not (response_text.startswith("mtopjsonp") or "mtopjsonp" in response_text):
            self._log("Invalid JSONP response format")
            return []

        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end == -1:
            return []

        json_str = response_text[json_start:json_end]
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            self._log(f"JSON decode error: {e}")
            return []

        if "ret" in result and not result.get("ret", ["SUCCESS"])[0].startswith("SUCCESS"):
            self._log(f"API returned error: {result.get('ret')}")
            return []

        return self._parse_api_products(result)

    def _parse_api_products(self, api_result: Dict) -> List[Dict]:
        products = []
        try:
            offer_data = api_result.get("data", {}).get("data", {}).get("OFFER", {})
            items = offer_data.get("items", [])
            if not items:
                self._log("No items found in API response")
                return []
            for item in items:
                try:
                    products.append(dict(item))
                except Exception as e:
                    self._log(f"Error parsing product item: {e}")
                    continue
        except Exception as e:
            self._log(f"Error parsing API products: {e}")
        return products

    def _decode_bytes(self, response_bytes: bytes, content_encoding: str) -> str:
        try:
            if "gzip" in content_encoding:
                import gzip
                return gzip.decompress(response_bytes).decode("utf-8")
            if "deflate" in content_encoding:
                import zlib
                return zlib.decompress(response_bytes).decode("utf-8")
            if "br" in content_encoding:
                try:
                    import brotli
                    return brotli.decompress(response_bytes).decode("utf-8")
                except ImportError:
                    self._log("Brotli compression not supported")
            if "zstd" in content_encoding:
                try:
                    import zstandard
                    dctx = zstandard.ZstdDecompressor()
                    return dctx.decompress(response_bytes).decode("utf-8")
                except ImportError:
                    self._log("Zstandard compression not supported")

            try:
                return response_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    return response_bytes.decode("latin-1")
                except UnicodeDecodeError:
                    return response_bytes.decode("cp1251")
        except Exception as e:
            self._log(f"Response decoding error: {e}")
            try:
                return response_bytes.decode("utf-8", errors="replace")
            except Exception:
                return None

    # ------------------------------------------------------------------ #
    # Cookie collection config                                            #
    # ------------------------------------------------------------------ #
    def _main_page_urls(self):
        return [
            "https://www.1688.com",
            "https://s.1688.com",
            "https://login.1688.com",
            "https://s.1688.com/selloffer/offer_search.htm?keywords=sample",
        ]

    def _important_cookies(self):
        # Only cookies that must exist *before* the API request.
        # _m_h5_tk / _m_h5_tk_enc / cna are issued by the API itself.
        return ["t", "_tb_token_", "cookie2"]

    def _check_missing_cookies(self):
        available = list(self.cookies_dict.keys())
        self._log(f"Available cookies: {available}")
        missing = [c for c in self._important_cookies() if c not in available]
        if missing:
            self._log(f"Missing important cookies: {missing}")
            return missing
        return []