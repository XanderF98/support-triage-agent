import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deid import redact, restore


def test_round_trip_restores_original_text():
    text = "Hi, this is Dana Whitfield, dana@example.com, member TW-482913."
    redacted, mapping = redact(text, known_names=["Dana Whitfield"])
    assert "Dana" not in redacted
    assert "dana@example.com" not in redacted
    assert "TW-482913" not in redacted
    assert restore(redacted, mapping) == text


def test_same_value_gets_same_placeholder():
    redacted, _ = redact("Email a@example.com, again a@example.com, then b@example.com.")
    assert redacted == "Email [EMAIL_1], again [EMAIL_1], then [EMAIL_2]."


def test_card_number_needs_a_valid_checksum():
    valid, _ = redact("Card 4111 1111 1111 1111 on file.")
    invalid, _ = redact("Invoice 4539 1488 0343 6468 attached.")
    assert "[CARD_1]" in valid
    assert "CARD" not in invalid


def test_text_without_personal_details_is_unchanged():
    text = "Does the plan cover exotic pets? I have a bearded dragon."
    redacted, mapping = redact(text)
    assert redacted == text
    assert mapping.values == {}


def test_restore_leaves_unknown_placeholders_alone():
    _, mapping = redact("Call 206-555-0142.")
    assert restore("Reached [PHONE_1], not [PHONE_9].", mapping) == "Reached 206-555-0142, not [PHONE_9]."


def test_name_introduction_matches_at_start_of_sentence():
    redacted, _ = redact("My daughter Layla wants to be added. Also my son Theo.")
    assert "Layla" not in redacted
    assert "Theo" not in redacted
