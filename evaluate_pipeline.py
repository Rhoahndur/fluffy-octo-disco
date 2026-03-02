import json
import re
from pathlib import Path
from cost_estimator import estimate_project, get_floor_plan_images

def parse_ground_truth(file_path):
    """Parses ground_truth table file and returns a dict mapping project_id to ground_truth_cost."""
    target_projects = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Pattern to match: │ PRJ-001 │        $8,750,000 │ ...
            match = re.search(r'│\s*(PRJ-\d+)\s*│\s*\$([\d,]+)\s*│', line)
            if match:
                project_id = match.group(1)
                cost_str = match.group(2).replace(',', '')
                target_projects[project_id] = float(cost_str)
    return target_projects

def load_projects(dataset_path):
    """Loads all projects from JSON dataset into a dict by project_id."""
    projects_by_id = {}
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for p in data:
            if 'project_id' in p:
                projects_by_id[p['project_id']] = p
    return projects_by_id

def main():
    print("Loading Ground Truth...")
    gt_costs = parse_ground_truth('ground_truth')
    print(f"Found {len(gt_costs)} projects in ground_truth.")
    
    print("Loading Dataset...")
    dataset = load_projects('rich_eval_dataset.json')
    
    results = []
    
    for project_id, gt_cost in gt_costs.items():
        print("=" * 60)
        print(f"Evaluating {project_id} (Ground Truth: ${gt_cost:,.2f})")
        print("=" * 60)
        
        project_data = dataset.get(project_id)
        if not project_data:
            print(f"WARNING: No project data found for {project_id} in rich_eval_dataset.json. Skipping.")
            continue
            
        floor_plan_images = get_floor_plan_images(project_id, 'rich_floor_plans')
        
        run_costs = []
        for i in range(3):
            print(f"\n--- Run {i+1} ---")
            try:
                # We need to suppress some of the verbose output from estimate_project if possible, 
                # but it prints directly. Oh well.
                res = estimate_project(project_data, floor_plan_images)
                total_cost = res['estimate']['total_cost']
                run_costs.append(total_cost)
                print(f"Run {i+1} Estimated Cost: ${total_cost:,.2f}")
            except Exception as e:
                print(f"Run {i+1} failed: {e}")
        
        if run_costs:
            avg_cost = sum(run_costs) / len(run_costs)
            diff = avg_cost - gt_cost
            pct_diff = (diff / gt_cost) * 100
            
            results.append({
                'project_id': project_id,
                'ground_truth': gt_cost,
                'run_costs': run_costs,
                'average_estimated': avg_cost,
                'difference': diff,
                'percent_difference': pct_diff
            })
            
            print(f"\n[SUMMARY for {project_id}]")
            print(f"Ground Truth: ${gt_cost:,.2f}")
            print(f"Average Estimated ({len(run_costs)} runs): ${avg_cost:,.2f}")
            print(f"Difference: ${abs(diff):,.2f} ({'+' if diff > 0 else ''}{pct_diff:.2f}%)")
        else:
            print(f"All runs failed for {project_id}.")

    print("\n" + "=" * 60)
    print("FINAL EVALUATION REPORT")
    print("=" * 60)
    print(f"{'Project':<10} | {'Ground Truth':<15} | {'Average Est.':<15} | {'Difference':<15} | {'% Diff':<10}")
    print("-" * 75)
    
    overall_pct_errors = []
    for r in results:
        gt = f"${r['ground_truth']:,.0f}"
        est = f"${r['average_estimated']:,.0f}"
        diff = f"${r['difference']:,.0f}"
        pct = f"{r['percent_difference']:.1f}%"
        print(f"{r['project_id']:<10} | {gt:>15} | {est:>15} | {diff:>15} | {pct:>10}")
        overall_pct_errors.append(abs(r['percent_difference']))
        
    if overall_pct_errors:
        mean_abs_error = sum(overall_pct_errors) / len(overall_pct_errors)
        print("-" * 75)
        print(f"Mean Absolute Percentage Error (MAPE): {mean_abs_error:.2f}%")
        
    with open('eval_report.json', 'w', encoding='utf-8') as f:
        json.dump({'results': results, 'mape': mean_abs_error if overall_pct_errors else 0}, f, indent=2)
        
    with open('eval_report.md', 'w', encoding='utf-8') as f:
        f.write("# Evaluation Report\n\n")
        f.write(f"| {'Project':<10} | {'Ground Truth':<15} | {'Average Est.':<15} | {'Difference':<15} | {'% Diff':<10} |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for r in results:
            gt_str = f"${r['ground_truth']:,.0f}"
            est_str = f"${r['average_estimated']:,.0f}"
            diff_str = f"${r['difference']:,.0f}"
            pct_str = f"{r['percent_difference']:.1f}%"
            f.write(f"| {r['project_id']:<10} | {gt_str:>15} | {est_str:>15} | {diff_str:>15} | {pct_str:>10} |\n")
        
        if overall_pct_errors:
            f.write(f"\n**Mean Absolute Percentage Error (MAPE)**: {mean_abs_error:.2f}%\n")
        
if __name__ == '__main__':
    main()
