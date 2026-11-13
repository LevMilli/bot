"""Plan docs stay true: inventory numbers match the code; plan pages exist and read plainly."""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLANS = os.path.join(HERE, "plans")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inventory():
    with open(os.path.join(HERE, "BUY_SELL_FAILSAFE_INVENTORY.md"), encoding="utf-8") as handle:
        return handle.read()


def test_btc15m_inventory_matches_code():
    sys.path.insert(0, os.path.join(HERE, "btc15m-signal"))
    btc = _load("btc15m_doc_pin", os.path.join(HERE, "btc15m-signal", "btc15m_signal.py"))
    text = _inventory()
    assert btc.MIN_CUSHION_USD == 35 and "**$35** BTC" in text
    assert (btc.ASK_MIN, btc.ASK_MAX) == (0.70, 0.92) and "**[0.70, 0.92]**" in text
    assert btc.MAX_SPREAD == 0.04 and "≤ **0.04**" in text
    assert btc.MIN_DEPTH == 3 and "≥ **3** contracts" in text
    assert btc.MAX_BUYS_PER_CHECK == 3 and "up to **3**" in text
    assert btc.MIN_Z == 0.60 and "≥ **0.60**" in text
    assert "≥ **$40**" not in text and "[0.65, 0.85]" not in text


def test_sports_gap_docs_match_code():
    sys.path.insert(0, os.path.join(HERE, "sports-gap-paper"))
    gap = _load("gap_doc_pin", os.path.join(HERE, "sports-gap-paper", "gap_bot.py"))
    assert gap.PRICE_BOUNDS == (0.05, 0.92)
    assert gap.MAX_BUYS_PER_CHECK == 4
    assert gap.PREGAME_WINDOW_MIN == 180
    text = _inventory()
    assert "**[0.05, 0.92]**" in text and "Up to **4** buys per check" in text and "**3 hours**" in text
    with open(os.path.join(HERE, "sports-gap-paper", "README.md"), encoding="utf-8") as handle:
        readme = handle.read()
    assert "**92¢**" in readme and "**4 buys per check**" in readme and "**3 hours**" in readme
    assert "**6 points or more**" in readme and "between 5¢ and 95¢" not in readme


PAGES = (
    "CHECKLIST_STATUS.md", "PARKED_SHELLS.md", "TOWER_PLAIN_WORDS.md", "HOW_TO_ADD_A_TOWER.md",
    "HOW_TO_READ_THE_CITY.md", "KEEP_IMPROVING.md",
    "new-towers/README.md", "new-towers/A1-maker-quote.md", "new-towers/A2-labor.md",
    "new-towers/A3-rain-today.md", "new-towers/A4-eia-crude.md", "new-towers/A7-hourly-index.md",
    "new-towers/A20-time-machine.md", "new-towers/A23-risk-room.md", "new-towers/A25-rule-match.md",
    "new-towers/A26-freshness.md",
)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def test_plan_pages_exist_and_read_plainly():
    for page in PAGES:
        path = os.path.join(PLANS, page)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        assert text.startswith("# "), page
        low = text.lower()
        assert "scrape" not in low and "crawl" not in low, page
        assert not _EMOJI.search(text), page
        assert "!" not in text.replace("<!--", ""), page


def test_checklist_names_every_tower_section():
    with open(os.path.join(PLANS, "CHECKLIST_STATUS.md"), encoding="utf-8") as handle:
        text = handle.read()
    for head in ("Sports gap (458-469)", "Kalshi S&P (470-481)", "BTC 15m (482-493)", "Commodity 15m (494-505)",
                 "Memecoin (506-517)", "Sized Kalshi (518-529)", "More 15m (530-541)", "Coinbase spot (542-553)",
                 "BTC carry (554-565)", "Sports sharp lag (566-577)", "Fed watch (578-589)",
                 "Exclusive set (590-601)", "Point spread and Game total (602-613)", "Weather high (614-625)",
                 "Gas weekly (626-637)", "Crypto ladder (638-649)", "Nasdaq (650-661)",
                 "Poly sports lean (662-673)", "Favorite harvest (674-685)", "10-year Treasury (686-697)",
                 "CPI and GDP nowcast (698-709)", "Soccer & tennis lean (710-721)", "QQQ momentum (722-733)",
                 "Research and support buildings (734-745)"):
        assert f"## {head}" in text, head


def test_parked_shells_doc_lists_every_paused_shell():
    sys.path.insert(0, HERE)
    import shadow_missing

    with open(os.path.join(PLANS, "PARKED_SHELLS.md"), encoding="utf-8") as handle:
        text = handle.read()
    for tid in shadow_missing.PAUSED:
        assert shadow_missing.BY_ID[tid]["name"] in text, tid
