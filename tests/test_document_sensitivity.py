"""P9-G: Document sensitivity keyword detection tests."""
import pytest

from kyc_engine.document_sensitivity import (
    SensitivityFlag,
    detect_sensitivity,
    should_block,
    requires_review,
    sensitivity_summary,
)


class TestDocumentSensitivity:
    """P9-G sensitivity keyword detection tests."""

    def test_ds_001_clean_text_no_flags(self):
        """DS-001: Clean document text produces no flags."""
        text = "John A. Miller, 122 West 49th St, New York, NY 10020. Account active."
        flags = detect_sensitivity(text)
        assert len(flags) == 0

    def test_ds_002_confidential_detected(self):
        """DS-002: CONFIDENTIAL keyword triggers review flag."""
        text = "CREDIT REPORT\nCONFIDENTIAL DOCUMENT\nName: John Miller"
        flags = detect_sensitivity(text)
        cats = [f.category for f in flags]
        assert "CONFIDENTIAL" in cats
        conf_flag = next(f for f in flags if f.category == "CONFIDENTIAL")
        assert conf_flag.severity == "review"

    def test_ds_003_sample_blocks(self):
        """DS-003: SAMPLE keyword triggers block-severity flag."""
        text = "THIS IS A SAMPLE DOCUMENT FOR TESTING PURPOSES"
        flags = detect_sensitivity(text)
        cats = [f.category for f in flags]
        assert "SAMPLE" in cats
        assert should_block(flags) is True

    def test_ds_004_specimen_blocks(self):
        """DS-004: SPECIMEN keyword triggers block-severity flag."""
        text = "SPECIMEN — Not valid for official use"
        flags = detect_sensitivity(text)
        assert should_block(flags) is True

    def test_ds_005_draft_detected(self):
        """DS-005: DRAFT keyword triggers review flag."""
        text = "DRAFT — Internal Review Only\nAccount Summary"
        flags = detect_sensitivity(text)
        cats = [f.category for f in flags]
        assert "DRAFT" in cats

    def test_ds_006_redacted_xxx_pattern(self):
        """DS-006: XXX-XX-8124 masked SSN triggers REDACTED flag."""
        text = "SSN: XXX-XX-8124\nName: John Miller"
        flags = detect_sensitivity(text)
        cats = [f.category for f in flags]
        assert "REDACTED" in cats
        assert requires_review(flags) is True

    def test_ds_007_multiple_categories(self):
        """DS-007: Document with multiple sensitivity markers flags all categories."""
        text = "CONFIDENTIAL DOCUMENT\nSSN: XXX-XX-1234\nDRAFT VERSION"
        flags = detect_sensitivity(text)
        cats = {f.category for f in flags}
        assert "CONFIDENTIAL" in cats
        assert "REDACTED" in cats
        assert "DRAFT" in cats

    def test_ds_008_dedup_per_category(self):
        """DS-008: Multiple matches within same category produce only one flag."""
        text = "CONFIDENTIAL\nThis is confidential and restricted information"
        flags = detect_sensitivity(text)
        conf_flags = [f for f in flags if f.category == "CONFIDENTIAL"]
        assert len(conf_flags) == 1

    def test_ds_009_empty_text_no_flags(self):
        """DS-009: Empty or whitespace text produces no flags."""
        assert detect_sensitivity("") == []
        assert detect_sensitivity("   ") == []
        assert detect_sensitivity(None) == []

    def test_ds_010_summary_structure(self):
        """DS-010: sensitivity_summary returns expected dict structure."""
        flags = detect_sensitivity("CONFIDENTIAL DOCUMENT with XXX-XX data")
        s = sensitivity_summary(flags)
        assert "flag_count" in s
        assert "categories" in s
        assert "blocked" in s
        assert "requires_review" in s
        assert "flags" in s
        assert s["requires_review"] is True

    def test_ds_011_block_sorting(self):
        """DS-011: Flags are sorted by severity — block before review before info."""
        text = "CONFIDENTIAL SAMPLE DOCUMENT, COPY attached"
        flags = detect_sensitivity(text)
        severities = [f.severity for f in flags]
        order = {"block": 0, "review": 1, "info": 2}
        numeric = [order[s] for s in severities]
        assert numeric == sorted(numeric)

    def test_ds_012_extra_keywords(self):
        """DS-012: Custom extra keywords are detected alongside built-in ones."""
        extra = [{"pattern": r"\bFRAUDULENT\b", "category": "FRAUD",
                  "severity": "block", "message": "Fraud indicator detected."}]
        text = "This document appears FRAUDULENT"
        flags = detect_sensitivity(text, extra_keywords=extra)
        cats = [f.category for f in flags]
        assert "FRAUD" in cats
        assert should_block(flags) is True

    def test_ds_013_garbled_bank_statement(self):
        """DS-013: Real garbled bank statement text — triggers no false SAMPLE/DRAFT."""
        text = "BBaannkk SSttaatteemmeenntt XXXXXXXX-XXXXXXXX-1294"
        flags = detect_sensitivity(text)
        cats = {f.category for f in flags}
        # Should detect REDACTED (XXX pattern) but NOT falsely flag as SAMPLE/DRAFT
        assert "REDACTED" in cats
        assert "SAMPLE" not in cats
        assert "DRAFT" not in cats

    def test_ds_014_utility_bill_watermark(self):
        """DS-014: Utility bill with scattered single chars — no false positives."""
        text = "A\nL\nS\nP\nM\nConEdison\nUTILITY BILL\nAccount Number: 9845-2103"
        flags = detect_sensitivity(text)
        # Should NOT trigger SAMPLE, CONFIDENTIAL, or DRAFT
        blocked_cats = {"SAMPLE", "CONFIDENTIAL", "DRAFT"}
        flagged_cats = {f.category for f in flags}
        assert not (blocked_cats & flagged_cats)
