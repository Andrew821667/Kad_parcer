#!/bin/bash
# Start Chrome with remote debugging for CDP connection
# This allows Playwright to connect to real Chrome (bypasses all bot detection)

echo "🚀 Запуск Chrome с remote debugging..."
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

# Start Chrome with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
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
