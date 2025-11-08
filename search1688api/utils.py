import base64
import time
import hashlib
import json
from typing import Dict, Any


def prepare_image_request(image_b64: str) -> str:
    params_data = {
        "searchScene": "imageEx",
        "interfaceName": "imageBase64ToImageId",
        "serviceParam.extendParam[imageBase64]": image_b64,
        "subChannel": "pc_image_search_image_id"
    }
    
    request_data = {
        "appId": 32517,
        "params": json.dumps(params_data, separators=(',', ':'))
    }
    
    return json.dumps(request_data, separators=(',', ':'))


def generate_sign(token_part: str, timestamp: str, app_key: str, data_string: str) -> str:
    if not token_part:
        raise ValueError("Токен не установлен")
    
    sign_string = f"{token_part}&{timestamp}&{app_key}&{data_string}"
    return hashlib.md5(sign_string.encode('utf-8')).hexdigest()


def read_and_encode_image(image_path: str) -> str:
    try:
        with open(image_path, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
        return image_b64
    except Exception as e:
        raise ValueError(f"Ошибка чтения файла: {e}")