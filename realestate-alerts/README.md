# Commercial real-estate alerts: Haifa & Krayot

This agent checks Israeli real-estate sites twice a day and sends you **new** commercial listings for rent.
By default it looks for:

| | |
|---|---|
| **Deal** | rent (sale ads are dropped automatically) |
| **Size** | 200–300 m². Listings within 10% of the range (180–330 m²) are also sent, marked "≈ close to range" |
| **Types** | shops (חנויות), warehouses (מחסנים), commercial/industrial buildings (מבנים, מבני תעשייה), halls, offices (משרדים) |
| **Area** | Haifa (including Kiryat Haim, Kiryat Shmuel and the Haifa Bay area), Kiryat Bialik, Kiryat Motzkin, Kiryat Ata, Kiryat Yam |
| **Sites** | Yad2 (יד2) and Madlan (מדלן). Templates for Komo, Homeless or any other site are included |
| **Alerts** | Telegram, email and/or WhatsApp. Plus an HTML report with every current match |

Each listing is sent once. If a listing you already got **drops in price**, you get a 📉 alert.
When the same property is posted on Yad2 and on Madlan, you get one message with both links.

```
🆕 נכס חדש
חנות · 250 מ"ר · ₪18,000 לחודש
📍 הרצל 12, הדר הכרמל, חיפה · קומה 0
💰 ₪72 למ"ר · תיווך · יד2
🔗 לצפייה במודעה
↪️ פורסם גם כאן
```

---

## Where to run it

Yad2 and Madlan use anti-bot protection (Radware, PerimeterX) that blocks most cloud servers.
To get past it, the agent opens the pages in a real Chrome browser, the same way you do.

| Option | Reliability | Cost | Notes |
|---|---|---|---|
| **Your own computer** (recommended) | High: a home connection in Israel looks like a normal visitor | Free | The computer has to be on at 08:00 and 18:00 |
| **GitHub Actions** (cloud) | Uncertain: Yad2/Madlan may block GitHub's servers | Free | Always on. Every scan tells you if a site was blocked |

You can run both. Each one keeps its own list of listings it already sent.

---

## Setup on your computer (about 15 minutes)

### 1. Install

**Windows:** install [Python 3.10+](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** in the installer.
Download this folder, then double-click `scripts\setup.bat`.

**Mac:** open Terminal in this folder and run `scripts/setup.sh`.

### 2. Pick how you want to get alerts

Copy `.env.example` to `.env` (the setup script does this for you), open it in Notepad or TextEdit, and fill in at least one channel:

- **Telegram (recommended).** Each property arrives as its own message with a photo preview, easy to forward.
  1. In Telegram, open **@BotFather**, send `/newbot`, and follow the steps. Paste the token into `TELEGRAM_BOT_TOKEN`.
  2. Send any message to your new bot. Then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy the number after `"chat":{"id":` into `TELEGRAM_CHAT_ID`.
  3. To alert several people, put several chat ids separated by commas, or add the bot to a group and use the group's id.
- **Email.** For Gmail, create an [App password](https://myaccount.google.com/apppasswords) and fill in `SMTP_USER` (your Gmail address) and `SMTP_PASSWORD`. `EMAIL_TO` is optional; it defaults to yourself.
- **WhatsApp.** Uses [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/), a free third-party service that messages your own number. Fill in `WHATSAPP_PHONE` and `CALLMEBOT_APIKEY`.

Check that it works:

```
scripts\run.bat test-notify        (Windows)
scripts/run.sh test-notify         (Mac)
```

### 3. First scan (with the browser visible)

```
scripts\run.bat --headed
```

A browser window opens and visits each search page. If a site asks you to confirm you're human (for example "press and hold"), do it once.
The browser profile in `.browser-profile/` remembers it for later runs.

The first scan sends **everything that matches right now** (as one compact list when there are more than 10). After that you only get new listings and price drops.
You can open `reports/latest.html` anytime to see all current matches.

### 4. Run it twice a day automatically

- **Windows:** double-click `scripts\schedule_windows.bat`. This creates Task Scheduler jobs for 08:00 and 18:00.
- **Mac:** run `scripts/schedule_mac_linux.sh`. This adds a cron job for 08:00 and 18:00.

To use other times, edit the times in that script and run it again.

---

## Cloud setup (GitHub Actions)

The workflow is in `.github/workflows/realestate-alerts.yml`. It runs at 08:00 and 18:00 Israel time and has a manual **Run workflow** button.

1. Merge it into the repository's default branch (`main`). GitHub only runs scheduled workflows from there.
2. In the repository, go to **Settings → Secrets and variables → Actions** and add the same names you use in `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, …).
3. In the **Actions** tab, open "Real-estate alerts" and click **Run workflow** to test it.

The list of sent listings is kept in the Actions cache. Each run also saves `latest.html` as a downloadable artifact.
If you get "⚠️ blocked by an anti-bot check" for a site every time, that site is blocking GitHub's servers. Run it on your computer instead.

---

## Changing what it searches for

Everything is in **`config.yaml`**, which has a comment on every setting:

- `min_sqm` / `max_sqm` / `size_tolerance_pct`: the size range
- `max_price`: a monthly rent ceiling (default: no limit)
- `property_types`: remove `office` if you don't want offices
- `cities`: add Nesher or Tirat Carmel by removing the `#` in front of them
- `exclude_keywords`: skip ads containing these words

**Tuning the search pages:** the most reliable way is to open Yad2 or Madlan in your browser, set the filters you want (area, size, "השכרה"), and paste the address from the browser bar into the `urls:` list of that site. The agent applies its own filters on top, so a wider page is fine.

**Adding another site** (Komo, Homeless, a broker's site…): set `enabled: true` on its entry under `sources:`, paste the search-results URL into `urls:`, and check that `link_pattern` matches the links of single listings on that site. The part in parentheses is the listing id.

---

## Facebook groups

Facebook groups are not included. Reading them automatically means logging in with your personal account, which breaks Facebook's terms and can get the account restricted.
Two free alternatives:

- In each group, click **⋯ → Notifications → All posts**. Facebook then notifies you of every new post.
- Most brokers who post in Haifa groups also list on Yad2, which the agent already covers.

If you still want it automated (at your own risk), it can be added as another source later.

---

## Troubleshooting

| Message | What to do |
|---|---|
| `⚠️ <site>: blocked by an anti-bot check` | Run once with `--headed` and complete the check. If it keeps happening on GitHub Actions, run on your computer |
| `⚠️ <site>: no listings found - the site may have changed` | Run `scripts\run.bat --headed --debug --only yad2`. Each page's HTML and a screenshot are saved in `debug/`. Send them over and the parser can be adjusted |
| Nothing arrives, no error | Run `test-notify`. Also check `logs/alerts.log` |
| Too many / irrelevant listings | Tighten `config.yaml` (types, `max_price`, `exclude_keywords`, `size_tolerance_pct: 0`) |
| I want to get everything again | Delete `state/seen.json` |

Useful options: `--dry-run` (scan and write the report, but send and remember nothing), `--only yad2,madlan`, `--headed`, `--debug`, `-v`.

---

## For developers

```
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest
```

How it works: `alerts/browser.py` loads each page in Chromium with a persistent profile. `alerts/extract.py` reads the page's embedded JSON (Yad2 `__NEXT_DATA__`, Madlan's SSR state, captured API responses) and falls back to the visible listing cards, parsed with `alerts/hebrew.py`. `alerts/filters.py` applies the search. `alerts/state.py` remembers what was already sent. `alerts/notify.py` delivers.
The tests include a real-browser run against the fixture pages in `tests/fixtures/`.
