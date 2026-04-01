"""
Тест производительности скрапинга.
Проверяет: browser pool, кэш, дедупликацию, скорость.

Запуск:
    python test_scraping.py
"""
import asyncio
import time
import logging
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.web_scraping import search_equipment_on_sites_async, close_browser
from cache import cache

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)-15s %(levelname)-7s %(message)s'
)
logger = logging.getLogger("Test")

TEST_ITEMS = [
    "Кабель КВВГнг 4х1.5",
    "Видеокамера DS-2CD2143G2-I",
    "Датчик движения",
    "Блок питания 12В",
    "Кабель КВВГнг 4х1.5",           # дубликат — должен взяться из кэша
    "Кабель  КВВГнг  4x1.5",         # нормализация: лишние пробелы + латинская x
]


async def test_search():
    """Тест поиска с замером времени."""
    print(f"\n{'='*60}")
    print(f"  ТЕСТ ПОИСКА: {len(TEST_ITEMS)} позиций")
    print(f"{'='*60}\n")

    total_start = time.time()
    results_summary = []

    for i, name in enumerate(TEST_ITEMS):
        start = time.time()
        results = await search_equipment_on_sites_async(name)
        elapsed = time.time() - start

        is_cached = elapsed < 1.0
        tag = "CACHE HIT" if is_cached else f"{elapsed:.1f}s"

        print(f"  [{i+1}/{len(TEST_ITEMS)}] '{name}'")
        print(f"         → {len(results)} results ({tag})")
        for r in results[:2]:
            print(f"           {r['site']:6s}: {r['name'][:50]} — {r['price']}₽ [{r['status']}]")
        print()

        results_summary.append({
            'name': name,
            'count': len(results),
            'time': elapsed,
            'cached': is_cached
        })

    total = time.time() - total_start
    cached_count = sum(1 for r in results_summary if r['cached'])

    print(f"{'='*60}")
    print(f"  ИТОГО:")
    print(f"    Время:        {total:.1f}s")
    print(f"    Среднее:      {total/len(TEST_ITEMS):.1f}s / позиция")
    print(f"    Из кэша:      {cached_count}/{len(TEST_ITEMS)}")
    print(f"{'='*60}\n")

    return results_summary


async def test_cache_normalization():
    """Тест нормализации ключей кэша."""
    print(f"\n{'='*60}")
    print(f"  ТЕСТ НОРМАЛИЗАЦИИ КЭША")
    print(f"{'='*60}\n")

    test_cases = [
        ("tinko_Кабель КВВГнг 4х1.5", "tinko_кабель кввгнг 4x1.5"),
        ("luis_Видеокамера  DS-2CD", "luis_видеокамера ds-2cd"),
        ("etm_Блок  питания  12В", "etm_блок питания 12в"),
    ]

    all_passed = True
    for key1, key2 in test_cases:
        path1 = cache._get_cache_path(key1)
        path2 = cache._get_cache_path(key2)
        passed = path1 == path2
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: '{key1}' == '{key2}'")
        if not passed:
            print(f"           path1: {path1}")
            print(f"           path2: {path2}")
            all_passed = False

    print()
    return all_passed


async def test_concurrent_limit():
    """Тест: семафор ограничивает параллельность."""
    print(f"\n{'='*60}")
    print(f"  ТЕСТ ПАРАЛЛЕЛЬНОСТИ (5 запросов одновременно)")
    print(f"{'='*60}\n")

    items = [
        "Тест кабель 1",
        "Тест кабель 2",
        "Тест кабель 3",
        "Тест кабель 4",
        "Тест кабель 5",
    ]

    start = time.time()
    tasks = [search_equipment_on_sites_async(name) for name in items]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    total_results = sum(len(r) for r in results)
    print(f"  5 параллельных запросов: {elapsed:.1f}s")
    print(f"  Всего результатов: {total_results}")
    print(f"  (Если ~8-15с — семафор работает, запросы идут параллельно)")
    print(f"  (Если ~40с+ — запросы идут последовательно, проблема)")
    print()

    return elapsed


async def main():
    print("\n" + "="*60)
    print("  ЗАПУСК ТЕСТОВ СКРАПИНГА")
    print("="*60)

    # Очистка кэша перед тестами
    cache.clear_old_cache()

    try:
        # 1. Нормализация кэша
        cache_ok = await test_cache_normalization()

        # 2. Параллельность
        parallel_time = await test_concurrent_limit()

        # 3. Поиск + кэш
        search_results = await test_search()

        # Итог
        print("\n" + "="*60)
        print("  РЕЗУЛЬТАТЫ:")
        print(f"    Нормализация кэша: {'✅' if cache_ok else '❌'}")
        print(f"    Параллельность:    {'✅' if parallel_time < 60 else '❌'} ({parallel_time:.0f}s)")
        cached = sum(1 for r in search_results if r['cached'])
        print(f"    Кэш попадания:     {cached}/{len(search_results)}"
              f" {'✅' if cached >= 2 else '⚠️ мало попаданий'}")
        print("="*60 + "\n")

    finally:
        await close_browser()
        print("Браузер закрыт.\n")


if __name__ == '__main__':
    asyncio.run(main())
