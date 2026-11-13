# Same product, other shops

Paste an Amazon.in product link. The site reports, for each other platform, whether
the same product is **in stock**, **out of stock** or **not listed**. If a platform
could not be checked, it says so in a pop-up instead of guessing.

| Category | Searched on | Must match (besides brand and model) |
| --- | --- | --- |
| Smartphones | Flipkart, Croma | RAM and storage |
| Televisions | Flipkart, Croma | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos and jerseys | Flipkart, Myntra | Colour |

## Requirements

- Python 3.10 or newer
- Google Chrome installed (Croma and Myntra reject a headless browser, so lookups
  run in a visible Chrome window)

## Setup

    pip install -r requirements.txt

## Turn on the AI check (optional)

Without it, a product name must match word for word. With it on, names that are
close but not identical (for example "Smashic Sneakers For Men" against "Smashic
Comfort Casual Sneakers") are also shown to an AI model (Gemini or Claude), which decides whether
they are the same product. Brand and the required fields (RAM and storage, screen
size, colour) must still match exactly; the AI only judges the name.

1. Copy `.env.example` to `.env` in the project folder.
2. Add one key:
   - `GEMINI_API_KEY=` for Google Gemini, which has a free tier
     (key from https://aistudio.google.com/apikey), or
   - `ANTHROPIC_API_KEY=` for Claude (paid, key from https://console.anthropic.com).
3. Restart the app. The "AI check" switch on the page becomes available and
   names the provider in use.

On Gemini's free tier, Google may use what is sent to improve its products. The
app sends only product titles and listing details, never anything about you.

The switch is per lookup and is remembered in your browser. Each lookup with it on
makes at most one AI call per platform, and none when the code already found an
exact match. If the AI call fails, the lookup still completes with basic matching
and the card says so.

## Run the website

    python run.py

Then open http://127.0.0.1:8000 and paste an Amazon.in product link.
A Chrome window opens while a lookup runs.

## Run one lookup in the terminal

    python -m app.cli "https://www.amazon.in/dp/B0DSKNQW8F"
    python -m app.cli --ai "https://www.amazon.in/dp/B0DSKNQW8F"     # with the AI check

## Run the tests

    python -m pytest -q

The tests use pages saved in `tests/fixtures`, so they need no network.

## Settings (all optional environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `HEADLESS` | `false` | `true` works for Amazon and Flipkart only |
| `BROWSER_CHANNEL` | `chrome` | Uses the installed Google Chrome |
| `FETCH_TIMEOUT_S` | `20` | Seconds allowed per page |
| `CACHE_MINUTES` | `0` | Minutes to reuse fetched pages; `0` re-reads the shops on every lookup |
| `PORT` | `8000` | Port for `run.py` |
| `GEMINI_API_KEY` | unset | Enables the AI check with Gemini |
| `ANTHROPIC_API_KEY` | unset | Enables the AI check with Claude |
| `AI_PROVIDER` | automatic | `gemini` or `anthropic`, when both keys are set |
| `AI_MODEL` | `gemini-3.5-flash` or `claude-haiku-5-5` | Model used by the AI check |

These can also go in the `.env` file. No API key is needed for basic matching.

## How to extend

| Change | What to edit |
| --- | --- |
| Match phones on colour too | Add `"colour"` to the smartphone row's `must_match` in `app/categories.py` |
| New category | Add a `CategoryRule` row in `app/categories.py` |
| New match field | Add a class in `app/attributes/`, register it, name it in a rule |
| New platform | Add an adapter in `app/platforms/` with `@register_platform`, import it in `app/platforms/__init__.py`, name it in a rule |
| Different page fetching | Add a `PageFetcher` and choose it in `app/container.py` |

## Layout

    app/
      main.py          web page and /check endpoint
      cli.py           one lookup from the terminal
      container.py     builds and wires every object
      service.py       LookupService and PlatformChecker
      categories.py    CATEGORY_RULES
      models.py  errors.py  config.py
      fetch/           Playwright, cached and fake fetchers; block detection
      sources/         Amazon reader
      platforms/       Flipkart, Croma, Myntra adapters
      attributes/      RAM, storage, screen size, colour
      matching/        engine, describer, model matchers, text clean-up
      tiebreak/        basic (no AI) and the AI check
      static/index.html
    scripts/fetch_test.py
    tests/
