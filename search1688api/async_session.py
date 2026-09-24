"""
Async 1688 session. All aiohttp specifics live here.
Operation order is preserved 1:1 with the original working version.
"""

import urllib.parse
from typing import Dict, List

import aiohttp
from yarl import URL

from .base import Base1688Mixin
from .utils import (
    prepare_image_request,
    read_and_encode_image,
    extract_products_from_html,
)


class Async1688Session(Base1688Mixin, aiohttp.ClientSession):
    def __init__(self, *args, debug: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_init(debug=debug)

    # ------------------------------------------------------------------ #
    # Context manager                                                     #
    # ------------------------------------------------------------------ #
    async def __aenter__(self):
        if not self._initialized:
            await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ------------------------------------------------------------------ #
    # Cookie jar helpers                                                  #
    # ------------------------------------------------------------------ #
    async def _collect_cookies_from_jar(self, url: str):
        url_obj = URL(url)
        cookies = self.cookie_jar.filter_cookies(url_obj)
        for cookie_name, cookie_obj in cookies.items():
            # Never overwrite cookies the user set manually
            if cookie_name in self._overridden_cookies:
                continue
            # Server-side write, do not fire the hook
            self.cookies_dict.set_internal(cookie_name, cookie_obj.value)

    # ------------------------------------------------------------------ #
    # Initialization                                                      #
    # ------------------------------------------------------------------ #
    async def _initialize(self):
        if self._initialized:
            return
        await self.start()
        self._initialized = True

    async def start(self):
        if self.closed:
            raise RuntimeError("Session is closed")
        try:
            # 1. Main pages
            await self._get_main_page_cookies()

            # 2. Test API request to obtain token
            test_params = self._build_start_params()
            async with self.get(url=self.base_url, params=test_params) as response:
                await self._collect_cookies_from_jar(self.base_url)

                cookies = self.cookie_jar.filter_cookies(URL(self.base_url))
                token_cookie = cookies.get("_m_h5_tk")

                if token_cookie:
                    # Library-side write from server response.
                    # set_token_internal does NOT mark _m_h5_tk as overridden,
                    # so a manual user override (if any) still wins later.
                    if "_m_h5_tk" not in self._overridden_cookies:
                        self._set_token_internal(token_cookie.value)
                    self._initialized = True
                    self._log(f"Token initialized: {self._token_part}...")
                    return True
                else:
                    self._initialized = True
                    self._log("Session initialized without token, will try to get it later")
                    return True
        except Exception as e:
            await self.close()
            raise Exception(f"Session initialization error: {e}")

    async def _get_main_page_cookies(self):
        try:
            headers = self._main_page_headers()
            for url in self._main_page_urls():
                try:
                    self._log(f"Getting cookies from: {url}")
                    async with self.get(url, headers=headers, allow_redirects=True) as response:
                        await response.text()
                        url_obj = URL(url)
                        cookies = self.cookie_jar.filter_cookies(url_obj)
                        for cookie_name, cookie_obj in cookies.items():
                            if cookie_name in self._overridden_cookies:
                                continue
                            self.cookies_dict.set_internal(cookie_name, cookie_obj.value)
                            self._log(f"Got cookie: {cookie_name} = {cookie_obj.value[:50]}...")
                        headers["referer"] = url
                except Exception as e:
                    self._log(f"Error getting cookies from {url}: {e}")
                    continue

            missing = self._check_missing_cookies()
            if missing:
                await self._use_fallback_cookies(missing)

            self._log("Main page cookies collected successfully")
            return True
        except Exception as e:
            self._log(f"Error getting main page cookies: {e}")
            return False

    async def close(self):
        await super().close()
        self._reset_state()

    async def _ensure_initialized(self):
        if not self._initialized or self.closed:
            await self._initialize()

    # ------------------------------------------------------------------ #
    # Public methods                                                      #
    # ------------------------------------------------------------------ #
    async def search_by_image(self, image_path: str) -> List[Dict]:
        await self._ensure_initialized()
        image_id = await self._get_image_id(image_path)
        if not image_id:
            self._log("Failed to get image ID")
            return []
        return await self._search_by_image_id_api(image_id)

    async def search_by_text(self, keywords: str) -> List[Dict]:
        await self._ensure_initialized()
        return await self._search_by_keywords_api(keywords)

    # ------------------------------------------------------------------ #
    # Image upload                                                        #
    # ------------------------------------------------------------------ #
    async def _get_image_id(self, image_path):
        await self._ensure_initialized()
        try:
            image_b64 = read_and_encode_image(image_path)
            data_string = prepare_image_request(image_b64)
            params, headers = self._build_image_upload_params(data_string)

            async with self.post(
                url=self.base_url, params=params, data={"data": data_string}, headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("data", {}).get("success"):
                        image_id = result["data"].get("imageId")
                        if image_id:
                            return image_id
                    else:
                        self._log(f"API error in image upload: {result.get('ret', ['Unknown error'])}")
                else:
                    self._log(f"Image upload HTTP error: {response.status}")
                return None
        except Exception as e:
            self._log(f"Image upload request error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Search page cookies                                                 #
    # ------------------------------------------------------------------ #
    async def _get_search_page_cookies(self, search_param: str, search_type: str = "image"):
        try:
            if search_type == "image":
                initial_url = "https://s.1688.com/youyuan/index.htm"
                initial_params = {
                    "tab": "imageSearch",
                    "imageId": search_param,
                    "imageIdList": search_param,
                    "spm": "a26352.13672862.imagesearch.upload",
                }
            else:
                initial_url = "https://s.1688.com/selloffer/offer_search.htm"
                initial_params = {
                    "keywords": search_param,
                    "spm": "a26352.b28411319/2508.searchbox.0",
                }

            initial_full_url = f"{initial_url}?{urllib.parse.urlencode(initial_params)}"
            initial_headers = {
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
                ),
                "accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/webp,*/*;q=0.8"
                ),
                "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "referer": "https://s.1688.com/",
            }

            async with self.get(
                url=initial_full_url, headers=initial_headers, allow_redirects=True
            ) as response:
                if response.status != 200:
                    self._log(f"Initial page request failed: {response.status}")
                    return False
                url_obj = URL(initial_full_url)
                cookies = self.cookie_jar.filter_cookies(url_obj)
                for cookie_name, cookie_obj in cookies.items():
                    if cookie_name in self._overridden_cookies:
                        continue
                    self.cookies_dict.set_internal(cookie_name, cookie_obj.value)
                    self._log(f"Updated cookie from search page: {cookie_name}")

            if search_type == "image":
                target_url = (
                    "https://pages-fast.1688.com/wow/cbu/srch_rec/image_search/"
                    "youyuan/index.html"
                )
                target_params = {
                    "tab": "imageSearch",
                    "imageId": search_param,
                    "imageIdList": search_param,
                    "spm": "a26352.13672862.imagesearch.upload",
                }
                target_full_url = f"{target_url}?{urllib.parse.urlencode(target_params)}"
                target_headers = {
                    "user-agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
                    ),
                    "accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/webp,*/*;q=0.8"
                    ),
                    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "referer": initial_full_url,
                }
                async with self.get(
                    url=target_full_url, headers=target_headers, allow_redirects=True
                ) as response:
                    if response.status != 200:
                        self._log(f"Target page request failed: {response.status}")
                        return False
                    url_obj = URL(target_full_url)
                    cookies = self.cookie_jar.filter_cookies(url_obj)
                    for cookie_name, cookie_obj in cookies.items():
                        if cookie_name in self._overridden_cookies:
                            continue
                        self.cookies_dict.set_internal(cookie_name, cookie_obj.value)

            return True
        except Exception as e:
            self._log(f"Cookie collection error: {e}")
            return False

    # ------------------------------------------------------------------ #
    # API search                                                          #
    # ------------------------------------------------------------------ #
    async def _search_by_image_id_api(self, image_id: str) -> List[Dict]:
        await self._ensure_initialized()
        cookies_success = await self._get_search_page_cookies(image_id, "image")
        if not cookies_success:
            self._log("Cookie collection failed, using fallback method")
            return await self._search_by_image_id_fallback(image_id)
        return await self._get_offer_list(image_id)

    async def _search_by_keywords_api(self, keywords: str) -> List[Dict]:
        await self._ensure_initialized()
        cookies_success = await self._get_search_page_cookies(keywords, "text")
        if not cookies_success:
            self._log("Cookie collection failed, using fallback method")
            return await self._search_by_keywords_fallback(keywords)
        return await self._get_text_offer_list(keywords)

    async def _get_offer_list(self, image_id: str) -> List[Dict]:
        try:
            full_url, headers = self._build_image_search_request(image_id)
            async with self.get(url=full_url, headers=headers) as response:
                if response.status == 200:
                    response_bytes = await response.read()
                    response_text = await self._decode_response(response, response_bytes)
                    return self._parse_jsonp_response(response_text)
                else:
                    self._log(f"Products request failed with status: {response.status}")
                    return []
        except Exception as e:
            self._log(f"Products request error: {e}")
            return []

    async def _get_text_offer_list(self, keywords: str) -> List[Dict]:
        try:
            full_url, headers = self._build_text_search_request(keywords)
            async with self.get(url=full_url, headers=headers) as response:
                if response.status == 200:
                    response_bytes = await response.read()
                    response_text = await self._decode_response(response, response_bytes)
                    products = self._parse_jsonp_response(response_text)
                    self._log(f"Text search API found {len(products)} products")
                    return products
                else:
                    self._log(f"Text search API request failed with status: {response.status}")
                    return []
        except Exception as e:
            self._log(f"Text search API request error: {e}")
            return []

    async def _decode_response(self, response, response_bytes: bytes) -> str:
        content_encoding = response.headers.get("content-encoding", "").lower()
        return self._decode_bytes(response_bytes, content_encoding)

    # ------------------------------------------------------------------ #
    # Fallback                                                            #
    # ------------------------------------------------------------------ #
    async def _search_by_image_id_fallback(self, image_id: str) -> List[Dict]:
        try:
            search_url = "https://s.1688.com/youyuan/index.htm"
            params = {"tab": "imageSearch", "imageId": image_id}
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/webp,*/*;q=0.8"
                ),
                "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "referer": "https://s.1688.com/",
            }
            async with self.get(url=search_url, params=params, headers=headers) as response:
                if response.status == 200:
                    html_content = await response.text()
                    products = extract_products_from_html(html_content)
                    self._log(f"Fallback method found {len(products)} products")
                    return products
                else:
                    self._log(f"Fallback method HTTP error: {response.status}")
                    return []
        except Exception as e:
            self._log(f"Fallback method error: {e}")
            return []

    async def _search_by_keywords_fallback(self, keywords: str) -> List[Dict]:
        return await self._get_text_offer_list(keywords)

    # ------------------------------------------------------------------ #
    # Properties / await support                                          #
    # ------------------------------------------------------------------ #
    @property
    def is_active(self):
        return not self.closed

    def __await__(self):
        return self._create_initialized().__await__()

    async def _create_initialized(self):
        await self._initialize()
        return self