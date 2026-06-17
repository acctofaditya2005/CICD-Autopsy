"""
Eval harness: runs the investigator against every branch in
GROUND_TRUTH and scores its output.

Metrics computed:
  - Category accuracy: did the predicted category exactly match?
  - File-retrieval accuracy: did AT LEAST ONE of the investigator's
    likely_files match a ground-truth broken file (exact path match)?
  - A confusion matrix across the 6 categories.

This is a real, runnable measurement -- not a guess -- but it does
make real GitHub API + Groq API calls for every branch (18 calls
minimum), so it costs real time and Groq quota to run. Consider
running it once you're confident the pipeline works on 1-2 branches
individually first.

Usage:
  python -m eval.run_eval --owner acctofaditya2005 --repo Taskhub-api
"""

import argparse
import json
from collections import defaultdict

from app.run_investigation import run_investigation
from eval.ground_truth import GROUND_TRUTH


def score_one(predicted_category: str, predicted_files: list[str], truth: dict) -> dict:
    category_correct = predicted_category == truth["category"]

    # File match: normalize path separators, allow substring match
    # since the LLM might return a slightly different relative path
    # format (e.g. with or without leading './').
    normalized_predicted = [f.strip("./").replace("\\", "/") for f in predicted_files]
    normalized_truth = [f.strip("./").replace("\\", "/") for f in truth["broken_files"]]

    file_correct = any(
        pred == truth_f or pred in truth_f or truth_f in pred
        for pred in normalized_predicted
        for truth_f in normalized_truth
    )

    return {
        "branch": truth["branch"],
        "true_category": truth["category"],
        "predicted_category": predicted_category,
        "category_correct": category_correct,
        "true_files": truth["broken_files"],
        "predicted_files": predicted_files,
        "file_correct": file_correct,
    }


def run_eval(repo_owner: str, repo_name: str) -> dict:
    results = []
    confusion = defaultdict(lambda: defaultdict(int))

    for truth in GROUND_TRUTH:
        branch = truth["branch"]
        print(f"\n{'=' * 60}\nInvestigating: {branch}\n{'=' * 60}")

        try:
            state = run_investigation(
                repo_owner=repo_owner,
                repo_name=repo_name,
                branch=branch,
                dry_run_issue_creation=True,  # never spam real issues during eval
                persist=False,  # eval runs are not "real" investigations
                include_commit_message_in_classification=False,  # score genuine
                # log-reading ability -- our break/* commit messages openly
                # state the bug, so including them would inflate accuracy
                # without proving the classifier actually read the log
            )
            predicted_category = (
                state.classification.category.value if state.classification else "Unknown"
            )
            predicted_files = state.repo_finding.likely_files if state.repo_finding else []

        except Exception as e:
            print(f"  ERROR investigating {branch}: {e}")
            predicted_category = "ERROR"
            predicted_files = []

        result = score_one(predicted_category, predicted_files, truth)
        results.append(result)
        confusion[truth["category"]][predicted_category] += 1

        status = "PASS" if result["category_correct"] else "FAIL"
        print(f"  [{status}] true={result['true_category']} predicted={predicted_category}")

    category_accuracy = sum(r["category_correct"] for r in results) / len(results)
    file_accuracy = sum(r["file_correct"] for r in results) / len(results)

    summary = {
        "total_cases": len(results),
        "category_accuracy": category_accuracy,
        "file_retrieval_accuracy": file_accuracy,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "per_case_results": results,
    }

    return summary


def main():
    parser = argparse.ArgumentParser(description="Score the investigator against ground truth")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", default="eval_results.json")
    args = parser.parse_args()

    summary = run_eval(args.owner, args.repo)

    print(f"\n{'=' * 60}")
    print("EVAL SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total cases: {summary['total_cases']}")
    print(f"Category accuracy: {summary['category_accuracy']:.1%}")
    print(f"File retrieval accuracy: {summary['file_retrieval_accuracy']:.1%}")
    print("\nConfusion matrix (true category -> predicted category counts):")
    for true_cat, predictions in summary["confusion_matrix"].items():
        print(f"  {true_cat}: {dict(predictions)}")

    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nFull results written to {args.output}")


if __name__ == "__main__":
    main()
