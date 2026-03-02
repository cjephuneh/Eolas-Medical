#!/usr/bin/env python3
"""
Test Azure OpenAI (or OpenAI) for classify + suggest_reply. Run from repo root or speed-to-response:
  cd speed-to-response && .venv/bin/python scripts/test_azure_llm.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent so config and modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classify import classify
from llm_client import get_client, get_model_name, has_llm
from suggest_reply import suggest_reply


def main() -> None:
    print("Checking LLM config...")
    if not has_llm():
        print("FAIL: No LLM configured. Set AZURE_OPENAI_KEY + AZURE_OPENAI_ENDPOINT (or OPENAI_API_KEY) in .env")
        sys.exit(1)
    client = get_client()
    model = get_model_name()
    print(f"  Client: {'Azure OpenAI' if 'azure' in str(type(client).__module__).lower() else 'OpenAI'}")
    print(f"  Model/deployment: {model}")

    print("\n1. Classify test (interested reply)...")
    label, reason = classify("Yes, would love to learn more. Can we book a demo next week?")
    print(f"   Label: {label}, Reason: {reason}")
    assert label == "interested", f"Expected interested, got {label}"

    print("\n2. Classify test (not interested)...")
    label2, reason2 = classify("Not interested, please remove me from your list.")
    print(f"   Label: {label2}, Reason: {reason2}")
    assert label2 == "not_interested", f"Expected not_interested, got {label2}"

    print("\n3. Suggest reply test...")
    signal = {
        "leadName": "Dr. Jane Smith",
        "company": "NHS Trust",
        "campaignOrSequence": "Medical Directors",
        "replyText": "Would like to learn more about how this could help our department.",
        "channel": "email",
    }
    draft = suggest_reply(signal)
    print(f"   Draft: {draft[:200]}...")
    assert len(draft) > 20, "Expected a non-trivial draft"

    print("\nAll checks passed. Azure/OpenAI LLM is working.")


if __name__ == "__main__":
    main()
