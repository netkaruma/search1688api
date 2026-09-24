"""
Sync 1688 session. All requests specifics live here.
Operation order is preserved 1:1 with the original working version.
"""

import urllib.parse
from typing import Dict, List

import requests

from .base import Base1688Mixin
from .utils import (
    prepare_image_request,
    read_and_encode_image,
    extract_products_from_html,
)


class Sync1688Session(Base1688Mixin, requests.Session):
    def __init__(self, debug: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_init(debug=debug)

    # ------------------------------------------------------------------ #
    # Context manager                                                     #
    # ------------------------------------------------------------------ #
    def __enter__(self):
        if not self._initialized:
            self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ------------------------------------------------------------------ #
    # Collect cookies from requests.Session.cookies                       #
    # ------------------------------------------------------------------ #
    def _collect_cookies_from_session(self):
        for cookie_name, cookie_value in self.cookies.items():
            # Never overwrite cookies the user set manually
            if cookie_name in self._overridden_cookies:
                continue
            # Server-side write, do not fire the hook
            self.cookies_dict.set_internal(cookie_name, cookie_value)

    # ------------------------------------------------------------------ #
    # Initialization                                                      #
    # ------------------------------------------------------------------ #
    def _initialize(self):
        if self._initialized:
            return
        self.start()
        self._initialized = True

    def start(self):
        try:
            # 1. Main pages
            self._get_main_page_cookies()

            # 2. Test API request
            test_params = self._build_start_params()
            self.get(url=self.base_url, params=test_params)

            self._collect_cookies_from_session()
            token_cookie = self.cookies.get("_m_h5_tk")

            if token_cookie:
                # Library-side write from server response.
                # If the user already set _m_h5_tk manually, keep theirs.
                if "_m_h5_tk" not in self._overridden_cookies:
                    self._set_token_internal(token_cookie)
                self._initialized = True
                self._log(f"Token initialized: {self._token_part}...")
                return True
            else:
                self._initialized = True
                self._log("Session initialized without token, will try to get it later")
                return True
        except Exception as e:
            self.close()
            raise Exception(f"Session initialization error: {e}")

    def _get_main_page_cookies(self):
        try:
            headers = self._main_page_headers()
            for url in self._main_page_urls():
                try:
                    self._log(f"Getting cookies from: {url}")
                    self.get(url, headers=headers, allow_redirects=True)
                    self._collect_cookies_from_session()
                    headers["referer"] = url
                except Exception as e:
                    self._log(f"Error getting cookies from {url}: {e}")
                    continue

            missing = self._check_missing_cookies()
            if missing:
                self._use_fallback_cookies(missing)

            self._log("Main page cookies collected successfully")
            return True
        except Exception as e:
            self._log(f"Error getting main page cookies: {e}")
            return False

    def close(self):
        super().close()
        self._reset_state()

    def _ensure_initialized(self):
        if not self._initialized:
            self._initialize()

    # ------------------------------------------------------------------ #
    # Public methods                                                      #
    # ------------------------------------------------------------------ #
    def search_by_image(self, image_path: str) -> List[Dict]:
        self._ensure_initialized()
        image_id = self._get_image_id(image_path)
        if not image_id:
            self._log("Failed to get image ID")
            return []
        return self._search_by_image_id_api(image_id)

    def search_by_text(self, keywords: str) -> List[Dict]:
        self._ensure_initialized()
        return self._search_by_keywords_api(keywords)

    # ------------------------------------------------------------------ #
    # Image upload                                                        #
    # ------------------------------------------------------------------ #
    def _get_image_id(self, image_path):
        self._ensure_initialized()
        try:
            image_b64 = read_and_encode_image(image_path)
            data_string = prepare_image_request(image_b64)
            params, headers = self._build_image_upload_params(data_string)

            response = self.post(
                url=self.base_url, params=params, data={"data": data_string}, headers=headers
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("data", {}).get("success"):
                    image_id = result["data"].get("imageId")
                    if image_id:
                        return image_id
                else:
                    self._log(f"API error in image upload: {result.get('ret', ['Unknown error'])}")
            else:
                self._log(f"Image upload HTTP error: {response.status_code}")
            return None
        except Exception as e:
            self._log(f"Image upload request error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Search page cookies                                                 #
    # ------------------------------------------------------------------ #
    def _get_search_page_cookies(self, search_param: str, search_type: str = "image"):
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

            response = self.get(
                url=initial_full_url, headers=initial_headers, allow_redirects=True
            )
            if response.status_code != 200:
                self._log(f"Initial page request failed: {response.status_code}")
                return False

            self._collect_cookies_from_session()
            for cookie_name in self.cookies.keys():
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
                response = self.get(
                    url=target_full_url, headers=target_headers, allow_redirects=True
                )
                if response.status_code != 200:
                    self._log(f"Target page request failed: {response.status_code}")
                    return False
                self._collect_cookies_from_session()

            return True
        except Exception as e:
            self._log(f"Cookie collection error: {e}")
            return False

    # ------------------------------------------------------------------ #
    # API search                                                          #
    # ------------------------------------------------------------------ #
    def _search_by_image_id_api(self, image_id: str) -> List[Dict]:
        self._ensure_initialized()
        cookies_success = self._get_search_page_cookies(image_id, "image")
        if not cookies_success:
            self._log("Cookie collection failed, using fallback method")
            return self._search_by_image_id_fallback(image_id)
        return self._get_offer_list(image_id)

    def _search_by_keywords_api(self, keywords: str) -> List[Dict]:
        self._ensure_initialized()
        cookies_success = self._get_search_page_cookies(keywords, "text")
        if not cookies_success:
            self._log("Cookie collection failed, using fallback method")
            return self._search_by_keywords_fallback(keywords)
        return self._get_text_offer_list(keywords)

    def _get_offer_list(self, image_id: str) -> List[Dict]:
        try:
            full_url, headers = self._build_image_search_request(image_id)
            response = self.get(url=full_url, headers=headers)
            if response.status_code == 200:
                return self._parse_jsonp_response(response.text)
            else:
                self._log(f"Products request failed with status: {response.status_code}")
                return []
        except Exception as e:
            self._log(f"Products request error: {e}")
            return []

    def _get_text_offer_list(self, keywords: str) -> List[Dict]:
        try:
            full_url, headers = self._build_text_search_request(keywords)
            response = self.get(url=full_url, headers=headers)
            if response.status_code == 200:
                products = self._parse_jsonp_response(response.text)
                self._log(f"Text search API found {len(products)} products")
                return products
            else:
                self._log(f"Text search API request failed with status: {response.status_code}")
                return []
        except Exception as e:
            self._log(f"Text search API request error: {e}")
            return []

    # ------------------------------------------------------------------ #
    # Fallback                                                            #
    # ------------------------------------------------------------------ #
    def _search_by_image_id_fallback(self, image_id: str) -> List[Dict]:
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
            response = self.get(url=search_url, params=params, headers=headers)
            if response.status_code == 200:
                html_content = response.text
                products = extract_products_from_html(html_content)
                self._log(f"Fallback method found {len(products)} products")
                return products
            else:
                self._log(f"Fallback method HTTP error: {response.status_code}")
                return []
        except Exception as e:
            self._log(f"Fallback method error: {e}")
            return []

    def _search_by_keywords_fallback(self, keywords: str) -> List[Dict]:
        return self._get_text_offer_list(keywords)

    # ------------------------------------------------------------------ #
    # Properties                                                          #
    # ------------------------------------------------------------------ #
    @property
    def is_active(self):
        return True