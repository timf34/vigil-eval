"""Build model-cards.json from rejudge benchmark run."""
import json
import os
import re

BENCHMARK_DIR = r"C:\Users\timf3\VSCode\MentalHealthLLMs\litmus\vigil-results\benchmark-2026-04-07T21-12-39-rejudge-v2"
OUT_FILE = r"C:\Users\timf3\VSCode\vigil-eval\public\model-cards.json"


def read_dossier_json(path):
    """Read state_dossier.json if it exists."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def extract_dossier_summary(md_path):
    """Extract the opening narrative paragraph from a state_dossier.md."""
    try:
        with open(md_path, encoding="utf-8") as f:
            content = f.read()
        # First non-heading paragraph after the H1
        lines = content.split("\n")
        paragraphs = []
        in_paragraph = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                if in_paragraph:
                    break
                continue
            if stripped:
                paragraphs.append(stripped)
                in_paragraph = True
            elif in_paragraph:
                break
        return " ".join(paragraphs)
    except FileNotFoundError:
        return None


result = {}

for model_dir in sorted(os.listdir(BENCHMARK_DIR)):
    model_path = os.path.join(BENCHMARK_DIR, model_dir)
    if not os.path.isdir(model_path):
        continue

    card_json_path = os.path.join(model_path, "model_card.json")
    if not os.path.exists(card_json_path):
        continue

    with open(card_json_path, encoding="utf-8") as f:
        card = json.load(f)

    model_key = card["model"]  # e.g. "openai/gpt-4.1"

    # Gather state dossiers
    state_dossiers = {}
    for state_dir in sorted(os.listdir(model_path)):
        state_path = os.path.join(model_path, state_dir)
        if not os.path.isdir(state_path):
            continue

        dossier_json = read_dossier_json(os.path.join(state_path, "state_dossier.json"))
        dossier_md_summary = extract_dossier_summary(os.path.join(state_path, "state_dossier.md"))

        if dossier_json or dossier_md_summary:
            state_dossiers[state_dir] = {
                "summary": dossier_md_summary,
                "core_metrics": dossier_json.get("core_metrics") if dossier_json else None,
                "behavior_rates": dossier_json.get("behavior_rates") if dossier_json else None,
                "recurring_protective_patterns": dossier_json.get("recurring_protective_patterns") if dossier_json else None,
                "recurring_risky_patterns": dossier_json.get("recurring_risky_patterns") if dossier_json else None,
            }

    result[model_key] = {
        "short_label": card.get("short_label"),
        "summary_blurb": card.get("summary_blurb"),
        "behavior_rates": card.get("behavior_rates"),
        "recurring_protective_patterns": card.get("recurring_protective_patterns"),
        "recurring_risky_patterns": card.get("recurring_risky_patterns"),
        "warning_labels": card.get("warning_labels"),
        "state_dossiers": state_dossiers,
    }

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

print(f"Wrote {OUT_FILE}")
for k, v in result.items():
    print(f"  {k}: {len(v['state_dossiers'])} state dossiers")
