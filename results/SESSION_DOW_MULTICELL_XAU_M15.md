# انتخابِ زیرمجموعهٔ چند-سلولی روز×سشن برای رساندنِ WR به ≥۶۰٪ — XAUUSD M15

> بازه: 2020-02-20 → 2026-07-07 | روش: greedy روی سلول‌های (روز × سشنِ اصلیِ پارتیشن‌شده) با WR نزولی.
> شرط: WR ترکیبی ≥60% و n کل ≥60 و n هر سلول ≥15.

⚠️ **این گام in-sample است** (انتخابِ سلول روی کلِ داده). کاندیدِ امیدوارکننده باید در گامِ بعد walk-forward شود.

| لایه | #سلول‌های منتخب | ترکیب | WR ترکیبی | n | net زیرمجموعه | تصمیم |
|---|---|---|---|---|---|---|
| S139 Overnight (Long) | 1 | Mon×Sydney | 48.4% | 246 | -63$ | ❌ حتی بهترین ترکیب WR=48%<۶۰ |
| S140++ Monday (Long) | 1 | Mon×NewYork | 41.1% | 409 | +8,706$ | ❌ حتی بهترین ترکیب WR=41%<۶۰ |
| S141 Turn-of-Month (Long) | 1 | Wed×London | 60.0% | 15 | +3,712$ | 🟡 WR پاس ولی n=15<60 |
| S142+ Mid-Month (Long) | 1 | Thu×Tokyo | 46.2% | 39 | +3,300$ | ❌ حتی بهترین ترکیب WR=46%<۶۰ |
| S144 End-of-Month Pre-End (Long) | 1 | Tue×NewYork | 50.0% | 36 | -257$ | ❌ حتی بهترین ترکیب WR=50%<۶۰ |
| SHORT-MA-Confluence (Short) | 1 | Tue×Sydney | 56.4% | 55 | +9,537$ | ❌ حتی بهترین ترکیب WR=56%<۶۰ |
| S168 Brooks High-2 (Long) | 1 | Thu×Tokyo | 53.6% | 138 | +870$ | ❌ حتی بهترین ترکیب WR=54%<۶۰ |
| S171 Signs-of-Strength (Long) | 6 | Fri×NewYork، Mon×NewYork، Thu×NewYork، Thu×London، Wed×Tokyo، Fri×Tokyo | 60.4% | 318 | +8,495$ | ✅ کاندیدِ بهبود (به WF برود) |
| S132/S136/S138 Squeeze→Breakout (Long) | 1 | Mon×NewYork | 53.8% | 26 | +162$ | ❌ حتی بهترین ترکیب WR=54%<۶۰ |
