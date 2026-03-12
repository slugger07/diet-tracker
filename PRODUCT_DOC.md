# 🍛 NutriLog India — Product Document

## Daily Food Nutrition Tracker for Indian Users

**Version**: 1.0 (MVP)  
**Target Users**: You + friends (5–15 people)  
**Budget**: ₹0 — Completely Free Tier  
**Last Updated**: February 2026

---

## 1. Problem Statement

Tracking nutrition in India is broken. Every major app (MyFitnessPal, HealthifyMe, etc.) either:

- Doesn't understand Indian food properly ("roti" could be 70 cal or 150 cal depending on size, atta, and ghee)
- Charges money for decent features
- Has a US/Western-centric food database that makes you search "chapati" five times before giving up
- Doesn't handle regional dishes (poha, upma, vada pav, chole bhature, dosa varieties)

**We want**: A simple app where you type what you ate in plain language, and it gives you accurate nutrition values — for free, forever.

---

## 2. Product Vision

> "Log what you ate in your own words. Get real nutrition numbers. Pay nothing."

**Core Idea**: Use a free LLM (via Ollama locally or Groq's free API) as the brain. It parses your food input, does a web search when needed, extracts nutrition data, and logs everything. No expensive nutrition database subscription required.

---

## 3. The Big Design Question: Do We Even Need a Nutrition Database?

### Your instinct is right — mostly.

If we have a smart LLM + web search, we can look up nutrition for *anything* on the fly. But here's the nuanced answer:

| Approach | Pros | Cons |
|----------|------|------|
| **Pure Web Search + LLM** | No database to maintain; handles any food; always up-to-date | Slower (web call per food); inconsistent results across sources; uses search quota |
| **Pure Database** | Fast; consistent; offline-capable | Expensive/hard to find good Indian data; can't handle everything |
| **Hybrid (Recommended)** | Best of both worlds | Slightly more complex to build |

### ✅ Our Approach: **Search-First with Smart Caching**

```
User types food → LLM parses items
                      ↓
              Check local cache (SQLite)
              ↓ HIT                ↓ MISS
        Return cached data    LLM + Web Search
                              → Extract nutrition
                              → Save to cache
                              → Return to user
```

**Why this works**:
- First lookup for "2 roti with dal" hits the web → gets nutrition → caches it
- Next time anyone logs "roti" or "dal" → instant response from cache
- Over time, your cache becomes YOUR personalized Indian food database
- No need to pre-build or pay for a database — it builds itself from usage

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    USER INTERFACE                     │
│              (Streamlit Web App / CLI)                │
└─────────────────┬───────────────────────────────────┘
                  │ "I ate 2 paratha, curd, and chai"
                  ▼
┌─────────────────────────────────────────────────────┐
│                  LLM BRAIN LAYER                     │
│          (Ollama local  OR  Groq free API)           │
│                                                      │
│  1. Parse input → extract food items + quantities    │
│  2. Check local cache for each item                  │
│  3. If cache miss → trigger web search               │
│  4. Extract structured nutrition from search results  │
│  5. Generate daily summary + insights                │
└────────┬──────────────────┬─────────────────────────┘
         │                  │
         ▼                  ▼
┌────────────────┐  ┌──────────────────────────┐
│  LOCAL CACHE   │  │     WEB SEARCH LAYER     │
│   (SQLite)     │  │                          │
│                │  │  DuckDuckGo (free, no key)│
│ - food_name    │  │  OR                      │
│ - calories     │  │  Tavily (1000 free/mo)   │
│ - protein      │  │  OR                      │
│ - carbs        │  │  SerpAPI (100 free/mo)   │
│ - fat          │  │                          │
│ - fiber        │  └──────────────────────────┘
│ - serving_size │
│ - source_url   │
│ - last_updated │
└────────────────┘
```

---

## 5. Tech Stack — Everything Free

### 5.1 LLM Layer (The Brain)

You have **two options** — pick based on your hardware:

#### Option A: Ollama (Local — Best if you have 8GB+ RAM)

| Detail | Value |
|--------|-------|
| **What** | Run open-source LLMs locally on your machine |
| **Cost** | Completely free, forever |
| **Models** | Llama 3.1 (8B), Mistral 7B, Phi-3, Gemma 2 |
| **Recommended** | `llama3.1:8b` — great balance of speed and intelligence |
| **Install** | `curl -fsSL https://ollama.com/install.sh \| sh` then `ollama pull llama3.1` |
| **Python SDK** | `pip install ollama` |
| **Pros** | No rate limits, no API key, works offline, complete privacy |
| **Cons** | Needs decent hardware (8GB RAM minimum), slower on CPU-only machines |

#### Option B: Groq Cloud API (Best if your machine is slow)

| Detail | Value |
|--------|-------|
| **What** | Free cloud API for open-source LLMs with blazing fast inference |
| **Cost** | Free tier available |
| **Models** | Llama 3.1 8B, Llama 3.1 70B, Mixtral 8x7B, Gemma 2 |
| **Rate Limits** | ~30 requests/min, ~14,400 requests/day on free tier (varies by model) |
| **Python SDK** | `pip install groq` |
| **Pros** | Super fast (fastest LLM API), no hardware needed, generous free tier |
| **Cons** | Needs internet, rate limits exist (but plenty for personal use) |

**Recommendation**: Start with **Groq** for ease of setup. Switch to **Ollama** if you want offline capability or hit rate limits.

---

### 5.2 Web Search Layer (For Nutrition Lookups)

When a food item isn't in our cache, we search the web. Options:

#### Option A: `duckduckgo-search` Python Package ⭐ RECOMMENDED

| Detail | Value |
|--------|-------|
| **What** | Free web search via DuckDuckGo, no API key needed |
| **Cost** | Completely free |
| **Install** | `pip install duckduckgo-search` |
| **Rate Limits** | Unofficial — be reasonable (~50-100 searches/day is fine) |
| **Pros** | Zero setup, no registration, no key management |
| **Cons** | Unofficial wrapper; could break if DDG changes their site |

#### Option B: Tavily Search API

| Detail | Value |
|--------|-------|
| **What** | AI-optimized search API designed for LLM applications |
| **Cost** | Free tier: 1,000 searches/month |
| **Pros** | Returns clean, structured results perfect for LLM consumption |
| **Cons** | 1,000/month limit (enough for ~33 searches/day) |

#### Option C: SerpAPI

| Detail | Value |
|--------|-------|
| **What** | Google Search results as API |
| **Cost** | Free tier: 100 searches/month |
| **Pros** | Google-quality results |
| **Cons** | Only 100/month — too limited as primary source |

**Recommendation**: Use **`duckduckgo-search`** as primary (free, no key). Keep **Tavily** as backup for when DDG results aren't good enough.

---

### 5.3 Data Storage

| Component | Choice | Why |
|-----------|--------|-----|
| **Food Cache** | SQLite | Zero setup, single file, perfect for local app |
| **User Logs** | SQLite | Same DB, separate tables |
| **Config** | `.env` file | Store API keys (Groq, Tavily) securely |

---

### 5.4 Frontend / UI

| Option | Best For | Effort |
|--------|----------|--------|
| **Streamlit** ⭐ | Beautiful web UI, fast to build | Low |
| **CLI (Rich/Typer)** | Terminal lovers, fastest to build | Very Low |
| **FastAPI + HTML** | If you want a proper web app later | Medium |

**Recommendation**: Start with **Streamlit** — it gives you a gorgeous web UI with minimal code, and can be deployed free on Streamlit Community Cloud or Hugging Face Spaces.

---

## 6. Core Features (MVP)

### 6.1 Food Logging (Natural Language)

Users type in plain language. The LLM handles the parsing.

**Example inputs the app should handle**:
```
"2 roti, dal fry, and a glass of chaas"
"had poha for breakfast with chai"
"lunch was rajma chawal and salad"
"1 plate chole bhature from the dhaba"
"protein shake with banana and oats"
"2 egg bhurji with 3 bread slices"
"maggi noodles"
"1 samosa and cutting chai"
```

**LLM Output** (structured JSON):
```json
{
  "items": [
    {"food": "roti (wheat chapati)", "quantity": 2, "unit": "piece"},
    {"food": "dal fry", "quantity": 1, "unit": "bowl (200ml)"},
    {"food": "chaas (buttermilk)", "quantity": 1, "unit": "glass (250ml)"}
  ]
}
```

### 6.2 Nutrition Lookup (Search-First)

For each parsed food item:
1. **Check SQLite cache** — if found and fresh (< 30 days old), use it
2. **If cache miss** — search web: `"roti chapati nutrition per piece calories protein India"`
3. **LLM extracts** structured nutrition from search results
4. **Cache the result** for future lookups

**Nutrition data we capture per item**:
| Field | Unit | Example (1 roti) |
|-------|------|-------------------|
| Calories | kcal | 104 |
| Protein | g | 3.0 |
| Carbohydrates | g | 18.0 |
| Fat | g | 3.5 |
| Fiber | g | 2.0 |
| Serving Size | text | "1 medium (35g atta)" |

### 6.3 Daily Dashboard

Show the user:
- **Meal-wise breakdown** (Breakfast / Lunch / Dinner / Snacks)
- **Daily totals**: Total Calories, Protein, Carbs, Fat, Fiber
- **Visual progress bars** against recommended daily values
- **Simple insights**: "You're low on protein today — consider adding paneer or eggs to dinner"

### 6.4 History & Trends

- View past 7/30 days of logs
- Weekly average nutrition
- Most frequently logged foods

---

## 7. Indian Food — Special Handling

This is what makes our app better than generic trackers:

### 7.1 Portion Size Intelligence

Indian food doesn't come in "1 cup" or "100g" — it comes in:
- **Roti/Chapati**: pieces (small/medium/large)
- **Dal/Curry**: katori/bowl
- **Rice**: plate/katori
- **Chai**: cup/glass (cutting vs full)
- **Snacks**: plate/piece

The LLM prompt will be trained to ask clarifying questions when portions are ambiguous:
> "You said 'rice' — was that approximately 1 katori (~150g) or a full plate (~300g)?"

### 7.2 Regional Food Knowledge

The LLM + web search combo handles regional foods naturally:
- **North**: Paratha, chole, lassi, rajma
- **South**: Dosa, idli, sambhar, rasam, appam
- **West**: Vada pav, dhokla, thepla, poha
- **East**: Machher jhol, rasgulla, litti chokha
- **Street food**: Pani puri, bhel, pav bhaji, momos

Since we search the web, we're not limited to a pre-built database. If someone eats "Kolkata-style egg roll", the web search will find it.

### 7.3 Home-Cooked vs Restaurant

The LLM prompt will default to **home-cooked values** (less oil, less butter) unless the user specifies restaurant/dhaba/takeout, in which case it adjusts upward (typically 1.3x–1.5x calories for restaurant food due to extra oil/butter/cream).

---

## 8. Database Schema

```sql
-- Cached nutrition data (self-building database)
CREATE TABLE food_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_name TEXT NOT NULL,
    food_name_normalized TEXT NOT NULL,  -- lowercase, trimmed
    calories_kcal REAL,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    fiber_g REAL,
    serving_size TEXT,
    serving_weight_g REAL,
    source TEXT,           -- 'web_search', 'manual', 'openfoodfacts'
    source_url TEXT,
    confidence TEXT,       -- 'high', 'medium', 'low'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_count INTEGER DEFAULT 1,
    UNIQUE(food_name_normalized)
);

-- User food logs
CREATE TABLE food_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,      -- simple multi-user (you + friends)
    meal_type TEXT NOT NULL,      -- 'breakfast', 'lunch', 'dinner', 'snack'
    food_name TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT,
    calories_kcal REAL,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    fiber_g REAL,
    logged_at DATE DEFAULT (DATE('now')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily summary (materialized for fast reads)
CREATE TABLE daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    log_date DATE NOT NULL,
    total_calories REAL,
    total_protein REAL,
    total_carbs REAL,
    total_fat REAL,
    total_fiber REAL,
    meal_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_name, log_date)
);

-- Index for fast lookups
CREATE INDEX idx_food_cache_normalized ON food_cache(food_name_normalized);
CREATE INDEX idx_food_logs_user_date ON food_logs(user_name, logged_at);
CREATE INDEX idx_daily_summary_user_date ON daily_summary(user_name, log_date);
```

---

## 9. LLM Prompt Strategy

The quality of this app lives and dies by the prompts. Here are the key ones:

### 9.1 Food Parsing Prompt

```
You are a nutrition assistant for Indian users. Parse the user's food input
and extract individual food items with quantities.

Rules:
- Default to Indian food interpretations (roti = wheat chapati, not tortilla)
- Use Indian portion sizes (katori, glass, plate, piece)
- If quantity is missing, assume 1 standard serving
- If a food could mean multiple things, pick the most common Indian version
- Return ONLY valid JSON, no explanation

Output format:
{
  "meal_type": "breakfast|lunch|dinner|snack",
  "items": [
    {"food": "name", "quantity": number, "unit": "piece|katori|glass|plate|g|ml"}
  ]
}
```

### 9.2 Nutrition Extraction Prompt

```
You are a nutrition data extractor. Given web search results about a food item,
extract the most accurate nutrition values per serving.

Prefer Indian sources (HealthifyMe, nutritionix.in, IFCT data, Indian food blogs).
If values conflict across sources, prefer the median value.
If the food is Indian, use typical Indian preparation methods and portion sizes.

Return ONLY valid JSON:
{
  "food_name": "string",
  "serving_size": "string (e.g., '1 medium piece, ~35g')",
  "serving_weight_g": number,
  "calories_kcal": number,
  "protein_g": number,
  "carbs_g": number,
  "fat_g": number,
  "fiber_g": number,
  "confidence": "high|medium|low",
  "notes": "string (optional, e.g., 'values for home-cooked version')"
}
```

### 9.3 Daily Insight Prompt

```
You are a friendly Indian nutrition coach. Given the user's daily food log
and nutrition totals, provide a brief, actionable insight in 2-3 sentences.

Be culturally relevant — suggest Indian foods (paneer, eggs, dal, sprouts for
protein; fruits, salads for fiber, etc.). Be encouraging, not preachy.
Keep it casual and friendly.
```

---

## 10. Project Structure

```
nutrilog-india/
├── app.py                  # Streamlit main app
├── core/
│   ├── __init__.py
│   ├── llm.py              # LLM interface (Ollama / Groq)
│   ├── search.py           # Web search (DuckDuckGo / Tavily)
│   ├── nutrition.py        # Nutrition extraction pipeline
│   ├── parser.py           # Food input parsing
│   └── cache.py            # SQLite cache operations
├── db/
│   ├── __init__.py
│   ├── models.py           # Database schema & migrations
│   └── queries.py          # CRUD operations
├── ui/
│   ├── __init__.py
│   ├── components.py       # Streamlit UI components
│   └── charts.py           # Visualization helpers
├── config.py               # App configuration
├── requirements.txt        # Dependencies
├── .env.example            # Template for API keys
├── .gitignore              # Excludes .env, __pycache__, *.db
└── tests/
    ├── test_parser.py
    ├── test_nutrition.py
    └── test_cache.py
```

---

## 11. Dependencies

```
# requirements.txt
streamlit>=1.30.0
ollama>=0.4.0               # Local LLM (Option A)
groq>=0.4.0                 # Cloud LLM (Option B)
duckduckgo-search>=6.0.0    # Free web search
pydantic>=2.0.0             # Data validation
python-dotenv>=1.0.0        # Environment variable management
rich>=13.0.0                # Beautiful terminal output (optional CLI)
```

---

## 12. Cost Analysis

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| Ollama (local LLM) | ₹0 | Runs on your machine |
| Groq API (cloud LLM) | ₹0 | Free tier: ~14,400 req/day |
| DuckDuckGo Search | ₹0 | No API key, no limits* |
| Tavily (backup search) | ₹0 | Free: 1,000 searches/month |
| SQLite Database | ₹0 | Local file |
| Streamlit UI | ₹0 | Local or free community cloud |
| **TOTAL** | **₹0/month** | |

*\*Be reasonable with DuckDuckGo — don't hammer it with 1000s of requests/day*

---

## 13. Development Roadmap

### Phase 1: Core MVP (Week 1–2) 🎯

- [ ] Set up project structure
- [ ] Implement LLM integration (Ollama + Groq as options)
- [ ] Build food input parser (natural language → structured items)
- [ ] Implement web search for nutrition lookup
- [ ] Build nutrition extraction pipeline (search results → structured data)
- [ ] Create SQLite cache layer
- [ ] Build basic Streamlit UI (input + daily log view)
- [ ] Add daily nutrition summary

### Phase 2: Polish & UX (Week 3) ✨

- [ ] Add meal type selection (Breakfast/Lunch/Dinner/Snack)
- [ ] Build history view (past 7/30 days)
- [ ] Add nutrition charts and visualizations
- [ ] Implement daily insights via LLM
- [ ] Add multi-user support (simple name-based)
- [ ] Handle edge cases (unknown foods, ambiguous portions)

### Phase 3: Smart Features (Week 4+) 🧠

- [ ] Auto-suggest based on frequently logged foods
- [ ] Weekly nutrition reports
- [ ] Food correction/editing after logging
- [ ] Export data as CSV
- [ ] Optional: Telegram bot interface for quick logging on the go

---

## 14. How the User Experience Flows

```
┌──────────────────────────────────────────────────────────┐
│  🍛 NutriLog India                        [Devender ▾]  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  What did you eat?                                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 2 paratha with curd and achar, chai with sugar   │   │
│  └──────────────────────────────────────────────────┘   │
│  Meal: [● Breakfast ○ Lunch ○ Dinner ○ Snack]          │
│                                              [Log It 🍽] │
│                                                          │
│  ─── Today's Log (28 Feb 2026) ─────────────────────    │
│                                                          │
│  🌅 Breakfast                                            │
│  ├─ 2x Paratha (aloo)         ── 440 kcal | 8g P       │
│  ├─ 1x Curd (1 katori)        ── 98 kcal  | 4g P       │
│  ├─ 1x Achar (1 tbsp)         ── 15 kcal  | 0g P       │
│  └─ 1x Chai with sugar        ── 90 kcal  | 2g P       │
│                                                          │
│  🌞 Lunch                                               │
│  ├─ 3x Roti                   ── 312 kcal | 9g P       │
│  ├─ 1x Dal fry (1 bowl)       ── 150 kcal | 9g P       │
│  └─ 1x Aloo gobi (1 katori)   ── 180 kcal | 4g P       │
│                                                          │
│  ─── Daily Summary ─────────────────────────────────    │
│                                                          │
│  Calories   ████████████░░░░░░░░  1,285 / 2,200 kcal   │
│  Protein    ████░░░░░░░░░░░░░░░░  36g / 120g            │
│  Carbs      ████████████░░░░░░░░  180g / 300g           │
│  Fat        ██████████░░░░░░░░░░  45g / 70g             │
│  Fiber      ████████░░░░░░░░░░░░  18g / 30g             │
│                                                          │
│  💡 "You've had a good start but protein is low.        │
│      Consider adding paneer, eggs, or a handful of      │
│      roasted chana to your evening snack!"              │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 15. Key Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| **Search-first, no pre-built DB** | Indian food is too diverse for any single database. Web search handles everything — from "maggi" to "machher jhol". The cache builds itself. |
| **LLM as the brain, not just a formatter** | The LLM understands context ("cutting chai" = half cup, "plate momos" = ~8 pieces). Rule-based parsing can't do this. |
| **DuckDuckGo over paid search APIs** | Zero cost, no API key, good enough for nutrition queries. We're not building Google — we just need "roti calories India". |
| **Groq + Ollama dual support** | Groq for friends without beefy machines. Ollama for offline/privacy. User picks. |
| **SQLite over PostgreSQL** | For 5-15 users logging 3-5 meals/day, SQLite handles it effortlessly. No server to manage. |
| **Streamlit over React/Next.js** | Ship fast. Looks good. Python-native. Perfect for an MVP with friends. |
| **No user auth for MVP** | Just a name dropdown. You trust your friends. Add auth later if needed. |

---

## 16. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM returns wrong nutrition values | User tracks inaccurate data | Show confidence level; allow manual correction; cross-reference multiple search results |
| DuckDuckGo blocks/rate-limits us | Search stops working | Fallback to Tavily free tier; aggressive caching reduces search needs |
| Groq free tier gets restricted | Cloud LLM stops working | Ollama as local fallback; app works with either |
| Indian foods not found in search | Incomplete nutrition data | LLM estimates from ingredients; flag as "estimated"; allow manual entry |
| Friends stop using it | Wasted effort | Keep it dead simple; add Telegram bot for frictionless logging |

---

## 17. Future Possibilities (Post-MVP, Still Free)

- **Telegram Bot**: Log food via Telegram message → instant nutrition response
- **Photo Logging**: Use a free vision model (LLaVA via Ollama) to identify food from photos
- **Meal Planning**: "Suggest a 2000 kcal Indian vegetarian meal plan for tomorrow"
- **Recipe Nutrition**: "I made palak paneer with 200g paneer, 1 bunch spinach, 2 tbsp oil — what's the nutrition?"
- **Community Cache**: Share your food cache with friends so everyone benefits from past lookups
- **WhatsApp Integration**: Since everyone in India uses WhatsApp, a WhatsApp bot would be killer

---

## 18. Getting Started (Developer Setup)

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd nutrilog-india

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your Groq API key (free from console.groq.com)

# 5. (Optional) Install Ollama for local LLM
# Visit ollama.com and install, then:
ollama pull llama3.1

# 6. Run the app
streamlit run app.py
```

---

## 19. Summary

**NutriLog India** is a smart, free, India-first nutrition tracker that:

1. **Takes natural language input** — "2 roti dal chaas" is all you need to type
2. **Uses AI to understand Indian food** — knows that "paratha" needs more calories than "roti"
3. **Searches the web when needed** — no food is too obscure
4. **Builds its own database over time** — gets faster and smarter with every use
5. **Costs absolutely nothing** — Ollama/Groq (free) + DuckDuckGo (free) + SQLite (free)
6. **Works for you and your friends** — simple multi-user, no complex auth

The key insight: **You don't need an expensive nutrition database. You need a smart LLM that can search the web and extract nutrition data on the fly, then cache it locally.** That's exactly what we're building.

---

*Built with 🇮🇳 love, ₹0 budget, and open-source everything.*

