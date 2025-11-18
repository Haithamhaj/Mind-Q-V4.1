#!/bin/bash
# فتح Mind-Q Colab Notebook مباشرة في المتصفح

echo "🚀 فتح Mind-Q Analytics Colab Notebook..."
echo ""

# الرابط المباشر
COLAB_URL="https://colab.research.google.com/github/Haithamhaj/Mind-Q-V4.1/blob/port/update-2025-10-11/Mind_Q_Analytics_Colab.ipynb"

echo "📂 الملف: Mind_Q_Analytics_Colab.ipynb"
echo "🔗 الرابط: $COLAB_URL"
echo ""

# فتح في المتصفح
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$COLAB_URL"
    echo "✅ تم فتح النوتبوك في المتصفح!"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open "$COLAB_URL"
    echo "✅ تم فتح النوتبوك في المتصفح!"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    start "$COLAB_URL"
    echo "✅ تم فتح النوتبوك في المتصفح!"
else
    echo "⚠️  لم أتمكن من التعرف على نظام التشغيل"
    echo "📋 انسخ هذا الرابط يدوياً:"
    echo "$COLAB_URL"
fi

echo ""
echo "💡 نصيحة: إذا لم يفتح تلقائياً، انسخ الرابط أعلاه وافتحه في المتصفح"
echo ""
echo "📖 للمزيد من الطرق، راجع: COLAB_TROUBLESHOOTING.md"
