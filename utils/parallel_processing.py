import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Настройка логирования
logger = logging.getLogger("ParallelProcessing")

def run_in_parallel(tasks, max_workers=5):
    """
    Выполняет задачи параллельно в пуле потоков
    
    :param tasks: Список кортежей (функция, аргументы)
    :param max_workers: Максимальное количество потоков
    :return: Список результатов выполнения задач
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Запускаем задачи
        futures = {executor.submit(func, args): (func, args) for func, args in tasks}
        
        # Обрабатываем результаты по мере завершения
        for future in as_completed(futures):
            func, args = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Ошибка в параллельной задаче {func.__name__}{args}: {e}")
    
    return results