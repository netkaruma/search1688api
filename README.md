# 1688 Search API by Image 

Python библиотека для поиска товаров на 1688.com по изображению.
А также парсинга данных товаров по ID/Артикулу

## Установка

```bash
pip install search1688api
```

## Использование

### Синхронная версия

```python
from search1688api import Sync1688Session

with Sync1688Session() as session:
    # Поиск по изображению
    products = session.search_by_image("path/to/image.jpg")
    for product in products:
        print(product.name)
        print(product.url)
        print(product.company)
        print(product.price)
    
    # Получение детальной информации о товаре по ID
    detailed_product = session.get_by_id("741375431874")
    if detailed_product:
        print(detailed_product.to_dict())
```

### Асинхронная версия

```python
import asyncio
from search1688api import Async1688Session

async def main():
    async with Async1688Session() as session:
        # Поиск по изображению
        products = await session.search_by_image("path/to/image.jpg")
        for product in products:
            print(product.name)
            print(product.url)
            print(product.company)
            print(product.price)
        
        # Получение детальной информации о товаре по ID
        detailed_product = await session.get_by_id("741375431874")
        if detailed_product:
            print(detailed_product.to_dict())

asyncio.run(main())
```
## Настройка таймаута
### При создании сессии

```python
# Таймаут по умолчанию 30 секунд
session = Sync1688Session()

# Установить кастомный таймаут
session = Sync1688Session(default_timeout=60)  # 60 секунд
```

### Для отдельных запросов
```python
# Использовать таймаут по умолчанию
products = session.search_by_image("image.jpg")
detailed = session.get_by_id("123456")

# Установить таймаут для конкретного запроса
products = session.search_by_image("image.jpg", timeout=10)  # 10 секунд
detailed = session.get_by_id("123456", timeout=15)           # 15 секунд
```
### Изменение таймаута после создания
```python
session = Sync1688Session()
session.default_timeout = 45  # Теперь все запросы будут с таймаутом 45 секунд
```
## Модель Product

## Класс Product содержит следующие атрибуты:
| Атрибут             | Тип          | Описание                                                                            |
| ------------------- | ------------ | ----------------------------------------------------------------------------------- |
| `id`                | `str`        | Уникальный идентификатор товара на 1688                                             |
| `name`              | `str`        | Полное название товара                                                              |
| `simple_name`       | `str`        | Упрощённое/сокращённое название товара                                              |
| `brief`             | `str`        | Краткое описание товара                                                             |
| `company`           | `str`        | Название компании-продавца                                                          |
| `company_location`  | `str`        | Регион продавца (провинция и город)                                                 |
| `credit_level`      | `str`        | Уровень доверия продавца (рейтинг)                                                  |
| `is_factory`        | `bool`       | Является ли продавец фабрикой (`True`/`False`)                                      |
| `price`             | `str`        | Основная цена товара                                                                |
| `quantity_prices`   | `List[Dict]` | Список цен в зависимости от количества. Пример: `[{"quantity": 2, "price": "¥10"}]` |
| `image_url`         | `str`        | Ссылка на основное изображение товара                                               |
| `image_url_220x220` | `str`        | Ссылка на изображение размером 220x220                                              |
| `booked_count`      | `int`        | Количество забронированных единиц                                                   |
| `sale_quantity`     | `int`        | Количество проданных единиц                                                         |
| `quantity_begin`    | `int`        | Минимальное количество заказа                                                       |
| `url`               | `str`        | Прямая ссылка на страницу товара (`https://detail.1688.com/offer/{id}.html`)        |
| `category_id`       | `int`        | Идентификатор категории товара                                                      |
| `tags`              | `List[str]`  | Список идентификаторов тегов (рыночные, членские, праздничные и т. д.)              |
| `service_labels`    | `List[str]`  | Список активных сервисных меток (например, «Быстрая доставка»)                      |
| `raw_data`          | `Dict`       | Исходные данные товара из JSON ответа                                               |
## Класс DetailProduct (парсинг по ID)
| Атрибут | Тип | Описание |
|---------|-----|-----------|
| `id` | `str` | ID товара |
| `name` | `str` | Название товара |
| `brand` | `str` | Бренд товара |
| `company` | `str` | Название компании |
| `grade` | `str` | Рейтинг товара |
| `weight` | `str` | Вес/объем товара |
| `goods` | `List[Dict]` | Список вариантов товара с ценами и изображениями |
| `repeat_orders` | `str` | Процент повторных заказов |
| `saledCount` | `int` | Количество продаж |
| `raw_data` | `Dict` | Исходные данные товара из JSON ответа |

## Методы
```python
search_by_image(image_path: str, timeout: float = None) -> List[Product]
```

### Параметры:
1. **image_path** - путь к файлу изображения
2. **timeout** - таймаут запроса в секундах (по умолчанию используется default_timeout сессии)
### Возвращает: список объектов Product

```python
get_by_id(offer_id: str, timeout: float = None) -> DetailProduct
```
### Получение детальной информации о товаре по его ID.
### Параметры:
1. **offer_id** - ID товара на 1688.com
2. **timeout** - таймаут запроса в секундах (по умолчанию используется default_timeout сессии)
### Возвращает: объект DetailProduct или None если товар не найден

## Конвертация в словарь
```python
product_dict = product.to_dict()
detailed_product_dict = detailed_product.to_dict()
```

## Пример конвертации в словарь
```python
product_dict = product.to_dict()
print(product_dict)
```

## Работа с вариантами товара
```python
detailed_product = session.get_by_id("741375431874", timeout=30)
if detailed_product:
    for variant in detailed_product.goods:
        print(f"Вариант: {variant['name']}")
        print(f"Цена: {variant['price']}")
        print(f"Изображение: {variant['imageUrl']}")
```

## Лицензия

MIT
