"""
Evaluation Framework for Construction Cost Estimation

Compares predicted costs against ground truth and generates detailed
metrics reports including MAPE, MAE, RMSE, R², per-type and per-division
breakdowns.

Usage:
    python evaluate.py --predictions results/dummy_predictions.json
    python evaluate.py --predictions results/dummy_predictions.json --dataset eval_dataset.json
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np
    import yaml
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)


def load_config(config_path: str = "eval_config.yaml") -> Dict:
    """Load evaluation configuration."""
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    # Defaults
    return {
        "thresholds": {
            "total_mape_acceptable": 0.15,
            "division_mape_acceptable": 0.25,
            "within_10_pct_target": 0.40,
            "within_20_pct_target": 0.65,
            "within_30_pct_target": 0.80,
        }
    }


def load_dataset(dataset_path: str = "eval_dataset.json") -> List[Dict]:
    """Load the ground truth dataset."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_predictions(predictions_path: str) -> List[Dict]:
    """Load prediction results."""
    with open(predictions_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── METRIC CALCULATIONS ─────────────────────────────────────────────

def calc_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Percentage Error."""
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])))


def calc_mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Error."""
    return float(np.mean(np.abs(actual - predicted)))


def calc_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Root Mean Squared Error."""
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def calc_r_squared(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Coefficient of determination (R²)."""
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    if ss_tot == 0:
        return 0.0
    return float(1 - ss_res / ss_tot)


def calc_within_pct(actual: np.ndarray, predicted: np.ndarray, threshold: float) -> float:
    """Fraction of predictions within threshold % of actual."""
    mask = actual != 0
    if not mask.any():
        return 0.0
    pct_errors = np.abs((actual[mask] - predicted[mask]) / actual[mask])
    return float(np.mean(pct_errors <= threshold))


# ─── EVALUATION ───────────────────────────────────────────────────────

def evaluate(
    dataset: List[Dict],
    predictions: List[Dict],
    config: Dict,
) -> Dict:
    """
    Run full evaluation comparing predictions to ground truth.

    Returns a results dict with overall, per-type, and per-division metrics.
    """
    # Index predictions by project_id
    pred_map = {p["project_id"]: p for p in predictions}

    # Match predictions to ground truth
    matched = []
    missing = []
    for entry in dataset:
        pid = entry["project_id"]
        if pid in pred_map:
            matched.append((entry, pred_map[pid]))
        else:
            missing.append(pid)

    if not matched:
        return {"error": "No matching predictions found", "missing": missing}

    # ── Overall Total Cost Metrics ────────────────────────────────────
    actuals = np.array([e["ground_truth"]["total_cost"] for e, _ in matched])
    preds = np.array([p["predicted_total"] for _, p in matched])

    overall = {
        "n": len(matched),
        "missing": missing,
        "mape": calc_mape(actuals, preds),
        "mae": calc_mae(actuals, preds),
        "rmse": calc_rmse(actuals, preds),
        "r_squared": calc_r_squared(actuals, preds),
        "within_10_pct": calc_within_pct(actuals, preds, 0.10),
        "within_20_pct": calc_within_pct(actuals, preds, 0.20),
        "within_30_pct": calc_within_pct(actuals, preds, 0.30),
        "median_pct_error": float(np.median(np.abs((actuals - preds) / actuals))),
        "max_pct_error": float(np.max(np.abs((actuals - preds) / actuals))),
    }

    # Per-case details
    case_details = []
    for entry, pred in matched:
        gt_total = entry["ground_truth"]["total_cost"]
        pred_total = pred["predicted_total"]
        pct_err = abs(gt_total - pred_total) / gt_total if gt_total != 0 else 0
        case_details.append({
            "project_id": entry["project_id"],
            "name": entry["name"],
            "building_type": entry["building_type"],
            "sub_type": entry["sub_type"],
            "actual_total": gt_total,
            "predicted_total": pred_total,
            "absolute_error": abs(gt_total - pred_total),
            "pct_error": pct_err,
            "within_10": pct_err <= 0.10,
            "within_20": pct_err <= 0.20,
            "within_30": pct_err <= 0.30,
        })

    # ── Per Building Type Metrics ─────────────────────────────────────
    building_types = sorted(set(e["building_type"] for e, _ in matched))
    per_type = {}
    for btype in building_types:
        bt_matched = [(e, p) for e, p in matched if e["building_type"] == btype]
        bt_actuals = np.array([e["ground_truth"]["total_cost"] for e, _ in bt_matched])
        bt_preds = np.array([p["predicted_total"] for _, p in bt_matched])
        per_type[btype] = {
            "n": len(bt_matched),
            "mape": calc_mape(bt_actuals, bt_preds),
            "mae": calc_mae(bt_actuals, bt_preds),
            "rmse": calc_rmse(bt_actuals, bt_preds),
            "r_squared": calc_r_squared(bt_actuals, bt_preds),
            "within_10_pct": calc_within_pct(bt_actuals, bt_preds, 0.10),
            "within_20_pct": calc_within_pct(bt_actuals, bt_preds, 0.20),
            "within_30_pct": calc_within_pct(bt_actuals, bt_preds, 0.30),
        }

    # ── Per CSI Division Metrics ──────────────────────────────────────
    # Collect all division names from ground truth
    all_divisions = set()
    for entry, _ in matched:
        all_divisions.update(entry["ground_truth"]["division_breakdown"].keys())
    all_divisions = sorted(all_divisions)

    per_division = {}
    for div in all_divisions:
        div_actuals = []
        div_preds = []
        for entry, pred in matched:
            gt_div = entry["ground_truth"]["division_breakdown"].get(div, 0)
            pred_divs = pred.get("predicted_divisions", {})
            pd_div = pred_divs.get(div, 0)
            if gt_div > 0:  # Only include non-zero actual values
                div_actuals.append(gt_div)
                div_preds.append(pd_div)

        if div_actuals:
            da = np.array(div_actuals)
            dp = np.array(div_preds)
            per_division[div] = {
                "n": len(div_actuals),
                "mape": calc_mape(da, dp),
                "mae": calc_mae(da, dp),
                "rmse": calc_rmse(da, dp),
                "within_20_pct": calc_within_pct(da, dp, 0.20),
                "avg_actual": float(np.mean(da)),
                "avg_predicted": float(np.mean(dp)),
            }

    # ── Threshold Assessment ──────────────────────────────────────────
    thresholds = config.get("thresholds", {})
    assessment = {
        "total_mape_pass": overall["mape"] <= thresholds.get("total_mape_acceptable", 0.15),
        "within_10_pass": overall["within_10_pct"] >= thresholds.get("within_10_pct_target", 0.40),
        "within_20_pass": overall["within_20_pct"] >= thresholds.get("within_20_pct_target", 0.65),
        "within_30_pass": overall["within_30_pct"] >= thresholds.get("within_30_pct_target", 0.80),
    }

    # Check per-division MAPE threshold
    div_mape_threshold = thresholds.get("division_mape_acceptable", 0.25)
    div_failures = []
    for div, metrics in per_division.items():
        if metrics["mape"] > div_mape_threshold:
            div_failures.append({"division": div, "mape": metrics["mape"]})
    assessment["division_mape_pass"] = len(div_failures) == 0
    assessment["division_failures"] = div_failures

    return {
        "timestamp": datetime.now().isoformat(),
        "overall": overall,
        "per_type": per_type,
        "per_division": per_division,
        "assessment": assessment,
        "case_details": case_details,
    }


# ─── REPORT GENERATION ───────────────────────────────────────────────

def generate_markdown_report(results: Dict) -> str:
    """Generate a formatted Markdown evaluation report."""
    lines = []
    lines.append("# Construction Cost Estimation — Evaluation Report")
    lines.append(f"\n**Generated:** {results['timestamp']}")

    # ── Overall Metrics ───────────────────────────────────────────────
    o = results["overall"]
    lines.append("\n## Overall Metrics")
    lines.append(f"\n| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Cases Evaluated | {o['n']} |")
    lines.append(f"| MAPE | {o['mape']:.1%} |")
    lines.append(f"| MAE | ${o['mae']:,.0f} |")
    lines.append(f"| RMSE | ${o['rmse']:,.0f} |")
    lines.append(f"| R² | {o['r_squared']:.4f} |")
    lines.append(f"| Within 10% | {o['within_10_pct']:.1%} |")
    lines.append(f"| Within 20% | {o['within_20_pct']:.1%} |")
    lines.append(f"| Within 30% | {o['within_30_pct']:.1%} |")
    lines.append(f"| Median % Error | {o['median_pct_error']:.1%} |")
    lines.append(f"| Max % Error | {o['max_pct_error']:.1%} |")

    if o["missing"]:
        lines.append(f"\n**Missing predictions:** {', '.join(o['missing'])}")

    # ── Threshold Assessment ──────────────────────────────────────────
    a = results["assessment"]
    lines.append("\n## Threshold Assessment")
    lines.append(f"\n| Check | Result |")
    lines.append(f"|-------|--------|")
    lines.append(f"| Total MAPE ≤ 15% | {'PASS' if a['total_mape_pass'] else 'FAIL'} |")
    lines.append(f"| ≥40% within 10% | {'PASS' if a['within_10_pass'] else 'FAIL'} |")
    lines.append(f"| ≥65% within 20% | {'PASS' if a['within_20_pass'] else 'FAIL'} |")
    lines.append(f"| ≥80% within 30% | {'PASS' if a['within_30_pass'] else 'FAIL'} |")
    lines.append(f"| All divisions ≤ 25% MAPE | {'PASS' if a['division_mape_pass'] else 'FAIL'} |")

    if a["division_failures"]:
        lines.append(f"\n**Division MAPE failures:**")
        for df in a["division_failures"]:
            lines.append(f"  - {df['division']}: {df['mape']:.1%}")

    # ── Per Building Type ─────────────────────────────────────────────
    lines.append("\n## Per Building Type")
    lines.append(f"\n| Type | N | MAPE | MAE | R² | ≤10% | ≤20% | ≤30% |")
    lines.append(f"|------|---|------|-----|-----|------|------|------|")
    for btype, m in sorted(results["per_type"].items()):
        lines.append(
            f"| {btype} | {m['n']} | {m['mape']:.1%} | ${m['mae']:,.0f} | "
            f"{m['r_squared']:.3f} | {m['within_10_pct']:.0%} | "
            f"{m['within_20_pct']:.0%} | {m['within_30_pct']:.0%} |"
        )

    # ── Per CSI Division ──────────────────────────────────────────────
    lines.append("\n## Per CSI Division")
    lines.append(f"\n| Division | N | MAPE | MAE | ≤20% | Avg Actual | Avg Predicted |")
    lines.append(f"|----------|---|------|-----|------|------------|---------------|")
    for div, m in sorted(results["per_division"].items()):
        flag = " **" if m["mape"] > 0.25 else ""
        lines.append(
            f"| {div} | {m['n']} | {m['mape']:.1%}{flag} | ${m['mae']:,.0f} | "
            f"{m['within_20_pct']:.0%} | ${m['avg_actual']:,.0f} | ${m['avg_predicted']:,.0f} |"
        )

    # ── Top 10 Worst Predictions ──────────────────────────────────────
    lines.append("\n## Top 10 Largest Errors")
    sorted_cases = sorted(results["case_details"], key=lambda x: x["pct_error"], reverse=True)
    lines.append(f"\n| Project | Type | Actual | Predicted | Error % |")
    lines.append(f"|---------|------|--------|-----------|---------|")
    for c in sorted_cases[:10]:
        lines.append(
            f"| {c['project_id']} ({c['name']}) | {c['sub_type']} | "
            f"${c['actual_total']:,.0f} | ${c['predicted_total']:,.0f} | "
            f"{c['pct_error']:.1%} |"
        )

    # ── Top 10 Best Predictions ───────────────────────────────────────
    lines.append("\n## Top 10 Best Predictions")
    lines.append(f"\n| Project | Type | Actual | Predicted | Error % |")
    lines.append(f"|---------|------|--------|-----------|---------|")
    for c in sorted_cases[-10:]:
        lines.append(
            f"| {c['project_id']} ({c['name']}) | {c['sub_type']} | "
            f"${c['actual_total']:,.0f} | ${c['predicted_total']:,.0f} | "
            f"{c['pct_error']:.1%} |"
        )

    # ── Full Results Table ────────────────────────────────────────────
    lines.append("\n## All Cases")
    lines.append(f"\n| Project | Name | Type | Actual | Predicted | Error | ≤20% |")
    lines.append(f"|---------|------|------|--------|-----------|-------|------|")
    for c in sorted(results["case_details"], key=lambda x: x["project_id"]):
        w20 = "Y" if c["within_20"] else ""
        lines.append(
            f"| {c['project_id']} | {c['name'][:30]} | {c['sub_type']} | "
            f"${c['actual_total']:,.0f} | ${c['predicted_total']:,.0f} | "
            f"{c['pct_error']:.1%} | {w20} |"
        )

    lines.append(f"\n---\n*Report generated by evaluate.py*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate construction cost predictions")
    parser.add_argument("--predictions", required=True,
                        help="Path to predictions JSON file")
    parser.add_argument("--dataset", default="eval_dataset.json",
                        help="Path to ground truth dataset JSON")
    parser.add_argument("--config", default="eval_config.yaml",
                        help="Path to evaluation config YAML")
    parser.add_argument("--output-dir", default="results",
                        help="Directory for output files")
    args = parser.parse_args()

    # Load inputs
    print("Loading dataset...")
    dataset = load_dataset(args.dataset)
    print(f"  {len(dataset)} ground truth cases")

    print("Loading predictions...")
    predictions = load_predictions(args.predictions)
    print(f"  {len(predictions)} predictions")

    config = load_config(args.config)

    # Run evaluation
    print("\nRunning evaluation...")
    results = evaluate(dataset, predictions, config)

    if "error" in results:
        print(f"\nERROR: {results['error']}")
        sys.exit(1)

    # Output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for filenames
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Write JSON results
    json_path = output_dir / f"eval_results_{ts}.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nJSON results: {json_path}")

    # Write Markdown report
    report = generate_markdown_report(results)
    md_path = output_dir / f"eval_report_{ts}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Markdown report: {md_path}")

    # Print summary
    o = results["overall"]
    a = results["assessment"]
    print(f"\n{'='*60}")
    print(f"EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Cases evaluated: {o['n']}")
    print(f"  MAPE:            {o['mape']:.1%}  {'PASS' if a['total_mape_pass'] else 'FAIL'}")
    print(f"  MAE:             ${o['mae']:,.0f}")
    print(f"  RMSE:            ${o['rmse']:,.0f}")
    print(f"  R²:              {o['r_squared']:.4f}")
    print(f"  Within 10%:      {o['within_10_pct']:.0%}  {'PASS' if a['within_10_pass'] else 'FAIL'}")
    print(f"  Within 20%:      {o['within_20_pct']:.0%}  {'PASS' if a['within_20_pass'] else 'FAIL'}")
    print(f"  Within 30%:      {o['within_30_pct']:.0%}  {'PASS' if a['within_30_pass'] else 'FAIL'}")
    print(f"  Division MAPE:   {'PASS' if a['division_mape_pass'] else 'FAIL'}")

    # Per-type summary
    print(f"\n  Per-type MAPE:")
    for btype, m in sorted(results["per_type"].items()):
        print(f"    {btype:20s}  {m['mape']:.1%}  (n={m['n']})")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
