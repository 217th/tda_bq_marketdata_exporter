# Query Patterns - Подробное описание

## Обзор стратегий запросов

Все три режима запросов должны удовлетворять требованию партиционирования таблицы по `timestamp`.

---

## 1. Режим ALL - Все доступные записи

### Цель
Получить все доступные записи для указанного символа и таймфрейма.

### Проблема
Таблица партиционирована - нельзя запросить "все" без временных границ.

### Решение
Использовать весь исторический диапазон (15 лет).

### SQL Query
```sql
SELECT 
  timestamp,
  open,
  high,
  low,
  close,
  volume
FROM `{project}.{dataset}.{table}`
WHERE 
  symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5475 DAY)  -- 15 лет истории
  AND timestamp <= CURRENT_TIMESTAMP()
  [AND exchange = @exchange]  -- опционально
ORDER BY timestamp ASC
```

### Параметры
- `symbol`: Обязательный
- `timeframe`: Обязательный
- `exchange`: Опциональный
- Временной диапазон: Последние 15 лет (5475 дней)

### Пример использования
```bash
python main.py --symbol BTCUSDT --timeframe 1d --all
```

---

## 2. Режим RANGE - Диапазон дат

### Цель
Получить записи в явно указанном временном диапазоне.

### SQL Query
```sql
SELECT 
  timestamp,
  open,
  high,
  low,
  close,
  volume
FROM `{project}.{dataset}.{table}`
WHERE 
  symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp >= @from_timestamp  -- удовлетворяет партиции
  AND timestamp <= @to_timestamp    -- удовлетворяет партиции
  [AND exchange = @exchange]  -- опционально
ORDER BY timestamp ASC
```

### Параметры
- `symbol`: Обязательный
- `timeframe`: Обязательный
- `from_timestamp`: Обязательный
- `to_timestamp`: Обязательный
- `exchange`: Опциональный

### Валидация
- `from_timestamp` должен быть <= `to_timestamp`
- Диапазон не должен быть слишком большим (рекомендация: максимум 2 года)

### Пример использования
```bash
python main.py --symbol ETHUSDT --timeframe 1h \
  --from 2024-01-01T00:00:00 \
  --to 2024-01-31T23:59:59
```

---

## 3. Режим NEIGHBORHOOD - Окрестность точки

### Цель
Получить точное количество записей до и после указанного timestamp.

### Стратегия
Используем три отдельных запроса с UNION ALL:
1. N записей ДО центральной точки
2. Центральная запись (опционально)
3. N записей ПОСЛЕ центральной точки

### SQL Query - Композитный подход

#### Подзапрос 1: Записи ДО центральной точки
```sql
-- Для timeframe='1M', n_before=3: adaptive_window будет ~108 дней (3.6 месяца)
-- Для timeframe='1d', n_before=100: adaptive_window будет ~120 дней
SELECT 
  timestamp,
  open,
  high,
  low,
  close,
  volume
FROM `{project}.{dataset}.{table}`
WHERE 
  symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp < @center_timestamp
  AND timestamp >= TIMESTAMP_SUB(@center_timestamp, INTERVAL @adaptive_window_days DAY)
ORDER BY timestamp DESC  -- от центра в прошлое
LIMIT @n_before
```

#### Подзапрос 2: Центральная запись
```sql
SELECT 
  timestamp,
  open,
  high,
  low,
  close,
  volume
FROM `{project}.{dataset}.{table}`
WHERE 
  symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp = @center_timestamp
LIMIT 1
```

#### Подзапрос 3: Записи ПОСЛЕ центральной точки
```sql
SELECT 
  timestamp,
  open,
  high,
  low,
  close,
  volume
FROM `{project}.{dataset}.{table}`
WHERE 
  symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp > @center_timestamp
  AND timestamp <= TIMESTAMP_ADD(@center_timestamp, INTERVAL @adaptive_window_days DAY)
ORDER BY timestamp ASC  -- от центра в будущее
LIMIT @n_after
```

#### Финальный запрос с UNION ALL
```sql
-- Пример: symbol='BTCUSDT', timeframe='1M', center='2024-01-15', n_before=3, n_after=3
-- adaptive_window_days будет рассчитан как ~108 дней (достаточно для 3 месячных свечей)

(
  -- Before records (reverse order, will be sorted later)
  SELECT timestamp, open, high, low, close, volume
  FROM `{project}.{dataset}.{table}`
  WHERE symbol = @symbol
    AND timeframe = @timeframe
    AND timestamp < @center_timestamp
    AND timestamp >= TIMESTAMP_SUB(@center_timestamp, INTERVAL @adaptive_window_days DAY)
  ORDER BY timestamp DESC
  LIMIT @n_before
)

UNION ALL

(
  -- Center record
  SELECT timestamp, open, high, low, close, volume
  FROM `{project}.{dataset}.{table}`
  WHERE symbol = @symbol
    AND timeframe = @timeframe
    AND timestamp = @center_timestamp
  LIMIT 1
)

UNION ALL

(
  -- After records
  SELECT timestamp, open, high, low, close, volume
  FROM `{project}.{dataset}.{table}`
  WHERE symbol = @symbol
    AND timeframe = @timeframe
    AND timestamp > @center_timestamp
    AND timestamp <= TIMESTAMP_ADD(@center_timestamp, INTERVAL @adaptive_window_days DAY)
  ORDER BY timestamp ASC
  LIMIT @n_after
)

ORDER BY timestamp ASC  -- Итоговая сортировка
```

**Важные примеры расчёта окна:**

| Timeframe | Records | Window calculation | Days needed |
|-----------|---------|-------------------|-------------|
| 1M        | 3       | 3 / (1/30) * 1.2 = 108 | ~108 дней (3.6 месяца) |
| 1M        | 12      | 12 / (1/30) * 1.2 = 432 | ~432 дня (~14 месяцев) |
| 1w        | 10      | 10 / (1/7) * 1.2 = 84 | ~84 дня (~12 недель) |
| 1d        | 100     | 100 / 1 * 1.2 = 120 | ~120 дней |
| 4h        | 100     | 100 / 6 * 1.2 = 20 | ~20 дней |
| 1h        | 100     | 100 / 24 * 1.2 = 5 | ~5 дней |

### Адаптивное окно

Окно должно быть достаточным для получения нужного количества записей:

| Timeframe | Дней в одной свече | Окно для 100 свечей | Окно для 1000 свечей |
|-----------|--------------------|---------------------|----------------------|
| 1M        | ~30                | ~3000 дней (~8 лет) | ~30000 дней (~82 года) |
| 1w        | ~7                 | ~700 дней (~2 года) | ~7000 дней (~19 лет) |
| 1d        | 1                  | ~100 дней           | ~1000 дней (~3 года) |
| 4h        | 0.167              | ~17 дней            | ~167 дней            |
| 1h        | 0.042              | ~5 дней             | ~42 дня              |
| 15m       | 0.010              | ~1 день             | ~10 дней             |
| 5m        | 0.003              | ~8 часов            | ~3 дня               |
| 1m        | 0.0007             | ~2 часа             | ~17 часов            |

**Примеры:**
- 1M, 3 свечи: требуется окно ~90 дней (3 месяца)
- 1w, 10 свечей: требуется окно ~70 дней (10 недель)
- 1d, 100 свечей: требуется окно ~100 дней

### Расчёт адаптивного окна в коде

```python
def calculate_adaptive_window(timeframe: str, records_needed: int) -> int:
    """
    Вычисляет окно в днях для получения нужного количества записей.
    
    Args:
        timeframe: Таймфрейм ('1M', '1w', '1d', '4h', '1h', '15', '5', '1')
        records_needed: Максимум из (n_before, n_after)
        
    Returns:
        Количество дней для окна
    """
    # Приблизительное количество записей в день для каждого таймфрейма
    records_per_day = {
        '1M': 1/30,      # ~1 запись в 30 дней
        '1w': 1/7,       # ~1 запись в 7 дней
        '1d': 1,         # 1 запись в день
        '4h': 6,         # 6 записей в день
        '1h': 24,        # 24 записи в день
        '15': 96,        # 96 записей в день (15 минут)
        '5': 288,        # 288 записей в день (5 минут)
        '1': 1440,       # 1440 записей в день (1 минута)
    }
    
    rpd = records_per_day.get(timeframe, 1)
    
    # Добавляем 20% запас на пропуски в данных
    days_needed = int((records_needed / rpd) * 1.2)
    
    # Минимум 1 день, максимум 365 дней
    return max(1, min(365, days_needed))
```

### Параметры
- `symbol`: Обязательный
- `timeframe`: Обязательный
- `center_timestamp`: Обязательный
- `n_before`: Количество записей до (обязательный)
- `n_after`: Количество записей после (обязательный)
- `exchange`: Опциональный

### Валидация
- `n_before` и `n_after` должны быть > 0
- `center_timestamp` должен быть валидным timestamp
- Адаптивное окно не должно превышать разумных пределов

### Пример использования
```bash
python main.py --symbol BTCUSDT --timeframe 15 \
  --around 2024-01-15T10:30:00 \
  --before 100 \
  --after 100
```

**Ожидаемый результат**: Ровно 201 запись (или меньше, если данных недостаточно)

---

## Обработка граничных случаев

### Недостаточно данных в NEIGHBORHOOD режиме

Если запрошено 100 записей до, но доступно только 50:
- Вернуть доступные 50 записей
- Логировать предупреждение
- Указать в метаданных фактическое количество

```json
{
  "metadata": {
    "requested_before": 100,
    "returned_before": 50,
    "requested_after": 100,
    "returned_after": 100,
    "warning": "Insufficient data before center point"
  },
  "candle_fields": [...],
  "data": [...]
}
```

### Центральная точка не найдена

Если timestamp в `--around` не существует:
- Логировать предупреждение
- Продолжить с записями до/после
- Или: Найти ближайший timestamp и использовать его

### Пустой результат

Если нет данных в указанном диапазоне:
- Вернуть пустой массив data
- Логировать информацию
- Выходной код успешный (не ошибка)

```json
{
  "candle_fields": ["date", "open", "high", "low", "close", "volume"],
  "data": []
}
```

---

## Оптимизация производительности

### Индексы
Предполагается, что таблица имеет индексы на:
- `(symbol, timeframe, timestamp)` - составной индекс для всех запросов

### Размер данных для --all режима

Примерные объёмы данных за 15 лет:

| Timeframe | Записей за 15 лет | Примерный размер |
|-----------|-------------------|------------------|
| 1M        | ~180              | Минимальный      |
| 1w        | ~780              | Маленький        |
| 1d        | ~5,475            | Средний          |
| 4h        | ~32,850           | Большой          |
| 1h        | ~131,400          | Очень большой    |
| 15m       | ~525,600          | Огромный         |
| 5m        | ~1,576,800        | Критический      |
| 1m        | ~7,884,000        | Экстремальный    |

**Рекомендации:**
- Для минутных таймфреймов (1m, 5m) рассмотреть pagination или warning пользователю
- Для часовых и выше - можно загружать одним запросом
- Можно добавить опцию `--max-records` для ограничения

### Кеширование
Для режима NEIGHBORHOOD можно кешировать промежуточные результаты, если делается несколько запросов подряд с близкими параметрами.

### Batch запросы
Если нужны данные для нескольких символов - делать параллельные запросы (вне scope текущей задачи).

---

## Примеры результатов

### Успешный запрос
```json
{
  "candle_fields": ["date", "open", "high", "low", "close", "volume"],
  "data": [
    {
      "date": "2024-01-01T00:00:00Z",
      "open": 43000.5,
      "high": 43250.0,
      "low": 42800.0,
      "close": 43100.25,
      "volume": 1234.567
    },
    ...
  ]
}
```

### Запрос с предупреждением
```json
{
  "metadata": {
    "warning": "Only 50 records available before center point (requested 100)"
  },
  "candle_fields": ["date", "open", "high", "low", "close", "volume"],
  "data": [...]
}
```

