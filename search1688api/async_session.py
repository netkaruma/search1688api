import asyncio
import aiohttp
import json
import re
import time
import urllib.parse
import random
import string
from typing import List, Dict, Any
from yarl import URL
from traceback import format_exc

from .utils import prepare_image_request, generate_sign, read_and_encode_image, extract_products_from_html


class Async1688Session(aiohttp.ClientSession):
    def __init__(self, *args, debug: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        
        self._token = None
        self._token_part = None
        self.app_key = "12574478"
        self.base_url = "https://h5api.m.1688.com/h5/mtop.relationrecommend.wirelessrecommend.recommend/2.0/"
        self._initialized = False
        self.cookies_dict = {}
        self.debug = debug  # Debug output control
    
    def _log(self, message: str):
        """Print debug messages only if debug=True"""
        if self.debug:
            print(message)
    
    def _generate_random_cookie_value(self, length: int = 16) -> str:
        """Generate random value for cookie"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _generate_fallback_cookies(self) -> Dict[str, str]:
        """Generate random values for missing cookies"""
        timestamp = str(int(time.time() * 1000))
        
        return {
            't': self._generate_random_cookie_value(32),
            '_tb_token_': self._generate_random_cookie_value(13), 
            'cookie2': self._generate_random_cookie_value(32),
            'cna': self._generate_random_cookie_value(16),
            '_m_h5_tk': f"{self._generate_random_cookie_value(32)}_{timestamp}",
            '_m_h5_tk_enc': self._generate_random_cookie_value(32)
        }
    
    async def __aenter__(self):
        if not self._initialized:
            await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _initialize(self):
        if self._initialized:
            return
        
        await self.start()
        self._initialized = True
    
    async def start(self):
        if self.closed:
            raise RuntimeError("Session is closed")
        
        try:
            # First get cookies from 1688.com main page
            await self._get_main_page_cookies()
            
            # Then try to get token via API
            test_params = {
                "jsv": "2.7.2",
                "appKey": self.app_key,
                "t": str(int(time.time() * 1000)),
                "api": "mtop.relationrecommend.WirelessRecommend.recommend",
                "v": "2.0",
                "type": "originaljson"
            }
            
            async with self.get(
                url=self.base_url,
                params=test_params
            ) as response:
                
                # Get cookies from API response via cookie_jar
                url_obj = URL(self.base_url)
                cookies = self.cookie_jar.filter_cookies(url_obj)
                for cookie_name, cookie_obj in cookies.items():
                    self.cookies_dict[cookie_name] = cookie_obj.value
                
                token_cookie = cookies.get('_m_h5_tk')
                
                if token_cookie:
                    self._token = token_cookie.value
                    self._token_part = self._token.split('_')[0]
                    self._initialized = True
                    self._log(f"Token initialized: {self._token_part}...")
                    return True
                else:
                    # Even if token not received, mark as initialized
                    self._initialized = True
                    self._log("Session initialized without token, will try to get it later")
                    return True
                
        except Exception as e:
            await self.close()
            raise Exception(f"Session initialization error: {e}")
    
    async def _get_main_page_cookies(self):
        """Get all necessary cookies from 1688.com main page"""
        try:
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "accept-encoding": "gzip, deflate, br",
                "dnt": "1",
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "upgrade-insecure-requests": "1"
            }
            
            urls_to_visit = [
                "https://www.1688.com",
                "https://s.1688.com", 
                "https://login.1688.com",
                "https://s.1688.com/selloffer/offer_search.htm?keywords=sample"
            ]
            
            for url in urls_to_visit:
                try:
                    self._log(f"Getting cookies from: {url}")
                    async with self.get(url, headers=headers, allow_redirects=True) as response:
                        # Read response to complete request
                        await response.text()
                        
                        # Get cookies via cookie_jar
                        url_obj = URL(url)
                        cookies = self.cookie_jar.filter_cookies(url_obj)
                        
                        for cookie_name, cookie_obj in cookies.items():
                            self.cookies_dict[cookie_name] = cookie_obj.value
                            self._log(f"Got cookie: {cookie_name} = {cookie_obj.value[:50]}...")
                        
                        # Update referer for next request
                        headers["referer"] = url
                        
                except Exception as e:
                    self._log(f"Error getting cookies from {url}: {e}")
                    continue
            
            # Check for important cookies
            important_cookies = ['_m_h5_tk', '_m_h5_tk_enc', 't', '_tb_token_', 'cookie2', 'cna']
            available_cookies = list(self.cookies_dict.keys())
            self._log(f"Available cookies: {available_cookies}")
            
            missing_cookies = [cookie for cookie in important_cookies if cookie not in available_cookies]
            if missing_cookies:
                self._log(f"Missing important cookies: {missing_cookies}")
                await self._use_fallback_cookies(missing_cookies)
            
            self._log("Main page cookies collected successfully")
            return True
                
        except Exception as e:
            self._log(f"Error getting main page cookies: {e}")
            return False
    
    async def _use_fallback_cookies(self, missing_cookies):
        """Use generated random cookies for missing ones"""
        fallback_cookies = self._generate_fallback_cookies()
        
        for cookie_name in missing_cookies:
            if cookie_name in fallback_cookies:
                self.cookies_dict[cookie_name] = fallback_cookies[cookie_name]
                self._log(f"Using generated fallback for {cookie_name}: {fallback_cookies[cookie_name][:30]}...")
    
    async def close(self):
        await super().close()
        self._token = None
        self._token_part = None
        self._initialized = False
        self.cookies_dict = {}
    
    async def _ensure_initialized(self):
        if not self._initialized or self.closed:
            await self._initialize()
    
    async def _get_image_id(self, image_path):
        await self._ensure_initialized()
        
        try:
            image_b64 = read_and_encode_image(image_path)
            data_string = prepare_image_request(image_b64)
            timestamp = str(int(time.time() * 1000))
            
            # If token exists, use it for signing
            if self._token_part:
                sign = generate_sign(self._token_part, timestamp, self.app_key, data_string)
            else:
                # Try to get token from cookies
                if '_m_h5_tk' in self.cookies_dict:
                    token_from_cookies = self.cookies_dict['_m_h5_tk']
                    token_part_from_cookies = token_from_cookies.split('_')[0] if '_' in token_from_cookies else token_from_cookies
                    sign = generate_sign(token_part_from_cookies, timestamp, self.app_key, data_string)
                    self._log("Using token from cookies for signing")
                else:
                    # Use fallback signature
                    sign = generate_sign("fallback_token", timestamp, self.app_key, data_string)
                    self._log("Using fallback token for signing")
            
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
                "timeout": "20000"
            }
            
            headers = {
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://s.1688.com",
                "referer": "https://s.1688.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with self.post(
                url=self.base_url,
                params=params,
                data={"data": data_string},
                headers=headers
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
    
    async def _get_search_page_cookies(self, search_param: str, search_type: str = "image"):
        """Get cookies for search page"""
        try:
            if search_type == "image":
                initial_url = "https://s.1688.com/youyuan/index.htm"
                initial_params = {
                    "tab": "imageSearch",
                    "imageId": search_param,
                    "imageIdList": search_param,
                    "spm": "a26352.13672862.imagesearch.upload"
                }
            else:  # text search
                initial_url = "https://s.1688.com/selloffer/offer_search.htm"
                initial_params = {
                    "keywords": search_param,
                    "spm": "a26352.b28411319/2508.searchbox.0"
                }
            
            initial_full_url = f"{initial_url}?{urllib.parse.urlencode(initial_params)}"
            
            initial_headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "referer": "https://s.1688.com/",
            }
            
            async with self.get(
                url=initial_full_url,
                headers=initial_headers,
                allow_redirects=True
            ) as response:
                if response.status != 200:
                    self._log(f"Initial page request failed: {response.status}")
                    return False
                    
                # Update cookies from response via cookie_jar
                url_obj = URL(initial_full_url)
                cookies = self.cookie_jar.filter_cookies(url_obj)
                for cookie_name, cookie_obj in cookies.items():
                    self.cookies_dict[cookie_name] = cookie_obj.value
                    self._log(f"Updated cookie from search page: {cookie_name}")

            # For image search, we also need the target page
            if search_type == "image":
                target_url = "https://pages-fast.1688.com/wow/cbu/srch_rec/image_search/youyuan/index.html"
                target_params = {
                    "tab": "imageSearch",
                    "imageId": search_param,
                    "imageIdList": search_param,
                    "spm": "a26352.13672862.imagesearch.upload"
                }
                target_full_url = f"{target_url}?{urllib.parse.urlencode(target_params)}"
                
                target_headers = {
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "referer": initial_full_url,
                }
                
                async with self.get(
                    url=target_full_url,
                    headers=target_headers,
                    allow_redirects=True
                ) as response:
                    if response.status != 200:
                        self._log(f"Target page request failed: {response.status}")
                        return False
                        
                    # Update cookies from response
                    url_obj = URL(target_full_url)
                    cookies = self.cookie_jar.filter_cookies(url_obj)
                    for cookie_name, cookie_obj in cookies.items():
                        self.cookies_dict[cookie_name] = cookie_obj.value

            return True
                
        except Exception as e:
            self._log(f"Cookie collection error: {e}")
            return False

    async def search_by_image(self, image_path: str) -> List[Dict]:
        """Search products by image"""
        await self._ensure_initialized()
        
        image_id = await self._get_image_id(image_path)
        
        if not image_id:
            self._log("Failed to get image ID")
            return []
        
        products = await self._search_by_image_id_api(image_id)
        return products

    async def search_by_text(self, keywords: str) -> List[Dict]:
        """Search products by text keywords"""
        await self._ensure_initialized()
        
        products = await self._search_by_keywords_api(keywords)
        return products

    async def _search_by_image_id_api(self, image_id: str) -> List[Dict]:
        await self._ensure_initialized()
        
        cookies_success = await self._get_search_page_cookies(image_id, "image")
        
        if not cookies_success:
            self._log("Cookie collection failed, using fallback method")
            return await self._search_by_image_id_fallback(image_id)
        
        products = await self._get_offer_list(image_id)
        return products

    async def _search_by_keywords_api(self, keywords: str) -> List[Dict]:
        """Search products by keywords using API"""
        await self._ensure_initialized()
        
        cookies_success = await self._get_search_page_cookies(keywords, "text")
        
        if not cookies_success:
            self._log("Cookie collection failed, using fallback method")
            return await self._search_by_keywords_fallback(keywords)
        
        products = await self._get_text_offer_list(keywords)
        return products

    async def _get_offer_list(self, image_id: str) -> List[Dict]:
        try:
            params_data = {
                "beginPage": 1,
                "pageSize": 60,
                "method": "imageOfferSearchService",
                "searchScene": "pcImageSearch",
                "appName": "pctusou",
                "tab": "imageSearch",
                "imageId": image_id,
                "imageIdList": image_id,
                "spm": "a26352.13672862.imagesearch.upload"
            }
            
            request_data = {
                "appId": 32517,
                "params": json.dumps(params_data, ensure_ascii=False)
            }
            
            data_string = json.dumps(request_data, ensure_ascii=False)
            
            timestamp = str(int(time.time() * 1000))
            
            # Use token for signing if available
            if self._token_part:
                sign = generate_sign(self._token_part, timestamp, self.app_key, data_string)
            else:
                # Try to get token from cookies
                if '_m_h5_tk' in self.cookies_dict:
                    token_from_cookies = self.cookies_dict['_m_h5_tk']
                    token_part_from_cookies = token_from_cookies.split('_')[0] if '_' in token_from_cookies else token_from_cookies
                    sign = generate_sign(token_part_from_cookies, timestamp, self.app_key, data_string)
                else:
                    sign = generate_sign("fallback", timestamp, self.app_key, data_string)
            
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
                "data": data_string
            }
            
            full_url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
            
            cookies_str = '; '.join([f'{k}={v}' for k, v in self.cookies_dict.items()])
            
            headers = {
                "authority": "h5api.m.1688.com",
                "method": "GET",
                "scheme": "https",
                "accept": "*/*",
                "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "cookie": cookies_str,
                "referer": f"https://pages-fast.1688.com/wow/cbu/srch_rec/image_search/youyuan/index.html?tab=imageSearch&imageId={image_id}&imageIdList={image_id}&spm=a26352.13672862.imagesearch.upload",
                "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "script",
                "sec-fetch-mode": "no-cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
            }
            
            async with self.get(
                url=full_url,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    response_bytes = await response.read()
                    
                    response_text = await self._decode_response(response, response_bytes)
                    
                    if response_text:
                        if response_text.startswith('mtopjsonp') or 'mtopjsonp' in response_text:
                            json_start = response_text.find('{')
                            json_end = response_text.rfind('}') + 1
                            if json_start != -1 and json_end != -1:
                                json_str = response_text[json_start:json_end]
                                
                                try:
                                    result = json.loads(json_str)
                                    
                                    # Check for API errors
                                    if 'ret' in result and not result.get('ret', ['SUCCESS'])[0].startswith('SUCCESS'):
                                        self._log(f"API returned error: {result.get('ret')}")
                                        return []
                                    
                                    products = self._parse_api_products(result)
                                    return products
                                    
                                except json.JSONDecodeError as e:
                                    self._log(f"JSON decode error: {e}")
                                    return []
                        else:
                            self._log("Invalid JSONP response format")
                            return []
                    else:
                        self._log("Failed to decode response")
                        return []
                else:
                    self._log(f"Products request failed with status: {response.status}")
                    return []
                    
        except Exception as e:
            self._log(f"Products request error: {e}")
            return []

    async def _get_text_offer_list(self, keywords: str) -> List[Dict]:
        """Get product list for text search using the correct API"""
        try:
            # Form parameters as in call stack
            params_data = {
                "beginPage": 1,
                "pageSize": 60,
                "method": "getOfferList",
                "pageId": "qWJOoeNkRwblv903Iv6KQqPVkYDrgMudKHTRsee9Sjz7N9z1",  # fixed pageId
                "verticalProductFlag": "pcmarket",
                "searchScene": "pcOfferSearch",
                "charset": "GBK",
                "spm": "a26352.b28411319/2508.searchbox.0",
                "keywords": keywords
            }
            
            request_data = {
                "appId": 32517,
                "params": json.dumps(params_data, ensure_ascii=False)
            }
            
            data_string = json.dumps(request_data, ensure_ascii=False)
            
            timestamp = str(int(time.time() * 1000))
            
            # Use token for signing if available
            if self._token_part:
                sign = generate_sign(self._token_part, timestamp, self.app_key, data_string)
            else:
                sign = generate_sign("fallback", timestamp, self.app_key, data_string)
            
            # Parameters as in call stack
            params = {
                "jsv": "2.7.4",  # version from stack
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
                "data": data_string
            }
            
            full_url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
            
            cookies_str = '; '.join([f'{k}={v}' for k, v in self.cookies_dict.items()])
            
            headers = {
                "authority": "h5api.m.1688.com",
                "method": "GET",
                "scheme": "https",
                "accept": "*/*",
                "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "cookie": cookies_str,
                "referer": f"https://s.1688.com/selloffer/offer_search.htm?keywords={urllib.parse.quote(keywords)}&spm=a26352.b28411319%2F2508.searchbox.0",
                "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "script",
                "sec-fetch-mode": "no-cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
            }
            
            async with self.get(
                url=full_url,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    response_bytes = await response.read()
                    
                    response_text = await self._decode_response(response, response_bytes)
                    
                    if response_text:
                        if response_text.startswith('mtopjsonp') or 'mtopjsonp' in response_text:
                            json_start = response_text.find('{')
                            json_end = response_text.rfind('}') + 1
                            if json_start != -1 and json_end != -1:
                                json_str = response_text[json_start:json_end]
                                
                                try:
                                    result = json.loads(json_str)
                                    
                                    # Check for API errors
                                    if 'ret' in result and not result.get('ret', ['SUCCESS'])[0].startswith('SUCCESS'):
                                        self._log(f"Text search API returned error: {result.get('ret')}")
                                        return []
                                    
                                    products = self._parse_api_products(result)
                                    self._log(f"Text search API found {len(products)} products")
                                    return products
                                    
                                except json.JSONDecodeError as e:
                                    self._log(f"Text search JSON decode error: {e}")
                                    return []
                        else:
                            self._log("Invalid JSONP response format in text search")
                            return []
                    else:
                        self._log("Failed to decode text search response")
                        return []
                else:
                    self._log(f"Text search API request failed with status: {response.status}")
                    return []
                    
        except Exception as e:
            self._log(f"Text search API request error: {e}")
            return []

    async def _decode_response(self, response, response_bytes: bytes) -> str:
        try:
            content_encoding = response.headers.get('content-encoding', '').lower()
            
            if 'gzip' in content_encoding:
                import gzip
                return gzip.decompress(response_bytes).decode('utf-8')
            elif 'deflate' in content_encoding:
                import zlib
                return zlib.decompress(response_bytes).decode('utf-8')
            elif 'br' in content_encoding:
                try:
                    import brotli
                    return brotli.decompress(response_bytes).decode('utf-8')
                except ImportError:
                    self._log("Brotli compression not supported")
            elif 'zstd' in content_encoding:
                try:
                    import zstandard
                    dctx = zstandard.ZstdDecompressor()
                    return dctx.decompress(response_bytes).decode('utf-8')
                except ImportError:
                    self._log("Zstandard compression not supported")
            
            try:
                return response_bytes.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    return response_bytes.decode('latin-1')
                except UnicodeDecodeError:
                    return response_bytes.decode('cp1251')
                    
        except Exception as e:
            self._log(f"Response decoding error: {e}")
            try:
                return response_bytes.decode('utf-8', errors='replace')
            except:
                return None

    def _parse_api_products(self, api_result: Dict) -> List[Dict]:
        products = []
        
        try:
            # Correct path to products: data -> data -> OFFER -> items
            offer_data = api_result.get('data', {}).get('data', {}).get('OFFER', {})
            items = offer_data.get('items', [])
            
            if not items:
                self._log("No items found in API response")
                return []
            
            for item in items:
                try:
                    # Simply convert each item to Python dictionary
                    product_dict = dict(item)
                    products.append(product_dict)
                except Exception as e:
                    self._log(f"Error parsing product item: {e}")
                    continue
                        
        except Exception as e:
            self._log(f"Error parsing API products: {e}")
        
        return products

    async def _search_by_image_id_fallback(self, image_id: str) -> List[Dict]:
        try:
            search_url = "https://s.1688.com/youyuan/index.htm"
            params = {
                "tab": "imageSearch",
                "imageId": image_id
            }
            
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "referer": "https://s.1688.com/"
            }
            
            async with self.get(
                url=search_url,
                params=params,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    html_content = await response.text()
                    # Now extract_products_from_html returns dictionaries directly
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
        """Fallback method for text search"""
        return await self._get_text_offer_list(keywords)

    @property
    def is_active(self):
        return not self.closed

    def __await__(self):
        return self._create_initialized().__await__()

    async def _create_initialized(self):
        await self._initialize()
        return self