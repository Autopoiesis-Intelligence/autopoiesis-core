# Agent: Claude
"""Mechanical checks of docs/theory: links, IDs, statuses and source fields. Not a check of content."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEORY = ROOT / "docs" / "theory"
FILES = ("INDEX.md", "FOUNDATIONS.md", "SOURCES.md", "CLAIMS.md", "THEORY_TO_CODE.md", "OPEN_QUESTIONS.md")
ID_HOME = {"CON": "FOUNDATIONS.md", "SRC": "SOURCES.md", "CLM": "CLAIMS.md", "T2C": "THEORY_TO_CODE.md", "OQ": "OPEN_QUESTIONS.md"}
STATUSES = {"OBSERVED", "SUPPORTED", "ACCEPTED", "HYPOTHESIZED", "UNRESOLVED", "REJECTED", "SUPERSEDED"}
KINDS = {"scientific", "design", "engineering"}

ID_PATTERN = re.compile(r"\b(CON|SRC|CLM|T2C|OQ)-(\d{3})\b")
HEADING = re.compile(r"^### ((?:CON|SRC|CLM|T2C|OQ)-\d{3}) — \S", re.MULTILINE)
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
TEST_REF = re.compile(r"`(tests/[\w/]+\.py)::(\w+)`")


def read(name):
    return (THEORY / name).read_text(encoding="utf-8")


def entries(name):
    """Map each entry ID in a file to the text of its section."""
    text = read(name)
    parts = HEADING.split(text)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def field(section, name):
    match = re.search(rf"^- {name}: (.+)$", section, re.MULTILINE)
    return match.group(1).strip() if match else None


class TheoryDocsTest(unittest.TestCase):
    def test_all_files_exist(self):
        for name in FILES:
            self.assertTrue((THEORY / name).is_file(), name)

    def test_relative_links_resolve(self):
        for name in FILES:
            for target in LINK.findall(read(name)):
                if "://" in target:
                    continue
                self.assertTrue((THEORY / target).resolve().exists(), f"{name}: broken link {target}")

    def test_ids_are_defined_once_in_their_own_file(self):
        seen = {}
        for name in FILES:
            for entry_id in HEADING.findall(read(name)):
                self.assertEqual(ID_HOME[entry_id.split("-")[0]], name, f"{entry_id} defined in {name}")
                self.assertNotIn(entry_id, seen, f"{entry_id} defined twice")
                seen[entry_id] = name

    def test_every_referenced_id_is_defined(self):
        defined = {entry_id for name in FILES for entry_id in HEADING.findall(read(name))}
        for name in FILES:
            for prefix, number in ID_PATTERN.findall(read(name)):
                self.assertIn(f"{prefix}-{number}", defined, f"{name} references undefined {prefix}-{number}")

    def test_claims_use_the_status_and_kind_vocabulary(self):
        claims = entries("CLAIMS.md")
        self.assertTrue(claims)
        for claim_id, section in claims.items():
            self.assertIn(field(section, "Status"), STATUSES, claim_id)
            self.assertIn(field(section, "Kind"), KINDS, claim_id)
            self.assertTrue(field(section, "Grounds"), f"{claim_id} has no grounds")
            self.assertTrue(field(section, "How to check"), f"{claim_id} has no check")
            if field(section, "Kind") == "design":
                self.assertTrue(field(section, "Alternatives"), f"{claim_id} has no alternatives")
                self.assertTrue(field(section, "Risks"), f"{claim_id} has no risks")
            if field(section, "Status") == "SUPERSEDED":
                self.assertRegex(field(section, "Superseded by") or "", r"CLM-\d{3}", claim_id)
            if field(section, "Status") == "REJECTED":
                self.assertTrue(field(section, "Reason"), f"{claim_id} has no reason")

    def test_open_questions_use_the_status_vocabulary(self):
        for question_id, section in entries("OPEN_QUESTIONS.md").items():
            self.assertIn(field(section, "Status"), STATUSES, question_id)

    def test_sources_name_a_url_and_their_check_status(self):
        sources = entries("SOURCES.md")
        self.assertTrue(sources)
        for source_id, section in sources.items():
            self.assertRegex(field(section, "URL") or "", r"^https://\S+$", source_id)
            self.assertTrue(field(section, "Checked"), f"{source_id} does not say whether it was checked")

    def test_referenced_tests_exist(self):
        for name in FILES:
            for path, test_name in TEST_REF.findall(read(name)):
                source = ROOT / path
                self.assertTrue(source.is_file(), f"{name}: missing {path}")
                self.assertIn(f"def {test_name}(", source.read_text(encoding="utf-8"), f"{name}: missing {path}::{test_name}")


if __name__ == "__main__":
    unittest.main()
