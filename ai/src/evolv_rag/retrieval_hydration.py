"""Query vocabulary for drinking water during physical activity."""
import re

from .retrieval import HybridSearch, fold


_ACTIVITY = re.compile(r"\b(?:trein\w*|exercici\w*|academia|corr(?:ida|er|endo)|musculacao|pedal\w*)\b")
_WATER = r"(?:agua|liquidos?)"
_INTAKE = re.compile(
    rf"\b(?:beber|bebo|bebe|beberia|tomar|tomo|toma) (?:mais |menos |muita |pouca )?{_WATER}\b|"
    rf"\b(?:quant[oa]s?|quantidade|qtd|volume|litros?|ml)\b.{{0,38}}\b{_WATER}\b|"
    rf"\b{_WATER}\b.{{0,28}}\b(?:quanto|quantidade|qtd)\b"
)
_COOKING = re.compile(r"\b(?:cozinh\w*|receita|diluir|dissolver)\b")


class HydrationSearch(HybridSearch):
    def lexical(self, text):
        normalized = fold(text)
        if _ACTIVITY.search(normalized) and _INTAKE.search(normalized) and not _COOKING.search(normalized):
            text += "\nhidratação líquido suor"
        return super().lexical(text)
