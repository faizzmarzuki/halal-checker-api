"""Manual end-to-end demo of the classification engine."""
from halal_scanner.classifier import HalalClassifier
from halal_scanner.gemma import GemmaClient
from halal_scanner.rulebook import Rulebook


def main():
    engine = HalalClassifier(Rulebook.load_default(), gemma_client=GemmaClient())
    sample = ["sugar", "gelatin", "gelatin (fish)", "pork gelatin", "e471", "carmine"]
    verdict = engine.classify(sample)
    print(verdict.summary)
    for r in verdict.ingredients:
        print(f"  - {r.input:25} -> {r.status.value:8} [{r.source.value}/{r.confidence.value}] {r.reason}")
    print("\n" + verdict.disclaimer)


if __name__ == "__main__":
    main()
