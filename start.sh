#!/bin/bash
# モメンタムダッシュボード ローカル起動スクリプト

cd "$(dirname "$0")"

if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

pip install -q -r requirements.txt

echo ""
echo "▲ Momentum Dashboard 起動中..."
echo "   http://localhost:5000"
echo ""

python3 app.py
