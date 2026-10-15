# Commercial real-estate alerts: Haifa & Krayot

This agent checks Israeli real-estate sites twice a day and sends you **new** commercial listings for rent.
It looks for:

| | |
|---|---|
| **Deal** | rent (sale ads are dropped automatically), no price limit |
| **Size** | 150–250 m². Listings within 10% of the range (135–275 m²) are also sent, marked "≈ close to range" |
| **Types** | shops (חנויות), warehouses (מחסנים), commercial/industrial buildings (מבנים, מבני תעשייה), halls (אולמות). No offices |
| **Area** | Haifa (including Kiryat Haim, Kiryat Shmuel and the Haifa Bay area), Kiryat Bialik, Kiryat Motzkin, Kiryat Ata, Kiryat Yam, Nesher, Tirat Carmel |
| **Sites** | Yad2 (יד2) and Madlan (מדלן). Templates for Komo, Homeless or any other site are included. Facebook is deliberately not used |
| **Alerts** | Email and WhatsApp (Telegram also supported). Plus an HTML report with every current match |

Each listing is sent once. If a listing you already got **drops in price**, you get a 📉 alert.
When the same property is posted on Yad2 and on Madlan, you get it once, with both links.

```
מחסן · 220 מ"ר · ₪12,000 לחודש
החרושת 3, אזור תעשייה, קרית ביאליק · קומה 0
₪55 למ"ר · פרטי · יד2
https://www.yad2.co.il/realestate/item/...
```

---

## Where it runs

Yad2 and Madlan block most cloud servers with anti-bot checks. So the agent runs on **your Windows computer**:
it opens the pages in a real Chrome browser on your home internet, the same way you do.
The computer needs to be on at 08:00 and 18:00 (if it's off, that scan is simply skipped).

---

## Setup on Windows (about 15 minutes)

### 1. Install

1. Install [Python](https://www.python.org/downloads/). In the first installer screen, tick **"Add python.exe to PATH"**.
2. Download the project: [this ZIP](https://github.com/DavidRambam/kidscity/archive/refs/heads/claude/israel-realestate-alerts-2b6h7p.zip) (sign in to GitHub first). Extract it, for example to `Documents`, and open the `realestate-alerts` folder inside.
3. Double-click **`scripts\setup.bat`**. It installs everything, then asks where to send the alerts (next step).

### 2. Email and WhatsApp

The setup asks for:

- **Your Gmail address** and a **Gmail app password**. This is a special 16-letter password just for this agent, not your normal password.
  Create it at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). If that page says it isn't available, first turn on [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification).
- **WhatsApp**, through [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/), a free service that sends WhatsApp messages to your own number:
  1. On that page, find CallMeBot's phone number and save it in your phone's contacts.
  2. Send it this WhatsApp message: `I allow callmebot to send me messages`
  3. It replies with your **API key**. Type it into the setup together with your number (e.g. `050-1234567`).

At the end it offers to send a test message to both. To change these details later, double-click `scripts\setup.bat` again.

### 3. First scan

Double-click **`scripts\first_scan.bat`**. A browser window opens and visits each search page.
If a site asks you to confirm you're human (for example "press and hold"), do it once in that window. It's remembered for later runs.

The first scan sends **everything that matches right now**. After that you only get new listings and price drops.
When it finishes, `reports\latest.html` opens with the full list. You can open it again anytime.

### 4. Run it twice a day automatically

Double-click **`scripts\schedule_windows.bat`**. It adds two Windows Task Scheduler jobs, at 08:00 and 18:00.
To use other times, edit the times in that file and run it again.

(On a Mac: `scripts/setup.sh`, `scripts/run.sh --headed`, then `scripts/schedule_mac_linux.sh`.)

---

## Cloud setup (GitHub Actions)

Optional, and less reliable than your computer (see above). The workflow is in `.github/workflows/realestate-alerts.yml`. It runs at 08:00 and 18:00 Israel time and has a manual **Run workflow** button.

1. Merge it into the repository's default branch (`main`). GitHub only runs scheduled workflows from there.
2. In the repository, go to **Settings → Secrets and variables → Actions** and add the same names you use in `.env` (`SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`, `WHATSAPP_PHONE`, `CALLMEBOT_APIKEY`).
3. In the **Actions** tab, open "Real-estate alerts" and click **Run workflow** to test it.

The list of sent listings is kept in the Actions cache. Each run also saves `latest.html` as a downloadable artifact.
If you get "⚠️ blocked by an anti-bot check" for a site every time, that site is blocking GitHub's servers. Run it on your computer instead.

---

## Changing what it searches for

Everything is in **`config.yaml`** (open it with Notepad). Every setting has a comment:

- `min_sqm` / `max_sqm` / `size_tolerance_pct`: the size range
- `max_price`: a monthly rent ceiling (now: no limit)
- `property_types`: add `office` to also get offices
- `cities`: the towns to keep
- `exclude_keywords`: skip ads containing these words

**Using your own filters from Yad2 / Madlan:** open the site in Chrome, set the filters you want (area, size, type, "השכרה"),
and copy the address from the browser bar into the `urls:` list of that site, one line per search. The agent still applies its own filters on top.

**Adding another site** (Komo, Homeless, a broker's site…): set `enabled: true` on its entry under `sources:`, paste the search-results URL into `urls:`, and check that `link_pattern` matches the links of single listings on that site. The part in parentheses is the listing id.

---

## Facebook

Facebook groups are deliberately not searched.

---

## Troubleshooting

| Message | What to do |
|---|---|
| `⚠️ <site>: blocked by an anti-bot check` | Run once with `--headed` and complete the check. If it keeps happening on GitHub Actions, run on your computer |
| `⚠️ <site>: no listings found - the site may have changed` | Run `scripts\run.bat --headed --debug --only yad2`. Each page's HTML and a screenshot are saved in `debug/`. Send them over and the parser can be adjusted |
| Nothing arrives, no error | Run `scripts\run.bat test-notify`. Also check `logs\alerts.log`. Look in Gmail's spam folder once and mark it "not spam" |
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
