# REPORT — study-planner-copilot

## סיכום תוצאות סופיות (API מול SDK)

| מדד | API | SDK |
|---|---:|---:|
| Mode | real_api | real_sdk |
| Provider | openai | openai |
| Model | gpt-4o-mini | gpt-4o-mini |
| Effort | medium | medium |
| Turns | 7 | 7 |
| Input tokens | 8,458 | 3,004 |
| Cache read tokens | 0 | 0 |
| Cache write tokens | 0 | 0 |
| Output tokens | 403 | 352 |
| Cache ratio* | 0.00% | 0.00% |
| Model calls | 13 | 12 |
| Total cost (USD) | 0.157095 | 0.020300 |
| Total latency (ms) | 17,801 | 635 |
| Checks passed | 5/5 | 5/5 |

\* Cache ratio = cache_read / (input + cache_read)

## LOC לפי חלקי Harness

### API/harness

| רכיב | LOC |
|---|---:|
| loop.py | 94 |
| tools.py | 29 |
| history.py | 28 |
| memory.py | 15 |
| context.py | 35 |
| compaction.py | 20 |
| caching.py | 21 |
| tokens.py | 64 |
| **סה"כ harness** | **307** |

### SDK

| קובץ | LOC |
|---|---:|
| main.py | 179 |
| agent.py | 174 |
| tools.py | 21 |
| **סה"כ SDK harness** | **374** |

> ב-SDK, הקבצים כוללים סימוני `# replaces:` ומרכזים אחריות שנפרסה ב-API למודולים נפרדים.

## איפה ה-SDK חסך ואיפה עלה

### חסך
- עלות כוללת נמוכה יותר משמעותית (`0.0203$` מול `0.1571$`) עם אותו pass rate.
- פחות input tokens ופחות output tokens על אותו תרחיש.

### עלה
- מספר קריאות המודל כמעט זהה (12 מול 13), כלומר החיסכון כאן לא הגיע מקיטון חד בלולאות אלא מהיקף טוקנים בכל קריאה ותמחור.
- מבחינת LOC נטו בגרסה הזו, ה-SDK לא קטן יותר מה-API כי נוספה לוגיקת גישור OpenAI מלאה בתוך `SDK/agent.py`.

## שליטה ב-API מול SDK

- API נותן שליטה מלאה בלולאת הודעות, tool_result format, context compaction, caching hooks וחישובי עלות.
- SDK מפחית תפעול runtime אבל מעביר חלק מהשליטה לפרימיטיבים של ה-SDK.
- בפתרון הזה, כדי לשמור שקיפות מדידה ולוגיקה דומה בין הגרסאות, נוספה מעטפת SDK יחסית מפורטת.

## בחירת גרסה לסוכן הזה

- אם המטרה היא **זמן פיתוח קצר ותחזוקה פשוטה**: לבחור SDK.
- אם המטרה היא **שליטה מלאה בניסוי harness ובניתוח טוקנים**: לבחור API.
- עבור המשימה הנוכחית שתי הגרסאות עומדות בדרישות, עם ריצות אמיתיות ו-`5/5` בדיקות בכל צד.

## הערות הרצה

- API אמיתי: `python API/main.py --scenario scenario.json --out results/api.json --use-real-api`
- SDK אמיתי: `python SDK/main.py --scenario scenario.json --out results/sdk.json --use-real-sdk`
- משתנה סביבה נדרש: `OPENAI_API_KEY` (לא לשמור בקוד/גיט).
