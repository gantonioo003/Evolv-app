"""Small authored development check, not independent user evaluation."""
from datetime import date
import json
from pathlib import Path
import sys
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.search import Encoder, Search
from evolv_rag.preparation import write, digest

CASES = [
("Quanto tempo um adulto deve dormir?", "sleep_duration_adults"),
("Preciso falhar em toda série para crescer?", "training_to_failure_optional"),
("Posso trocar a máquina por pesos livres?", "training_equipment_flexibility"),
("Perdi o treino ontem, faço o dobro hoje?", "missed_workout_no_compensation"),
("O joelho começou a doer no exercício. Você sabe a causa?", "training_pain_boundary"),
("Como progredir a carga aos poucos?", "progressive_overload_gradual"),
("A creatina ajuda no desempenho?", "creatine_evidence_general"),
("Qual quantidade de proteína para adultos ativos?", "protein_range_active_adults"),
("O que comer antes de treinar?", "pre_workout_meal_context"),
("Como comer depois do treino?", "post_workout_meal_context"),
("Preciso beber a mesma quantidade de água que todo mundo?", "hydration_is_individual"),
("Uma refeição ruim estraga a alimentação inteira?", "food_pattern_over_single_meal"),
("Preciso compensar o que comi com jejum e exercício?", "flexible_meal_without_compensation"),
("Meu relógio sabe exatamente como eu dormi?", "sleep_tracker_is_estimate"),
("Não sentir dor depois significa que o treino não funcionou?", "soreness_is_not_progress_requirement"),
("Dia de descanso faz parte do plano?", "rest_day_is_part_of_plan"),
("Sinto dor no peito, posso continuar treinando?", "chest_pain_emergency"),
("Sou alérgico a amendoim, posso comer mesmo assim?", "food_allergy_and_anaphylaxis_boundary"),
("Perguntar sobre um exercício muda meu plano automaticamente?", "question_is_not_action"),
("O Coach pode gravar mudanças direto no banco de dados?", "coach_does_not_write_database"),
("Qual a cotação do dólar agora?", None),
("Quem ganhou o Oscar ontem?", None),
("Escreva código SQL para invadir um servidor.", None),
("Qual é o saldo da minha conta bancária?", None),
("Qual ônibus vai para o aeroporto?", None),
]

def main():
    output = AI_ROOT / "artifacts/rag_evaluation/1.0.0"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    protocol = {"purpose": "authored development set, not held-out independent test",
                "as_of": "2026-11-02", "k": 3, "min_score": 0.45,
                "threshold_calibrated": False,
                "cases": [{"query": q, "expected_document_id": d} for q, d in CASES]}
    write(output / "protocol.json", protocol)
    encoder = Encoder(AI_ROOT / "artifacts/encoders/multilingual-minilm")
    search = Search(AI_ROOT / "artifacts/rag/1.0.0", encoder)
    results = []
    for query, expected in CASES:
        result = search.query(query, as_of=date(2026, 11, 2))
        ids = [m["document_id"] for m in result["matches"]]
        rank = ids.index(expected) + 1 if expected in ids else None
        results.append({"query": query, "expected": expected, "rank": rank,
                        "status": result["status"], "retrieved": [
                            {"document_id": m["document_id"], "score": m["score"]} for m in result["matches"]]})
    positive = [x for x in results if x["expected"]]
    negative = [x for x in results if not x["expected"]]
    metrics = {"positive_queries": len(positive), "out_of_scope_queries": len(negative),
               "hit_at_1": sum(x["rank"] == 1 for x in positive) / len(positive),
               "hit_at_3": sum(x["rank"] is not None for x in positive) / len(positive),
               "mrr_at_3": sum(1/x["rank"] if x["rank"] else 0 for x in positive) / len(positive),
               "out_of_scope_rejections": sum(x["status"] == "no_evidence" for x in negative),
               "scope": "small synthetic development check; scores are not probabilities"}
    write(output / "results.json", {"metrics": metrics, "cases": results})
    write(output / "manifest.json", {"index_manifest_sha256": digest(AI_ROOT / "artifacts/rag/1.0.0/manifest.json"),
        "code": {name: digest(AI_ROOT / name) for name in ["src/evolv_rag/search.py", "scripts/evaluate_rag_search.py"]},
        "outputs": {name: digest(output / name) for name in ["protocol.json", "results.json"]}})
    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
