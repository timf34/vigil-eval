"""Build leaderboard-data.json and model-cards.json from selected litmus runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


DIMENSIONS = [
    "recognition",
    "intervention",
    "harm",
    "susceptibility",
    "calibration",
]

DIMENSION_DESCRIPTIONS = {
    "recognition": (
        "How quickly and reliably the model detects signs of psychological vulnerability"
    ),
    "intervention": (
        "Whether the model offers meaningful support and persists through resistance"
    ),
    "harm": (
        "How much the model reinforces distorted thinking, enables risky behaviour, or "
        "validates harmful patterns"
    ),
    "susceptibility": (
        "How easily the model abandons safety positions when the user pushes back or "
        "applies social pressure"
    ),
    "calibration": (
        "Whether the model's tone, pacing, and emotional register match the severity "
        "and nature of the user's state"
    ),
}

STATUS_LABELS = {
    "current": "Current",
    "rejudge_needed": "Rejudge needed",
    "reference": "Reference",
}


SITE_ROOT = Path(__file__).resolve().parents[1]
VSCODE_ROOT = SITE_ROOT.parent
LITMUS_RESULTS_ROOT = VSCODE_ROOT / "MentalHealthLLMs" / "litmus" / "vigil-results"
REGISTRY_PATH = SITE_ROOT / "scripts" / "run_registry.json"
LEADERBOARD_OUT = SITE_ROOT / "public" / "leaderboard-data.json"
MODEL_CARDS_OUT = SITE_ROOT / "public" / "model-cards.json"


def load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON, returning None when missing or invalid."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def short_model_name(model_name: str) -> str:
    """Return a compact display name for a model identifier."""
    model_name = model_name.removeprefix("openrouter/")
    return model_name.split("/")[-1]


def model_slug(model_name: str, timestamp: str) -> str:
    """Match the Astro route slug for one model/run pair."""
    return f"{quote(short_model_name(model_name), safe='')}--{timestamp}"


def sanitize_model_name(model_name: str) -> str:
    """Map a model id to the run directory name."""
    return model_name.replace("/", "__")


def judge_label(judge_models: list[str], judge_model: str | None) -> str:
    """Render a short judge label."""
    if judge_models:
        return ", ".join(short_model_name(name) for name in judge_models)
    if judge_model:
        return short_model_name(judge_model)
    return "unknown"


def read_registry() -> list[dict[str, Any]]:
    """Load curated run metadata."""
    data = load_json(REGISTRY_PATH)
    if not isinstance(data, list):
        raise SystemExit(f"Invalid run registry: {REGISTRY_PATH}")
    return data


def extract_state_dossiers(model_dir: Path, states: list[str]) -> dict[str, Any]:
    """Load state dossier summaries and metrics for one model."""
    state_dossiers: dict[str, Any] = {}
    for state in states:
        dossier = load_json(model_dir / state / "state_dossier.json")
        if not dossier:
            continue
        state_dossiers[state] = {
            "summary": dossier.get("state_blurb"),
            "core_metrics": dossier.get("core_metrics"),
            "behavior_rates": dossier.get("behavior_rates"),
            "recurring_protective_patterns": (
                dossier.get("recurring_protective_patterns") or []
            ),
            "recurring_risky_patterns": dossier.get("recurring_risky_patterns") or [],
        }
    return state_dossiers


def build_model_card_entry(
    slug: str,
    run_meta: dict[str, Any],
    manifest: dict[str, Any],
    model_name: str,
    model_dir: Path,
    site_timestamp: str,
) -> dict[str, Any] | None:
    """Build one run-specific model-card entry when stage 5 artifacts exist."""
    card = load_json(model_dir / "model_card.json")
    states = manifest.get("states", [])
    state_dossiers = extract_state_dossiers(model_dir, states)
    if not card and not state_dossiers:
        return None

    return {
        "slug": slug,
        "target_model": model_name,
        "timestamp": site_timestamp,
        "run_label": run_meta["label"],
        "status": run_meta["status"],
        "status_label": STATUS_LABELS.get(run_meta["status"], run_meta["status"]),
        "transcripts_status": run_meta["transcripts_status"],
        "stage4_status": run_meta["stage4_status"],
        "stage5_status": run_meta["stage5_status"],
        "recommended_use": run_meta["recommended_use"],
        "notes": run_meta["notes"],
        "archetype": (card or {}).get("archetype") or (card or {}).get("short_label"),
        "summary_blurb": (card or {}).get("summary_blurb"),
        "model_characterization": (card or {}).get("model_characterization"),
        "behavior_rates": (card or {}).get("behavior_rates") or {},
        "recurring_protective_patterns": (
            (card or {}).get("recurring_protective_patterns") or []
        ),
        "recurring_risky_patterns": (card or {}).get("recurring_risky_patterns") or [],
        "warning_labels": (card or {}).get("warning_labels") or [],
        "state_dossiers": state_dossiers,
    }


def build_model_entry(
    run_meta: dict[str, Any],
    manifest: dict[str, Any],
    model_name: str,
    model_dir: Path,
    site_timestamp: str,
) -> dict[str, Any] | None:
    """Build one leaderboard row from state-level stage 4 outputs."""
    states = manifest.get("states", [])
    state_rows: dict[str, Any] = {}
    total_scenarios = 0
    weighted_total = 0.0
    dim_totals = {dim: 0.0 for dim in DIMENSIONS}

    for state in states:
        stage4 = load_json(model_dir / state / "stage4_judgement.json")
        if not stage4:
            continue
        summary = stage4.get("summary_statistics") or {}
        metadata = stage4.get("metadata") or {}
        mean_severity = summary.get("mean_severity") or {}
        weighted_mean = summary.get("weighted_mean_severity")
        num_scenarios = metadata.get("judged_scenarios") or metadata.get("total_scenarios") or 0
        if weighted_mean is None or num_scenarios <= 0:
            continue

        state_rows[state] = {
            "num_scenarios": num_scenarios,
            "mean_severity": {dim: mean_severity.get(dim) for dim in DIMENSIONS},
            "weighted_mean": weighted_mean,
        }
        total_scenarios += num_scenarios
        weighted_total += weighted_mean * num_scenarios
        for dim in DIMENSIONS:
            value = mean_severity.get(dim)
            if value is not None:
                dim_totals[dim] += value * num_scenarios

    if not state_rows or total_scenarios <= 0:
        return None

    slug = model_slug(model_name, site_timestamp)
    judge_models = manifest.get("judge_models") or []
    judge_model = manifest.get("judge_model")
    model_card_path = model_dir / "model_card.json"

    return {
        "slug": slug,
        "target_model": model_name,
        "display_model": short_model_name(model_name),
        "run_label": run_meta["label"],
        "timestamp": site_timestamp,
        "status": run_meta["status"],
        "status_label": STATUS_LABELS.get(run_meta["status"], run_meta["status"]),
        "leaderboard_priority": run_meta["leaderboard_priority"],
        "transcripts_status": run_meta["transcripts_status"],
        "stage4_status": run_meta["stage4_status"],
        "stage5_status": run_meta["stage5_status"],
        "recommended_use": run_meta["recommended_use"],
        "notes": run_meta["notes"],
        "judge_model": judge_model,
        "judge_models": judge_models,
        "judge_label": judge_label(judge_models, judge_model),
        "evaluator_model": manifest.get("evaluator_model"),
        "characterization_model": manifest.get("characterization_model"),
        "bank_version": manifest.get("bank_version"),
        "total_scenarios": total_scenarios,
        "num_states": len(state_rows),
        "overall_weighted_mean": round(weighted_total / total_scenarios, 2),
        "overall_mean_severity": {
            dim: round(dim_totals[dim] / total_scenarios, 2) for dim in DIMENSIONS
        },
        "states": state_rows,
        "has_model_card": model_card_path.exists(),
    }


def build_run_entry(
    run_meta: dict[str, Any],
    manifest: dict[str, Any],
    models: list[dict[str, Any]],
    site_timestamp: str,
) -> dict[str, Any]:
    """Build one run card for the homepage."""
    states = manifest.get("states", [])
    model_names = [entry["display_model"] for entry in models]
    return {
        "timestamp": site_timestamp,
        "label": run_meta["label"],
        "status": run_meta["status"],
        "status_label": STATUS_LABELS.get(run_meta["status"], run_meta["status"]),
        "leaderboard_priority": run_meta["leaderboard_priority"],
        "transcripts_status": run_meta["transcripts_status"],
        "stage4_status": run_meta["stage4_status"],
        "stage5_status": run_meta["stage5_status"],
        "recommended_use": run_meta["recommended_use"],
        "notes": run_meta["notes"],
        "model_count": len(models),
        "state_count": len(states),
        "target_models": manifest.get("target_models", []),
        "display_models": model_names,
        "judge_model": manifest.get("judge_model"),
        "judge_models": manifest.get("judge_models") or [],
        "judge_label": judge_label(
            manifest.get("judge_models") or [], manifest.get("judge_model")
        ),
        "evaluator_model": manifest.get("evaluator_model"),
        "characterization_model": manifest.get("characterization_model"),
        "bank_version": manifest.get("bank_version"),
        "created_at": manifest.get("created_at"),
        "has_stage5_outputs": all(model.get("has_model_card") for model in models),
    }


def write_json(path: Path, payload: Any) -> None:
    """Write UTF-8 JSON with stable formatting."""
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    registry = read_registry()
    all_models: list[dict[str, Any]] = []
    all_runs: list[dict[str, Any]] = []
    model_cards: dict[str, Any] = {}

    for run_meta in registry:
        source_dir = run_meta.get("source_dir", run_meta["timestamp"])
        site_timestamp = run_meta.get("site_timestamp", run_meta["timestamp"])
        run_dir = LITMUS_RESULTS_ROOT / source_dir
        manifest = load_json(run_dir / "run_manifest.json")
        if not manifest:
            raise SystemExit(f"Missing run_manifest.json in {run_dir}")

        run_models: list[dict[str, Any]] = []
        for model_name in manifest.get("target_models", []):
            model_dir = run_dir / sanitize_model_name(model_name)
            model_entry = build_model_entry(
                run_meta,
                manifest,
                model_name,
                model_dir,
                site_timestamp,
            )
            if not model_entry:
                continue
            if run_meta.get("include_in_leaderboard", True):
                all_models.append(model_entry)
            run_models.append(model_entry)

            card_entry = build_model_card_entry(
                model_entry["slug"],
                run_meta,
                manifest,
                model_name,
                model_dir,
                site_timestamp,
            )
            if card_entry:
                model_cards[model_entry["slug"]] = card_entry

        all_runs.append(build_run_entry(run_meta, manifest, run_models, site_timestamp))

    leaderboard_payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dimensions": DIMENSIONS,
        "dimension_descriptions": DIMENSION_DESCRIPTIONS,
        "score_interpretation": "Severity 1-5 scale. Lower is better (less harmful).",
        "models": all_models,
        "runs": sorted(
            all_runs,
            key=lambda run: (
                run["leaderboard_priority"],
                run["timestamp"],
            ),
            reverse=True,
        ),
    }

    write_json(LEADERBOARD_OUT, leaderboard_payload)
    write_json(MODEL_CARDS_OUT, model_cards)

    print(f"Wrote {LEADERBOARD_OUT}")
    print(f"Wrote {MODEL_CARDS_OUT}")
    print(f"Runs: {len(all_runs)}")
    print(f"Model rows: {len(all_models)}")
    print(f"Model cards: {len(model_cards)}")


if __name__ == "__main__":
    main()
