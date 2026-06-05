"""
RAGAS Evaluation Script — RAG Q&A System
Compares CustomOpenSearchStack vs KnowledgeBaseStack on 4 RAGAS metrics.

Usage:
  1. Deploy both stacks
  2. Copy config.example.json to config.json and fill in API URLs
  3. pip install -r requirements.txt
  4. python evaluate.py
  5. Results saved to results/
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import boto3
import requests
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_aws import ChatBedrock, BedrockEmbeddings

RESULTS_DIR = Path(__file__).parent / "results"
CONFIG_PATH = Path(__file__).parent / "config.json"
DATASET_PATH = Path(__file__).parent / "dataset.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("ERROR: config.json not found.")
        print("  cp evaluation/config.example.json evaluation/config.json")
        print("  Then fill in your API endpoint URLs.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return json.load(f)


def query_api(api_url: str, question: str, language: str) -> dict:
    """Call a /qa endpoint; return answer + contexts."""
    try:
        resp = requests.post(
            f"{api_url}/qa",
            json={"question": question, "language": language},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "answer": data.get("answer", ""),
            "contexts": data.get("contexts", []),
            "processing_time": data.get("processingTime", 0.0),
        }
    except Exception as exc:
        print(f"    WARNING: API error — {exc}")
        return {"answer": "", "contexts": [""], "processing_time": 0.0}


def collect_samples(api_url: str, dataset: list[dict]) -> list[dict]:
    """Query the API for every item in the dataset and return collected samples."""
    samples = []
    for i, item in enumerate(dataset, 1):
        print(f"  [{i}/{len(dataset)}] {item['question'][:70]}...")
        response = query_api(api_url, item["question"], item["language"])
        samples.append({
            "question": item["question"],
            "answer": response["answer"],
            "contexts": response["contexts"] if response["contexts"] else [""],
            "ground_truth": item["ground_truth"],
            "language": item["language"],
            "category": item.get("category", ""),
            "processing_time": response["processing_time"],
        })
        time.sleep(0.5)  # avoid Bedrock rate limits inside the Lambda
    return samples


def build_ragas_dataset(samples: list[dict]) -> Dataset:
    return Dataset.from_dict({
        "question": [s["question"] for s in samples],
        "answer": [s["answer"] for s in samples],
        "contexts": [s["contexts"] for s in samples],
        "ground_truth": [s["ground_truth"] for s in samples],
    })


def run_ragas(ragas_dataset: Dataset, ragas_llm, ragas_embeddings) -> dict:
    """Run the 4 core RAGAS metrics and return mean scores."""
    metrics = [faithfulness, answer_relevancy, context_recall, context_precision]

    result = evaluate(
        ragas_dataset,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=ragas_embeddings,
    )
    df = result.to_pandas()
    return {
        "faithfulness": round(float(df["faithfulness"].mean()), 4),
        "answer_relevancy": round(float(df["answer_relevancy"].mean()), 4),
        "context_recall": round(float(df["context_recall"].mean()), 4),
        "context_precision": round(float(df["context_precision"].mean()), 4),
        "per_sample": df.to_dict(orient="records"),
    }


def print_comparison(results: dict) -> None:
    os_scores = results["opensearch"]["scores"]
    kb_scores = results["knowledge_base"]["scores"]
    metrics = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]

    print("\n" + "=" * 65)
    print("  RAGAS EVALUATION RESULTS")
    print("=" * 65)
    print(f"  {'Metric':<22} {'OpenSearch':>12} {'KnowledgeBase':>14} {'Winner':>8}")
    print("-" * 65)
    for m in metrics:
        os_val = os_scores.get(m, 0)
        kb_val = kb_scores.get(m, 0)
        winner = "OpenSearch" if os_val >= kb_val else "KnowledgeBase"
        print(f"  {m:<22} {os_val:>12.4f} {kb_val:>14.4f} {winner:>8}")
    print("-" * 65)

    avg_os = sum(os_scores.get(m, 0) for m in metrics) / len(metrics)
    avg_kb = sum(kb_scores.get(m, 0) for m in metrics) / len(metrics)
    overall_winner = "OpenSearch" if avg_os >= avg_kb else "KnowledgeBase"
    print(f"  {'AVERAGE':<22} {avg_os:>12.4f} {avg_kb:>14.4f} {overall_winner:>8}")
    print("=" * 65)

    print(f"\n  Avg processing time (OpenSearch):    {results['opensearch']['avg_processing_time']:.2f}s")
    print(f"  Avg processing time (KnowledgeBase): {results['knowledge_base']['avg_processing_time']:.2f}s")
    print()


def main():
    config = load_config()
    dataset = load_dataset()

    print(f"Loaded {len(dataset)} evaluation samples.")
    print(f"AWS profile: {config.get('aws_profile', 'lazar-private')} | region: {config.get('aws_region', 'us-east-1')}\n")

    # Set up Bedrock as judge LLM for RAGAS
    session = boto3.Session(
        profile_name=config.get("aws_profile", "lazar-private"),
        region_name=config.get("aws_region", "us-east-1"),
    )
    bedrock_client = session.client("bedrock-runtime")

    ragas_llm = LangchainLLMWrapper(
        ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            client=bedrock_client,
        )
    )
    ragas_embeddings = LangchainEmbeddingsWrapper(
        BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v2:0",
            client=bedrock_client,
        )
    )

    stacks = [
        ("opensearch", config["opensearch_api_url"]),
        ("knowledge_base", config["knowledge_base_api_url"]),
    ]

    all_results = {}

    for stack_key, api_url in stacks:
        print(f"\n{'='*60}")
        print(f"  Stack: {stack_key.upper()}")
        print(f"  URL:   {api_url}")
        print(f"{'='*60}")

        samples = collect_samples(api_url, dataset)

        print(f"\n  Running RAGAS evaluation ({len(samples)} samples)...")
        ragas_dataset = build_ragas_dataset(samples)
        scores = run_ragas(ragas_dataset, ragas_llm, ragas_embeddings)

        avg_time = sum(s["processing_time"] for s in samples) / len(samples)
        all_results[stack_key] = {
            "scores": {k: v for k, v in scores.items() if k != "per_sample"},
            "per_sample_scores": scores["per_sample"],
            "raw_samples": samples,
            "avg_processing_time": avg_time,
        }

    print_comparison(all_results)

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"evaluation_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"  Full results saved to: {output_path}\n")


if __name__ == "__main__":
    main()
