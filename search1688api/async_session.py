import asyncio
from urllib import response
import aiohttp
import json
import re
import time
from typing import List, Dict, Any
from yarl import URL

from .models import Product, DetailProduct, extract_products_from_html
from .utils import prepare_image_request, generate_sign, read_and_encode_image


class Async1688Session:
    def __init__(self, default_timeout: float = 30):
        self._session = None
        self._token = None
        self._token_part = None
        self.app_key = "12574478"
        self.base_url = "https://h5api.m.1688.com/h5/mtop.relationrecommend.wirelessrecommend.recommend/2.0/"
        self._initialized = False
        self.default_timeout = default_timeout
        self.cookies_dict = {}
    
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
        if self._session and not self._session.closed:
            await self.close()
        
        self._session = aiohttp.ClientSession()
        
        try:
            test_params = {
                "jsv": "2.7.2",
                "appKey": self.app_key,
                "t": str(int(time.time() * 1000)),
                "api": "mtop.relationrecommend.WirelessRecommend.recommend",
                "v": "2.0",
                "type": "originaljson"
            }
            
            async with self._session.get(
                self.base_url,
                params=test_params,
                timeout=self.default_timeout
            ) as response:
                
                url_obj = URL(self.base_url)
                cookies = self._session.cookie_jar.filter_cookies(url_obj)
                token_cookie = cookies.get('_m_h5_tk')
                
                if token_cookie:
                    self._token = token_cookie.value
                    self._token_part = self._token.split('_')[0]
                    self._initialized = True
                    return True
                else:
                    raise Exception("Не удалось получить токен")
                
        except Exception as e:
            await self.close()
            raise Exception(f"Ошибка запуска сессии: {e}")
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            self._token = None
            self._token_part = None
            self._initialized = False
            self.cookies_dict = {}
    
    async def _ensure_initialized(self):
        if not self._initialized or not self.is_active:
            await self._initialize()
    
    async def _get_image_id(self, image_path, timeout=None):
        await self._ensure_initialized()
        
        if timeout is None:
            timeout = self.default_timeout
        
        image_b64 = read_and_encode_image(image_path)
        data_string = prepare_image_request(image_b64)
        timestamp = str(int(time.time() * 1000))
        sign = generate_sign(self._token_part, timestamp, self.app_key, data_string)
        
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
        
        try:
            async with self._session.post(
                self.base_url,
                params=params,
                data={"data": data_string},
                headers=headers,
                timeout=timeout
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    if result.get("data", {}).get("success"):
                        image_id = result["data"].get("imageId")
                        if image_id:
                            return image_id
                return None
            
        except Exception as e:
            raise Exception(f"Ошибка при запросе: {e}")
    
    async def search_by_image(self, image_path: str, timeout: float = None) -> List[Product]:
        await self._ensure_initialized()
        
        if timeout is None:
            timeout = self.default_timeout
        
        image_id = await self._get_image_id(image_path, timeout=timeout)
        
        if not image_id:
            return []
        
        products = await self._search_by_image_id(image_id, timeout=timeout)
        return products
    
    async def _search_by_image_id(self, image_id: str, timeout=None) -> List[Product]:
        await self._ensure_initialized()
        
        if timeout is None:
            timeout = self.default_timeout
        
        search_url = f"https://s.1688.com/youyuan/index.htm"
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
        
        try:
            async with self._session.get(
                search_url,
                params=params,
                headers=headers,
                timeout=timeout
            ) as response:
                
                if response.status == 200:
                    html_content = await response.text()
                    products = extract_products_from_html(html_content)
                    return products
                else:
                    return []
                    
        except Exception:
            return []
    
    async def _get_cookies_with_aiohttp(self):
        """Получает куки через aiohttp запросы"""
        temp_session = None
        try:
            # Используем временную сессию для получения кук
            temp_session = aiohttp.ClientSession()
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            }
            
            # Запрос к главной странице 1688
            async with temp_session.get("https://www.1688.com/", headers=headers, allow_redirects=True) as response:
                # Получаем куки из ответа
                response_cookies = response.cookies
                for cookie in response_cookies:
                    self.cookies_dict[cookie.key] = cookie.value
            
            # Дополнительный запрос для симуляции поведения браузера
            async with temp_session.get("https://login.1688.com/", headers=headers, allow_redirects=True) as response:
                # Обновляем куки
                response_cookies = response.cookies
                for cookie in response_cookies:
                    self.cookies_dict[cookie.key] = cookie.value
            
            # Запрос к API для получения дополнительных кук
            api_headers = headers.copy()
            api_headers.update({
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            })
            
            async with temp_session.get("https://www.1688.com/api/token/init", headers=api_headers) as response:
                # Обновляем куки
                response_cookies = response.cookies
                for cookie in response_cookies:
                    self.cookies_dict[cookie.key] = cookie.value
            
        except Exception:
            # Fallback на базовые куки
            self.cookies_dict = {
                "cna": "Ez7rHJABCwKCAXrD2Q==",
                "_m_h5_tk": "random_token_12345", 
                "_m_h5_tk_enc": "random_enc_token_12345",
            }
        finally:
            # Всегда закрываем временную сессию
            if temp_session and not temp_session.closed:
                await temp_session.close()
    
    async def get_by_id(self, offer_id: str, timeout: float = None) -> DetailProduct:
        """Парсит товар по ID"""
        await self._ensure_initialized()
        
        if timeout is None:
            timeout = self.default_timeout
        
        # Если куки еще не получены, получаем их
        if not self.cookies_dict:
            await self._get_cookies_with_aiohttp()
        
        url = f"https://detail.1688.com/offer/{offer_id}.html"
        
        cookies_str = '; '.join([f'{k}={v}' for k, v in self.cookies_dict.items()])
        
        headers = {
            "cookie": cookies_str,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        
        try:
            async with self._session.get(
                url,
                headers=headers,
                timeout=timeout
            ) as response:

                if response.status == 200:
                    html_content = await response.text()
                    
                    # Ищем JSON данные
                    json_str = self._extract_json_string(html_content)
                    
                    if json_str:
                        # Исправляем JSON перед парсингом
                        fixed_json_str = self._fix_json_issues(json_str)
                        
                        try:
                            product_data = json.loads(fixed_json_str)
                            product = DetailProduct(product_data)
                            return product
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e}")
                            return None
                    else:
                        print("1688.com blocked information from json")
                        return None
                else:
                    print(f"HTTP error: {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            print("Request timeout")
            return None
        except Exception as e:
            print(f"Request error: {e}")
            return None

    def _extract_json_string(self, html_content: str) -> str:
        """Извлекает JSON строку из HTML"""
        pattern = r'window\.contextPath\s*,\s*({.*?})\);'
        match = re.search(pattern, html_content, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            return json_str
        
        return ""

    def _fix_json_issues(self, json_str: str) -> str:
        """Исправляет проблемы в JSON"""
        # Исправляем объект skuWeight
        sku_weight_pattern = r'"skuWeight":\s*\{[^}]+\}'
        def fix_sku_weight(match):
            sku_weight_obj = match.group(0)
            fixed = re.sub(r'(\s*)(\d+)(\s*):(\s*)', r'\1"\2"\3:\4', sku_weight_obj)
            return fixed
        
        fixed_json = re.sub(sku_weight_pattern, fix_sku_weight, json_str)
        
        # Исправляем объект skuFeatures  
        sku_features_pattern = r'"skuFeatures":\s*\{[^}]+\}'
        def fix_sku_features(match):
            sku_features_obj = match.group(0)
            fixed = re.sub(r'(\s*)(\d+)(\s*):(\s*)', r'\1"\2"\3:\4', sku_features_obj)
            return fixed
        
        fixed_json = re.sub(sku_features_pattern, fix_sku_features, fixed_json)
        
        return fixed_json

    @property
    def is_active(self):
        return self._session is not None and not self._session.closed

    def __await__(self):
        return self._create_initialized().__await__()

    async def _create_initialized(self):
        await self._initialize()
        return self