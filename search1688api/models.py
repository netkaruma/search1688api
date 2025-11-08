import json
import re
from typing import List, Dict, Any

class Product:
    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.id = data.get("id")
        self.name = data.get("information", {}).get("subject", "")
        self.simple_name = data.get("information", {}).get("simpleSubject", "")
        self.brief = data.get("information", {}).get("brief", "")
        
        company = data.get("company", {})
        self.company = company.get("name", "")
        self.company_location = f"{company.get('province', '')} {company.get('city', '')}".strip()
        self.credit_level = company.get("creditLevelText", "")
        self.is_factory = company.get("isFactory") == "Y"
        
        price_info = data.get("tradePrice", {}).get("offerPrice", {})
        self.price = price_info.get("valueString", "")
        self.quantity_prices = self._parse_quantity_prices(price_info.get("quantityPrices", []))
        
        image_info = data.get("image", {})
        self.image_url = image_info.get("imgUrl", "")
        self.image_url_220x220 = image_info.get("imgUrlOf220x220", "")
        
        trade_quantity = data.get("tradeQuantity", {})
        self.booked_count = trade_quantity.get("bookedCount", 0)
        self.sale_quantity = trade_quantity.get("saleQuantity", 0)
        self.quantity_begin = trade_quantity.get("quantityBegin", 1)
        
        self.url = f"https://detail.1688.com/offer/{self.id}.html" if self.id else ""
        self.category_id = data.get("information", {}).get("categoryId")
        self.features = data.get("features", {}).get("list", [])
        
        self.tags = []
        market_tags = data.get("marketOfferTag", {})
        self.tags.extend(market_tags.get("offerTagIds", []))
        self.tags.extend(market_tags.get("memberTagIds", []))
        self.tags.extend(market_tags.get("holidayTagIds", []))
        
        self.service_labels = []
        common_labels = data.get("commonPositionLabels", {}).get("offerMiddle", [])
        for label in common_labels:
            if label.get("enable"):
                self.service_labels.append(label.get("text", ""))
    
    def _parse_quantity_prices(self, quantity_prices: List[Dict]) -> List[Dict]:
        parsed_prices = []
        for qp in quantity_prices:
            quantity = qp.get("quantity", "")
            price = qp.get("valueString", "")
            if price:
                parsed_prices.append({
                    "quantity": quantity,
                    "price": price
                })
        return parsed_prices
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "simple_name": self.simple_name,
            "brief": self.brief,
            "company": self.company,
            "company_location": self.company_location,
            "credit_level": self.credit_level,
            "is_factory": self.is_factory,
            "price": self.price,
            "quantity_prices": self.quantity_prices,
            "image_url": self.image_url,
            "image_url_220x220": self.image_url_220x220,
            "booked_count": self.booked_count,
            "sale_quantity": self.sale_quantity,
            "min_quantity": self.quantity_begin,
            "url": self.url,
            "category_id": self.category_id,
            "tags": self.tags,
            "service_labels": self.service_labels
        }
    
    def __str__(self):
        return f"Product(id={self.id}, name={self.simple_name[:50]}..., price={self.price}, company={self.company})"
    
    def __repr__(self):
        return f"Product(id={self.id}, name={self.simple_name[:30]}...)"


class DetailProduct:
    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self._extract_data()
    
    def _extract_data(self):
        """Извлекает все данные из JSON структуры"""
        try:
            # ID товара
            self.id = self._get_nested_value(["result", "data", "shippingServices", "fields", "deliveryLimitTimeModel", "offerId"])
            
            # Название товара
            self.name = self._get_nested_value(["result", "data", "gallery", "fields", "subject"])
            
            # Бренд и вес из featureAttributes
            attributes = self._get_nested_value(["result", "global", "globalData", "model", "offerDetail", "featureAttributes"])
            self.brand = None
            self.weight = None
            if attributes:
                for attr in attributes:
                    if attr.get("name") == "品牌":
                        self.brand = attr.get("value")
                    if attr.get("name") == "净含量":
                        self.weight = attr.get("value")
            
            # Компания
            self.company = self._get_nested_value(["result", "data", "Root", "fields", "dataJson", "tempModel", "companyName"])
            
            # Названия товаров (goods) с ценами и картинками
            self.goods = []
            
            # ПРАВИЛЬНЫЙ путь к данным
            sku_props = self._get_nested_value(["result", "data", "Root", "fields", "dataJson", "skuModel", "skuProps"])
            sku_info_map = self._get_nested_value(["result", "data", "Root", "fields", "dataJson", "skuModel", "skuInfoMap"])
            
            if sku_props and len(sku_props) > 0 and 'value' in sku_props[0]:
                goods_data = sku_props[0]['value']
                
                if goods_data and sku_info_map:
                    for good in goods_data:
                        good_name = good.get("name")
                        image_url = good.get("imageUrl")
                        
                        # Получаем цену из skuInfoMap
                        price = None
                        if good_name in sku_info_map:
                            price = sku_info_map[good_name].get("price")
                        
                        # Добавляем товар с названием, ценой и картинкой
                        self.goods.append({
                            "name": good_name,
                            "price": price,
                            "imageUrl": image_url
                        })
            
            # Рейтинг
            self.grade = self._get_nested_value(["result", "data", "productTitle", "fields", "rateInfo", "goodsGrade"])
            
            # Процент повторных заказов
            self.repeat_orders = self._get_nested_value(["result", "data", "productTitle", "fields", "shopInfo", "byrRepeatRate3m"])
            
            # Количество продаж
            self.saledCount = self._get_nested_value(["result", "data", "Root", "fields", "dataJson", "tempModel", "saledCount"])
            
        except Exception:
            pass
    
    def _get_nested_value(self, keys: List[str]):
        """Безопасно получает значение из вложенной структуры"""
        current = self.raw_data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def to_dict(self) -> Dict[str, Any]:
        """Возвращает данные в виде словаря"""
        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "company": self.company,
            "grade": self.grade,
            "weight": self.weight,
            "goods": self.goods,
            "repeat_orders": self.repeat_orders,
            "saledCount": self.saledCount
        }


def extract_products_from_html(html_content: str) -> List[Product]:
    products = []
    
    try:
        patterns = [
            r'window\.data\.offerresultData\s*=\s*successDataCheck\(\s*({.*?})\s*\)',
            r'window\.data\.offerresultData\s*=\s*({.*?});',
            r'offerresultData\s*=\s*successDataCheck\(\s*({.*?})\s*\)'
        ]
        
        json_data = None
        for pattern in patterns:
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    data = json.loads(json_str)
                    json_data = data
                    break
                except json.JSONDecodeError:
                    continue
        
        if not json_data:
            return products
        
        offer_list = []
        
        if "data" in json_data and "offerList" in json_data["data"]:
            offer_list = json_data["data"]["offerList"]
        elif "offerList" in json_data:
            offer_list = json_data["offerList"]
        else:
            def find_offer_list(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == "offerList" and isinstance(value, list):
                            return value
                        result = find_offer_list(value)
                        if result is not None:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_offer_list(item)
                        if result is not None:
                            return result
                return None
            
            offer_list = find_offer_list(json_data) or []
        
        for offer_data in offer_list:
            try:
                product = Product(offer_data)
                products.append(product)
            except Exception:
                continue
                
    except Exception:
        pass
    
    return products