"""Local hybrid retrieval with bounded user-only context. No query persistence."""
from datetime import date
import re
import unicodedata
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from .search import Search

STOP = set("a o as os um uma uns umas de do da dos das e em no na nos nas para por com ao aos que qual quais como quando onde porque pq pra pro eu meu minha meus minhas voce vc seu sua seus suas ele ela isso esse essa esses essas isto aquele aquela se me mim nos ja muito mais ser estar ter fazer tem tenho pode posso sao eh faz foi ta vou sobre so tambem ou entao mesmo mesma cada daqui ai aqui la quanto quanta quantas quantos daquilo disso desse dessa pelo pela pelos pelas".split())


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", fold(text)) if len(t) > 1 and t not in STOP]


def dependent(text):
    text = fold(text).strip()
    return bool(re.match(r"^(?:e\b|mas\b|nesse\b|nessa\b|entao\b|isso\b|e se\b)", text)
                or re.search(r"\b(?:nesse caso|nessa situacao|isso ai|o mesmo|a mesma|desses|dessas)\b", text))


def explicit_switch(text):
    return bool(re.search(r"\b(?:mudando de assunto|outra duvida|outro assunto|agora sobre|agora quero saber)\b", fold(text)))


class HybridSearch(Search):
    def __init__(self, directory, encoder, config):
        super().__init__(directory, encoder)
        self.config = dict(config)
        for key in ("lexical_weight", "context_weight", "min_score"):
            if not 0 <= self.config[key] <= 1:
                raise ValueError("Invalid retrieval weight/threshold")
        texts = [r["embedding_text"] for r in self.rows]
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode", lowercase=True)
        self.char_matrix = self.char.fit_transform(texts)
        vocab = sorted({t for text in texts for t in tokens(text)})
        self.vocab = {t: i for i, t in enumerate(vocab)}
        self.counts = np.zeros((len(texts), len(vocab)), dtype=np.float32)
        for i, text in enumerate(texts):
            for t in tokens(text):
                self.counts[i, self.vocab[t]] += 1
        self.lengths = self.counts.sum(axis=1)
        self.mean_length = max(float(self.lengths.mean()), 1)
        df = (self.counts > 0).sum(axis=0)
        self.idf = np.log(1 + (len(texts) - df + .5) / (df + .5))

    def lexical(self, text):
        words = sorted({self.vocab[t] for t in tokens(text) if t in self.vocab})
        bm = np.zeros(len(self.rows), dtype=np.float32)
        if words:
            count = self.counts[:, words]
            denom = count + 1.2 * (1 - .75 + .75 * self.lengths[:, None] / self.mean_length)
            bm = (self.idf[words] * count * 2.2 / denom).sum(axis=1)
        chars = (self.char_matrix @ self.char.transform([text]).T).toarray().ravel()
        return .5 * (bm / (bm + 3)) + .5 * chars

    def query(self, text, **kwargs):
        return self.query_conversation(text, [], **kwargs)

    def query_conversation(self, text, history, *, k=3, min_score=None, as_of=None, domain=None, topics=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise ValueError("Query must be nonempty and at most 20000 characters")
        threshold = self.config["min_score"] if min_score is None else min_score
        if not 1 <= k <= 3 or not 0 <= threshold <= 1:
            raise ValueError("Invalid retrieval limits")
        if not isinstance(history, list) or len(history) > 16:
            raise ValueError("History must be a bounded list")
        today = (as_of or date.today()).isoformat()
        candidates = [i for i, r in enumerate(self.rows)
            if r["reviewed_at"] <= today < r["effective_review_due_at"]
            and all(s["status"] == "approved" and s["last_verified_at"] <= today < s["review_due_at"] for s in r["citations"])
            and (domain is None or r["domain"] == domain)
            and (not topics or set(topics) & set(r["topic_ids"]))]
        context_info = {"used": False, "user_turns_used": 0, "reason": "standalone"}
        empty = lambda reason: {"status": "no_evidence", "matches": [], "score_is_probability": False,
                                "context": {**context_info, "reason": reason}, "method": "hybrid"}
        if not candidates:
            return empty("no_eligible_documents")
        prior = [m["content"] for m in history if isinstance(m, dict) and m.get("role") == "user"
                 and isinstance(m.get("content"), str) and m["content"].strip()]
        is_dependent = dependent(text) and not explicit_switch(text)
        if is_dependent and not prior and len(tokens(text)) < 3:
            return empty("missing_context")
        current = self.encoder.encode([text])[0]
        semantic = self.vectors @ current
        lexical = self.lexical(text)
        # A question that carries no subject still needs clarification, even with history.
        if is_dependent and not tokens(text):
            return empty("insufficient_subject")
        if is_dependent and prior and self.config["context_weight"]:
            # Only the most recent user message; assistant statements never become retrieval facts.
            previous = prior[-1][-8000:]
            # Current content must have some support; prior context cannot turn a foreign topic into evidence.
            if float(semantic[candidates].max()) < .30 and float(lexical[candidates].max()) < .12:
                return empty("current_message_unsupported")
            previous_vector = self.encoder.encode([previous])[0]
            previous_scores = self.vectors @ previous_vector
            current_top = candidates[int(np.argmax(semantic[candidates]))]
            previous_top = candidates[int(np.argmax(previous_scores[candidates]))]
            independently_clear = (len(tokens(text)) >= 3 and float(semantic[current_top]) >= .62
                                   and float(self.vectors[current_top] @ self.vectors[previous_top]) < .45)
            if independently_clear:
                context_info["reason"] = "independent_new_subject"
            else:
                combined = previous + "\n" + text
                combined_vector = self.encoder.encode([combined])[0]
                weight = self.config["context_weight"]
                semantic = (1 - weight) * semantic + weight * (self.vectors @ combined_vector)
                lexical = (1 - weight) * lexical + weight * self.lexical(combined)
                context_info.update(used=True, user_turns_used=1, reason="dependent_user_followup")
        elif explicit_switch(text):
            context_info["reason"] = "explicit_subject_switch"
        weight = self.config["lexical_weight"]
        scores = (1 - weight) * semantic + weight * lexical
        ordered = sorted(candidates, key=lambda i: (-float(scores[i]), self.rows[i]["id"]))
        chosen = []
        for i in ordered:
            if scores[i] < threshold:
                break
            # Diversify highly redundant snippets without removing the best result.
            if any(float(self.vectors[i] @ self.vectors[j]) > .94 for j in chosen):
                continue
            chosen.append(i)
            if len(chosen) == k:
                break
        return {"status": "found" if chosen else "no_evidence", "matches": [
            {**self.rows[i], "score": float(scores[i]), "semantic_score": float(semantic[i]),
             "lexical_score": float(lexical[i])} for i in chosen],
            "score_is_probability": False, "context": context_info, "method": "hybrid",
            "threshold": threshold}
