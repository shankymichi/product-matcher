# How the Product Matcher Works

Nov 13, 2026 · @OnCallEngineers

You paste a link to a product on Amazon, and the app tells you whether Flipkart, Croma or Myntra sells the very same thing, and whether you can buy it there right now.

## The four steps

Every check goes through the same four steps, and the last three happen in every shop at the same time.

&#91;embedded content: the four steps of every check\]

1. **Read the Amazon page.** It notes the brand, the model and the key details, such as a phone's RAM and storage. Together these are the product's fingerprint.
2. **Search each shop.** It searches by name, and tries simpler, then broader, searches if the first finds nothing.
3. **Compare each result.** Brand, model and key details must all agree. One mismatch rules a result out.
4. **Check stock.** It opens the matching product's page and looks for a working Buy button.

The visiting happens in a real Chrome window on your computer, because the shops only show their pages properly to a real browser.

## How it decides two things are the same

Two listings are the same product only when three things all agree: the brand, the model, and the one key detail that matters most for that kind of product.

| Kind of product | Shops it checks | The key detail that must also match |
| --- | --- | --- |
| Smartphones | Flipkart, Croma | Memory (RAM) and storage |
| Televisions | Flipkart, Croma | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos and jerseys | Flipkart, Myntra | Colour |

The key detail separates versions that share a name, such as the 256 GB and 512 GB Galaxy S25 Ultra. Price is ignored, and so is a phone's colour, although Amazon's colour is preferred when several are on offer. Both names are cleaned of filler words such as "Smart" or "For Men" before comparing, so "SAMSUNG Galaxy S25 Ultra 5G (12GB RAM, 256GB)" becomes "galaxy s25 ultra 5g".

## The four answers

For each shop you get one of three answers, plus a fourth for when the app couldn't look properly.

| Answer | What it means | What you see |
| --- | --- | --- |
| In stock | Found the same product, and you can buy it now | A green card with a button to the shop's page |
| Out of stock | Found the same product, but it can't be bought right now | An amber card with a link, so you can check back later |
| Not listed | The shop doesn't sell this product | A grey card, no link |
| Couldn't check | The shop didn't let the app look, or took too long | A red card and a pop-up explaining why |

"Couldn't check" keeps the app honest: if a shop blocks it or is too slow, it says so instead of guessing "not listed". Croma's stock depends on the delivery pincode, so the app uses Croma's default (Mumbai 400049) and notes it on the card.

## Tricky cases it has learned to handle

These all come from products tested while building the app.

- **Look-alike phones:** the Galaxy M08, F08 and A08 LTE share their specs but are different models, so the M08 is correctly "not listed" on Flipkart.
- **Same TV, different names:** Amazon's "BRAVIA 2M2" is Croma's "BRAVIA 2 II". The app matches them on the model number (K-43S22BM2), which also picks the right one of three similarly named Croma listings.
- **Nearly identical model numbers:** K-55S30B and K-55S30 differ only by a colour suffix, so they match, with a note on the card.
- **Weak shop search:** Croma's search for "sony bravia 3" shows no Sony TVs, so the app also tries a broader search ("sony 55 inch tv").
- **Newer generation:** BRAVIA 3 II (2026) is not the same product as BRAVIA 3 (2024).

## The AI helper

An optional **AI check** switch lets an AI model (Gemini or Claude) judge names that are close but not identical, such as "Smashic Comfort Casual Sneakers" on Amazon and "Smashic Sneakers For Men" on Flipkart. With the switch off, such names count as no match.

- **Hard checks first:** it only sees listings that already passed the brand and key-detail checks.
- **Only when needed:** it isn't asked when an exact match already exists.
- **Safe fallback:** if it fails or runs out of quota, the app falls back to strict matching and says so.
- **Labelled:** every match it approves is marked on its card, with its reason.

## Deep technical dive

This section is for developers: how the code is organised, the exact matching algorithm, and where it can be extended.

### Architecture

&#91;embedded content: architecture · 3 layers over 5 plug points\]

Read top to bottom: the page calls `LookupService`, which uses the Amazon reader, one checker per shop, and the matching engine. They reach the shops, the rules and the AI only through the plug points in the bottom band.

| Part | Choice | Why |
| --- | --- | --- |
| Language | Python 3.10+ | Mature browser automation and AI libraries |
| Web layer | FastAPI, server-sent events | Results stream to the page as each shop finishes |
| Browser | Playwright driving the installed Google Chrome, in a visible window | Croma and Myntra reject a hidden (headless) browser |
| Page parsing | selectolax (lexbor), schema.org JSON, embedded page data | Fast, and structured data where the shop offers it |
| Data models | Pydantic | One definition shared by the matcher, the AI check and the API |
| Name similarity | rapidfuzz | Word-order-independent scores for clothing and shoe names |
| AI check (optional) | google-genai or anthropic SDK | Only loaded when a key is set |

### A lookup, end to end

1. **Request.** The page calls `GET /check?url=…&ai=…` and listens for events.
2. **Read the source.** `AmazonReader` accepts only amazon.in product links, reduces them to `/dp/<ASIN>` (dropping tracking parameters), and parses the title, breadcrumb path, spec tables and detail bullets. The model number comes from "Model Number", "Item model number", "Style Number" or "Manufacturer Part Number", in that order.
3. **Pick the category.** `find_rule` maps the *deepest* breadcrumb to a `CategoryRule`. "Shirts" under "T-shirts, Polos & Shirts" is therefore not taken for a T-shirt.
4. **Build the fingerprint.** `Describer` extracts each must-match attribute, cleans the model name, and builds three searches: model plus required fields, model only, then brand plus required fields plus product type.
5. **Check every shop at once.** One `PlatformChecker` per shop runs concurrently. Each result is sent to the page as soon as it's ready.

### The matching algorithm

`MatchEngine.compare` runs these checks in order and stops at the first rejection:

1. **Brand:** normalised and alias-mapped. A search result without a brand field must *start* with the brand, which rejects accessories titled "Case for Samsung Galaxy…". A brand that extends the other ("U.S. Polo Assn. Denim Co.") is accepted.
2. **Must-match fields:** each field named in the rule is compared by its `AttributeSpec`. RAM, storage and screen size are parsed to whole numbers (TB to GB, cm to inches) and compared exactly. Colour is reduced to base colours through a synonym table ("Titanium Silverblue" becomes blue). A field the listing doesn't state is *unclear*, never assumed.
3. **Model number:** identical numbers are an immediate match.
4. **Model name:** televisions and phones use `ExactWordsMatcher` (the same set of words; a short code such as "UE81A" inside the full model number also counts). Shoes and clothing use `NameScoreMatcher`: the same words in any order match, and any difference in number-words (V1 against V2, 574 against 530) is a rejection.
5. **Notes:** a match whose model numbers differ gets a note. If they differ only by a suffix of up to two letters, the note says so.

Before comparing, model names are cleaned: brackets and anything after a comma, a "|" or "with" are dropped, along with spec tokens (GB, mAh, inch), energy ratings ("2 Star"), the brand, filler words, the category's stop words, colour words and the model number's own tokens. "Sony 108 cm (43 inches) Smartchoice BRAVIA 2M2 Series 4K Ultra HD Smart LED Google TV K-43S22BM2" becomes "bravia 2m2".

`PlatformChecker` wraps the engine with the steps that need the network:

- Up to 40 search results are compared. Reading a search result is free; opening a product page costs seconds.
- When a must-match field is missing from a search result, the product page is opened, at most 5 per shop.
- When the source has a model number and nothing matched by name, candidates that passed brand and fields have their product pages read for their model numbers, best name score first.
- With the AI check on, unclear candidates and near misses (rejected only on name, with a score of 40 or more) go to the AI in one call of at most 8 candidates.
- The first search that produces a match ends the search.
- Matches are ranked: identical model number, then a suffix-only difference, then preferred fields (for phones, the same colour), then the shop's own order.
- Stock is read from up to 3 matched product pages. An in-stock one wins over an out-of-stock one.

### Stock and status rules

| Shop | How stock is read |
| --- | --- |
| Flipkart | schema.org `offers.availability` on the product page; otherwise the Buy Now button against "Currently unavailable" or "Notify me" |
| Croma | An unavailability notice always wins, because Croma keeps its Buy buttons even when it can't deliver to the default pincode |
| Myntra | The page's embedded data: not flagged out of stock, and at least one size available |

"Not listed" is returned only when every search succeeded and nothing matched. A blocked search, a timeout, or an unread candidate page that leaves no match all become "Couldn't check", because "not listed" would then be a guess.

### Fetching, blocking and caching

- **Browser:** pages load in the installed Chrome with an Indian locale, a 20-second timeout, one retry, and at most 4 pages at a time.
- **Blocks:** HTTP 403, 429 and 503, and known check pages ("continue shopping", "access denied", CAPTCHA wording) raise `FetchBlocked`. They are reported, never bypassed.
- **Cache:** off by default, so every lookup reads the shops afresh. When enabled with `CACHE_MINUTES`, a page whose expected content never appeared is never cached, so a slow, half-loaded page can't keep returning "not listed".
- **Cloud hosting:** a fetch test from a cloud server on 12 Nov 2026 loaded only Flipkart; Amazon, Croma and Myntra blocked it or didn't respond. That's why the app runs on a home computer and is shared through a tunnel.

### The AI check

`LlmTieBreaker` holds the shared prompt and rules, and a small backend per provider: Gemini with a JSON response schema, or Claude with a forced tool call. The prompt includes the reference product, the candidates, and which fields code already verified. Each verdict is `same`, `different` or `unsure`, and only `same` counts. Definite answers are cached for the session; a skipped answer is asked again next time. Any failure falls back to strict matching with a note. The provider is chosen from whichever key is in `.env`, Gemini first; the defaults are `gemini-3.5-flash` and `claude-haiku-5-5`.

### Extending it

Each kind of change touches one class or one config row.

| Change | What to add or edit |
| --- | --- |
| Match phones on colour too | Add `"colour"` to the smartphone row's `must_match` in `app/categories.py` |
| New category, such as laptops | One `CategoryRule` row |
| New match field, such as processor | One `AttributeSpec` class, then name it in a rule |
| New shop, such as Reliance Digital | One adapter in `app/platforms/` with `@register_platform`, then name it in the rules |
| New AI provider | One backend class in `app/tiebreak/llm.py` |
| Different way of fetching pages | One `PageFetcher`, chosen in `app/container.py` |

`container.py` is the only file that names concrete classes. Everything else depends on interfaces, which is what keeps these changes local.

### Testing

The 99 automated tests need no network: `FakeFetcher` serves pages saved from the four shops, including trimmed copies of the Sony TV pages that exposed the naming and search problems. They cover the parsers, every matching rule, the look-alike phones, the TV cases, the AI check with stand-in providers, the cache rules and the web endpoint. Run them with `python -m pytest -q`.

### Known limits

- **Needs your computer:** it runs on a home computer with Chrome, since the shops block cloud servers.
- **Croma stock is pincode-based:** it reflects Croma's default pincode, not the user's.
- **Clothing is the weakest category:** shop titles are generic ("Men Solid Polo Neck T-Shirt"), and neither Flipkart nor Myntra shows the maker's style code in search results.
- **Layout changes:** a shop changing its page layout can break that shop's parser until it's updated.
- **Speed:** a lookup takes roughly 5 to 20 seconds per shop, more when model numbers have to be read from product pages.
- **Not measured yet:** accuracy hasn't been measured on a labelled set of links, so the figures here describe behaviour, not error rates.
