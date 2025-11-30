# 1688 API Search by Image 

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

with Sync1688Session(debug = False, proxy = proxy) as session:
    products = session.search_by_image("path/to/image.jpg")
```

### Asynchronous version

```python
from search1688api import Async1688Session
import asyncio

async def main():

    async with Async1688Session(debug = False, proxy = proxy) as session:

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

## Лицензия
MIT
