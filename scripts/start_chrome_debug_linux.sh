#!/bin/bash
# Start Chrome with remote debugging for CDP connection (Linux version)
# This allows Playwright to connect to real Chrome (bypasses all bot detection)

echo "🚀 Запуск Chrome с remote debugging (Linux)..."
echo ""
echo "Chrome будет доступен на порту 9222"
echo "Используй Ctrl+C для остановки"
echo ""

# Check if Chrome is already running on port 9222
if lsof -Pi :9222 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Порт 9222 уже занят!"
    echo "   Возможно Chrome уже запущен с debugging."
    echo "   Закройте существующий процесс или используйте другой порт."
    exit 1
fi

# Try to find Chrome/Chromium executable
CHROME=""
for cmd in google-chrome google-chrome-stable chromium-browser chromium; do
    if command -v $cmd &> /dev/null; then
        CHROME=$cmd
        break
    fi
done

if [ -z "$CHROME" ]; then
    # Try Playwright's Chromium
    PLAYWRIGHT_CHROME=$(python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path)" 2>/dev/null)
    if [ -n "$PLAYWRIGHT_CHROME" ] && [ -f "$PLAYWRIGHT_CHROME" ]; then
        CHROME="$PLAYWRIGHT_CHROME"
    else
        echo "❌ Chrome/Chromium не найден!"
        echo "   Установите Chrome или Chromium:"
        echo "   - Ubuntu/Debian: sudo apt install google-chrome-stable"
        echo "   - Fedora: sudo dnf install google-chrome-stable"
        echo "   - Или используйте Playwright: playwright install chromium"
        exit 1
    fi
fi

echo "Используется: $CHROME"
echo ""

# Start Chrome with remote debugging
"$CHROME" \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug-profile" \
  --no-first-run \
  --no-default-browser-check \
  2>&1 | grep -v "ERROR\|WARNING" &

CHROME_PID=$!

echo "✅ Chrome запущен (PID: $CHROME_PID)"
echo ""
echo "Теперь можете запускать парсер с use_cdp=True"
echo ""
echo "Для остановки Chrome:"
echo "  kill $CHROME_PID"
echo ""

# Keep script running
wait $CHROME_PID
