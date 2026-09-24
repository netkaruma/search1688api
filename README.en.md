# 1688 API Search by Image|Text 

A Python library for searching products on 1688.com by image|text.

Python библиотека для поиска товаров на 1688.com по изображению.

## Установка|Setup

```bash
pip install search1688api
```

## Usage

### Synchronous version

```python
from search1688api import Sync1688Session

proxies = {
    "http": "http://user:password@proxy.example.com:8080",
    "https": "http://user:password@proxy.example.com:8080",
}

with Sync1688Session(debug = False, proxies = proxies) as session:

    # authorization token, if needed
    session.cookies_dict['_m_h5_tk'] = 'a5684f3729bb00ef0c8208249107d061_1720690129578'

    products = session.search_by_image("path/to/image.jpg")
    products = session.search_by_text("search query")
```

### Asynchronous version

```python
from search1688api import Async1688Session
import asyncio

proxy_url = "http://user:password@proxy.example.com:8080"

async def main():

    async with Async1688Session(debug = False, proxy = proxy_url) as session:
        response = await session.search_by_image("path/to/image.jpg")
        response = await session.search_by_text("rose-colored glasses")
        
asyncio.run(main())
```

## Methods
```python
search_by_image(image_path: str, debug = True) -> List[]
search_by_text(image_path: str, debug = True) -> List[]
```

### Options:
1. **image_path** - path to the image file
2. **debug** - using logging


## LICENSE
MIT
