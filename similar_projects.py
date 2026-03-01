"""
Similar Project Matching

Direct port of web/src/lib/similar/matcher.ts
Finds similar projects from eval datasets for comparison.
"""

import json
from pathlib import Path
from typing import Optional

# Module-level cache
_eval_dataset = []
_rich_dataset = []
_datasets_loaded = False


def _load_datasets() -> None:
    """
    Load eval datasets from JSON files (called once on first use).
    Direct port of loadDatasets from matcher.ts.
    """
    global _eval_dataset, _rich_dataset, _datasets_loaded

    if _datasets_loaded:
        return

    base_dir = Path(__file__).parent

    try:
        eval_path = base_dir / "eval_dataset.json"
        if eval_path.exists():
            with open(eval_path, "r", encoding="utf-8") as f:
                _eval_dataset = json.load(f)
    except Exception as e:
        print(f"Failed to load eval_dataset.json: {e}")
        _eval_dataset = []

    try:
        rich_path = base_dir / "rich_eval_dataset.json"
        if rich_path.exists():
            with open(rich_path, "r", encoding="utf-8") as f:
                _rich_dataset = json.load(f)
    except Exception as e:
        print(f"Failed to load rich_eval_dataset.json: {e}")
        _rich_dataset = []

    _datasets_loaded = True


def find_similar_projects(
    criteria: dict,
    limit: int = 3,
) -> list:
    """
    Find similar projects from the eval datasets.
    Direct port of findSimilarProjects from matcher.ts.

    Args:
        criteria: dict with building_type, sub_type, quality, area_sf
        limit: Maximum number of results

    Returns:
        List of SimilarProject dicts sorted by similarity score
    """
    _load_datasets()

    all_projects = _eval_dataset + _rich_dataset

    if not all_projects:
        return []

    # Score each project by similarity
    scored = []
    for project in all_projects:
        score = _calculate_similarity(criteria, project)
        scored.append({"project": project, "score": score})

    # Sort by score descending and take top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    top_projects = scored[:limit]

    results = []
    for item in top_projects:
        project = item["project"]
        ground_truth = project.get("ground_truth", {})
        results.append({
            "project_id": project.get("project_id", ""),
            "name": project.get("name", ""),
            "building_type": project.get("building_type", ""),
            "sub_type": project.get("sub_type", ""),
            "quality": project.get("quality", ""),
            "area_sf": project.get("area_sf", 0),
            "total_cost": ground_truth.get("total_cost", 0),
            "cost_per_sf": ground_truth.get("cost_per_sf", 0),
            "similarity_score": round(item["score"] * 100) / 100,
        })

    return results


def _calculate_similarity(query: dict, project: dict) -> float:
    """
    Calculate similarity score between a query and a project.
    Direct port of calculateSimilarity from matcher.ts.

    Scoring dimensions:
    - Building type match: 40 points
    - Sub-type match: 30 points
    - Quality match: 15 points
    - Area similarity: 15 points
    """
    score = 0.0

    # Exact building type match: +40 points
    if query.get("building_type") == project.get("building_type"):
        score += 40
    else:
        # Partial credit for related types
        related_types = {
            "residential": ["commercial"],
            "commercial": ["residential", "institutional"],
            "industrial": ["infrastructure"],
            "institutional": ["commercial"],
            "infrastructure": ["industrial"],
        }
        project_type = project.get("building_type", "")
        related = related_types.get(query.get("building_type", ""), [])
        if project_type in related:
            score += 15

    # Sub-type match: +30 points
    query_sub = query.get("sub_type", "")
    proj_sub = project.get("sub_type", "")
    if query_sub and query_sub == proj_sub:
        score += 30
    elif query_sub:
        # Partial credit for similar sub-types
        query_words = set(query_sub.lower().split("_"))
        proj_words = set(proj_sub.lower().split("_"))
        overlap = len(query_words & proj_words)
        score += overlap * 8

    # Quality match: +15 points
    query_quality = query.get("quality", "")
    proj_quality = project.get("quality", "")
    if query_quality and query_quality == proj_quality:
        score += 15
    elif query_quality and proj_quality:
        # Partial credit for adjacent quality
        qualities = ["low", "mid", "high"]
        q_idx = qualities.index(query_quality) if query_quality in qualities else -1
        p_idx = qualities.index(proj_quality) if proj_quality in qualities else -1
        if q_idx >= 0 and p_idx >= 0 and abs(q_idx - p_idx) == 1:
            score += 8

    # Area similarity: +15 points (scaled by closeness)
    query_area = query.get("area_sf", 0)
    proj_area = project.get("area_sf", 0)
    if query_area and proj_area:
        area_ratio = min(query_area, proj_area) / max(query_area, proj_area)
        score += area_ratio * 15

    return score
