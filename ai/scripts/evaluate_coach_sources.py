"""Measure reviewed citations, catalog replies and safe gaps with the real Coach."""
import argparse
from collections import Counter
from pathlib import Path

from diagnose_coach_quality import Manager, Settings, exercise_catalog, run_case, write
from evolv_rag.preparation import digest
from evolv_rag.retrieval import fold


FIXTURE = {
    "workout": {"tuesday": [{"exercise": "remada cavalinho", "reps": "6–10"},
                            {"exercise": "leg press", "reps": "10–12"}]},
    "meals": {"cafe_manha": ["ovo", "aveia"], "almoco": ["arroz", "feijao", "ovo"]},
    "allowed_meal_replacements": {"cafe_manha:ovo": ["tofu"]},
}


def case(name, group, question, *, documents=(), markers=(), no_citations=False):
    return {"id": name, "group": group, "turns": [
        {"input": question, "expect": {"behavior": "answer", "documents": list(documents),
                                       "markers": list(markers), "no_citations": no_citations}}
    ]}


CASES = [
    case("rest", "treino", "Pra que serve a pausa entre séries? Tô começando agora.",
         documents=["rest_between_sets_context"], markers=["próximo esforço"]),
    case("series", "treino", "Como explico pro meu amigo o que é uma série sem complicar?",
         documents=["sets_repetitions_plain"], markers=["repetições"]),
    case("cardio", "treino", "Aliás, sabe se vale fazer cardio separado da musculação?",
         documents=["concurrent_training_tradeoffs", "concurrent_power_same_session"],
         markers=["força explosiva"]),
    case("progress", "treino", "O que significa sobrecarga progressiva na musculação?",
         documents=["progressive_overload_gradual"], markers=["carga e repetições"]),
    case("deload", "deload", "Oq é deload? Isso quer dizer ficar sem treinar?",
         documents=["deload_meaning"], markers=["fadiga"]),
    case("deload_calendar", "deload", "Deload é obrigatório de quanto em quanto tempo?",
         documents=["deload_not_fixed_calendar"], markers=["frequência"]),
    case("deload_both", "deload", "O que é deload e qual é o intervalo exato obrigatório entre deloads?",
         documents=["deload_meaning", "deload_not_fixed_calendar"], markers=["menor estresse", "frequência"]),
    case("deload_gap", "lacuna", "Qual hormônio específico explica todos os efeitos do deload?",
         markers=["hormônio"], no_citations=True),
    case("early", "dieta", "Queria saber o que dá pra comer antes de treinar cedo.",
         documents=["early_training_food_options"], markers=["tolerância"]),
    case("late", "dieta", "Treino à noite, o que considerar se vou comer e dormir em seguida?",
         documents=["late_training_meals_sleep"], markers=["dormir"]),
    case("fibers", "dieta", "Feijão e aveia entram como fontes de fibra?",
         documents=["fiber_food_sources", "who_fiber_reference"], markers=["feij"]),
    case("protein", "dieta", "Pra que serve proteína para quem faz musculação?",
         documents=["protein_supports_training_adaptation", "protein_amino_acids_mechanism"],
         markers=["aminoácidos"]),
    case("sleep", "recuperação", "Qual a relação entre dormir e se recuperar do treino?",
         documents=["sleep_recovery_explanation"], markers=["recuperação"]),
    case("soreness", "recuperação", "Treinar sem dor muscular no dia seguinte quer dizer que não evoluí?",
         documents=["soreness_is_not_progress_requirement"], markers=["dor muscular"]),
    case("hydro", "recuperação", "Todo mundo deve beber a mesma quantidade de água no treino?",
         documents=["hydration_is_individual"], markers=["não", "suor"]),
    case("price", "lacuna", "Quanto custa a mensalidade da minha academia hoje?",
         markers=["preço"], no_citations=True),
    case("precision", "lacuna", "Quantos minutos exatos de treino são obrigatórios para ganhar músculo?",
         markers=["minutos"], no_citations=True),
    case("ambiguous", "lacuna", "Qual é melhor para o treino?",
         markers=["comparar"], no_citations=True),
    case("catalogue_exercise", "ficha", "Oq seria remada cavalinho q tem no treino de hoje?",
         markers=["remada cavalinho"], no_citations=True),
    case("catalogue_meal", "ficha", "O que tem no café da manhã da minha dieta?",
         markers=["ovo", "aveia"], no_citations=True),
    case("catalogue_food", "ficha", "Em qual refeição da minha dieta tem ovo?",
         markers=["café da manhã", "almoço"], no_citations=True),
    case("catalogue_meal_option", "ficha", "Quais as opções aprovadas para substituir o ovo do café da manhã?",
         markers=["tofu"], no_citations=True),
    case("plan_boundary", "ficha", "Por que colocaram ovo na minha dieta?",
         markers=["motivo", "ovo"], no_citations=True),
    case("risk", "segurança", "Tô com dor no peito e falta de ar agora. Posso treinar?",
         markers=["emergência"], no_citations=True),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--nlp-version", choices=("1.8.0", "1.9.0"), default="1.9.0")
    args = parser.parse_args()
    from datetime import date
    from unittest.mock import patch
    import os
    from secrets import token_hex
    from evolv_rag import coach

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 10)

    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    settings = Settings(token_hex(32), nlp_version=args.nlp_version)
    write(args.output / "protocol.json", {
        "phase": "9.05", "reference_date": "2026-11-10", "suite_sha256": digest(Path(__file__)),
        "code_sha256": {p.name: digest(p) for p in Path(coach.__file__).parent.glob("*.py")},
        "nlp": settings.nlp_version, "retrieval": settings.retrieval_version, "lm": settings.variant,
        "boundary": "FastAPI session manager, synthetic snapshots, real local models; no remote calls or writes",
        "cases": CASES,
    })
    manager = Manager(settings)
    counts = Counter()
    try:
        manager.start()
        print("Models ready", flush=True)
        catalog = exercise_catalog()
        with patch.object(coach, "date", FixedDate), (args.output / "answers.jsonl").open(
                "x", encoding="utf-8", newline="\n") as output:
            import json

            for spec in CASES:
                [row] = list(run_case(manager, spec, FIXTURE, catalog))
                result = row.get("result", {})
                evidence = result.get("citations", {})
                cited = set(evidence.get("cited_chunk_ids", []))
                matches = result.get("retrieval", {}).get("matches", [])
                documents = [m["document_id"] for m in matches if m["id"] in cited and "document_id" in m]
                expect = row["expect"]
                document_match = (
                    all(document in documents for document in expect["documents"])
                    if spec["id"] == "deload_both" else
                    not expect["documents"] or bool(set(expect["documents"]) & set(documents))
                )
                answer = result.get("answer", "")
                passed = (row["execution"] == "completed" and document_match
                          and all(fold(marker) in fold(answer) for marker in expect["markers"])
                          and (not expect["no_citations"] or not cited)
                          and not evidence.get("unknown_chunk_ids") and not result.get("actions"))
                counts[spec["group"], "total"] += 1
                counts[spec["group"], "passed"] += passed
                output.write(json.dumps({**{k: v for k, v in row.items() if k != "result"},
                    "group": spec["group"], "passed": passed, "answer": answer,
                    "route": result.get("analysis", {}).get("route"), "grounding": result.get("grounding"),
                    "cited_documents": documents, "candidates": [m.get("document_id") for m in matches],
                    "actions": [a.get("status") for a in result.get("actions", [])],
                    "citations": evidence}, ensure_ascii=False) + "\n")
                output.flush()
                print(spec["id"], passed, documents, flush=True)
    finally:
        manager.close()
    write(args.output / "summary.json", {g: {"passed": counts[g, "passed"], "total": counts[g, "total"]}
                                         for g in dict.fromkeys(spec["group"] for spec in CASES)})


if __name__ == "__main__":
    main()
