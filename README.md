# study-planner-copilot

פרויקט משימה: "סוכן אחד, שני harnesses".

## מבנה

- `shared/` — קוד דומיין משותף (כלים, זיכרון, מצב)
- `API/` — גרסת Messages API עם harness ידני מפורק לרכיבים
- `SDK/` — גרסת SDK עם סימוני `# replaces:`
- `tests/` — בדיקות offline עם client מדומה
- `scenario.json` — תרחיש 2 סשנים, 7 תורים
- `results/` — פלטי מדידה (`api.json`, `sdk.json`)
- `REPORT.md` — השוואה מלאה API מול SDK

## התקנה

```bash
python -m pip install -r requirements.txt
```

## הרצה

```bash
python API/main.py --scenario scenario.json --out results/api.json
python SDK/main.py --scenario scenario.json --out results/sdk.json
python -m pytest -q
```

## ריצה אמיתית מול OpenAI API

```bash
# PowerShell
$env:OPENAI_API_KEY="..."
python API/main.py --scenario scenario.json --out results/api.json --use-real-api
python SDK/main.py --scenario scenario.json --out results/sdk.json --use-real-sdk
```

> בגרסה המומרת הזו שתי ההרצות משתמשות ב-`OPENAI_API_KEY` לריצה אמיתית.
