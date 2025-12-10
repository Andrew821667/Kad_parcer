# Инструкции по тестированию парсера

## Требования

Для работы парсера с CDP (Chrome DevTools Protocol) необходим запущенный Chrome/Chromium с remote debugging.

## Запуск тестов

### 1. Запустите Chrome с remote debugging

**macOS:**
```bash
./scripts/start_chrome_debug.sh
```

**Linux:**
```bash
./scripts/start_chrome_debug_linux.sh
```

**Windows:**
```powershell
# Найдите путь к Chrome (обычно):
# C:\Program Files\Google\Chrome\Application\chrome.exe

"C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="C:\temp\chrome-debug-profile" `
  --no-first-run `
  --no-default-browser-check
```

### 2. Запустите тест

В новом терминале:

```bash
# Тест полного workflow: парсинг 3 страниц + скачивание 5 PDF актов
python scripts/test_full_workflow.py

# Тест только парсинга (3 страницы, ~75 дел)
python scripts/test_parser_pagination.py

# Debug скрипт для анализа страницы дела
python scripts/debug_case_page.py
```

## Что тестируется

### test_full_workflow.py

1. **Парсинг 3 страниц** (~75 дел) с корректным извлечением всех полей:
   - Номер дела (case_number)
   - Дата (case_date)
   - Судья (judge)
   - Суд (court)
   - Истец (plaintiff)
   - Ответчики (respondents)

2. **Скачивание 5 судебных актов** (PDF):
   - Выбор 5 случайных дел из спарсенных
   - Переход на страницу каждого дела
   - Поиск прямых ссылок на PDF (a[href$=".pdf"])
   - Скачивание PDF файлов в ~/Downloads/kad_test/
   - Проверка размера файлов

## Ожидаемый результат

После успешного выполнения `test_full_workflow.py`:

1. В консоли будет выведена информация о 75 спарсенных делах
2. В папке `~/Downloads/kad_test/` будет 5 PDF файлов с судебными актами
3. Файлы должны быть настоящими PDF документами (не HTML страницы)

## Проверка результата

```bash
# Посмотреть скачанные файлы
ls -lh ~/Downloads/kad_test/

# Проверить что это действительно PDF
file ~/Downloads/kad_test/*.pdf

# Открыть PDF для просмотра
xdg-open ~/Downloads/kad_test/СИП-123-2024_*.pdf  # Linux
open ~/Downloads/kad_test/СИП-123-2024_*.pdf       # macOS
```

## Устранение проблем

### Chrome не подключается (ECONNREFUSED)

```
Error: BrowserType.connect_over_cdp: connect ECONNREFUSED 127.0.0.1:9222
```

**Решение:** Убедитесь что Chrome запущен с remote debugging (см. шаг 1)

### Ошибка доступа к kad.arbitr.ru (403 Forbidden)

```
curl: (56) CONNECT tunnel failed, response 403
x-deny-reason: host_not_allowed
```

**Решение:** Запустите тест на локальной машине с прямым доступом к интернету, а не в контейнере или за корпоративным прокси.

### Скачались HTML файлы вместо PDF

Это была проблема в предыдущей версии. Текущая версия использует:
- Прямые ссылки на PDF: `a[href$=".pdf"]`
- Скачивание через новую вкладку с обработчиком download
- Fallback через CDP `Page.printToPDF`

Если проблема повторится, проверьте логи и откройте issue.

## Следующие шаги

После успешного теста:

1. Масштабирование на все 40 страниц (январь 2024)
2. Добавление сохранения в PostgreSQL
3. Расширение на период 2020-2025
4. Добавление поддержки 18 арбитражных судов
