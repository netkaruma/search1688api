import base64
import time
import hashlib
import json
from typing import Dict, List

def extract_products_from_html(html_content: str) -> List[Dict]:
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
        
        # Вместо создания объектов Product, сразу возвращаем словари
        for offer_data in offer_list:
            try:
                # Просто добавляем сырые данные оффера как словарь
                if isinstance(offer_data, dict):
                    products.append(offer_data)
            except Exception:
                continue
                
    except Exception:
        pass
    
    return products

def prepare_image_request(image_b64: str) -> str:
    params_data = {
        "searchScene": "imageEx",
        "interfaceName": "imageBase64ToImageId",
        "serviceParam.extendParam[imageBase64]": image_b64,
        "subChannel": "pc_image_search_image_id"
    }
    
    request_data = {
        "appId": 32517,
        "params": json.dumps(params_data, ensure_ascii=False)
    }
    
    return json.dumps(request_data, ensure_ascii=False)


def generate_sign(token_part: str, timestamp: str, app_key: str, data_string: str) -> str:
    if not token_part:
        raise ValueError("Токен не установлен")
    
    sign_string = f"{token_part}&{timestamp}&{app_key}&{data_string}"
    md5_hash = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
    return md5_hash


def read_and_encode_image(image_path: str) -> str:
    try:
        with open(image_path, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
        return image_b64
    except Exception as e:
        raise ValueError(f"Ошибка чтения файла: {e}")