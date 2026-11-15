"""Test number helper for the live test=1 tests.

FILE:      kwtsms_sms/tests/kwtsms_test_number.py
CREATED:   2026-11-05 11:31 +03
TASK:      int-testnumber
AUTHOR:    M Alhassoun
WHAT:      Reads the test number from the KWTSMS_TEST_NUMBER environment variable and
           builds its Arabic-Indic and Persian digit variants at runtime.
WHY:       Live tests used a hard-coded sample Kuwait mobile number, and sample
           numbers belong to real people. Live sends now go only to the approved
           test number; the value is never logged or written to a file.
USAGE:     from .kwtsms_test_number import get_test_number, to_arabic_indic
           TEST_PHONE = get_test_number()   # '' when unset or malformed: skip
DEPENDS:   Python stdlib only (os, re).
"""

import os
import re

_ARABIC_INDIC = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')
_PERSIAN = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def get_test_number():
    """Return KWTSMS_TEST_NUMBER if it is a Kuwait mobile (965XXXXXXXX), else ''."""
    number = os.environ.get('KWTSMS_TEST_NUMBER', '')
    return number if re.fullmatch(r'965[4569]\d{7}', number) else ''


def to_arabic_indic(text):
    """Convert Latin digits in text to Arabic-Indic digits (U+0660-U+0669)."""
    return text.translate(_ARABIC_INDIC)


def to_persian(text):
    """Convert Latin digits in text to Extended Arabic-Indic digits (U+06F0-U+06F9)."""
    return text.translate(_PERSIAN)
