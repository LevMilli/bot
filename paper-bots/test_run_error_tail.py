"""A failed run shows the real error, not the first line of the traceback."""
import pimp_desk as d

TB = """Traceback (most recent call last):
  File "/app/paper-bots/coinbase-spot-paper/bot.py", line 1249, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "/app/paper-bots/coinbase-spot-paper/bot.py", line 900, in fetch_closes
    raise urllib.error.URLError("timed out")
urllib.error.URLError: <urlopen error timed out>
"""


def test_tail_is_the_real_error():
    assert d.traceback_tail(TB) == "urllib.error.URLError: <urlopen error timed out>"
    assert d.traceback_tail("SIGNAL: SKIP ETH-USD") == ""
    assert d.traceback_tail(TB.replace("urllib.error.URLError", "KeyError")).startswith("KeyError:")


def test_card_is_plain():
    text = d.card_copy(TB)
    assert "Traceback" not in text and "URLError" in text and "tries again" in text
    assert d.card_copy("CARD: z 0.10 < 2") == "z 0.10 < 2"
