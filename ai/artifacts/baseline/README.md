# Baseline artifacts

Cada subpasta representa uma versao reproduzivel do baseline NLP. Os modelos
`joblib` usam serializacao baseada em pickle: carregue apenas artefatos gerados
por este repositorio e cujo SHA-256 corresponda ao `manifest.json`.

Os binarios dependem das versoes Python e scikit-learn registradas no
manifesto. O comando oficial de reconstrucao e:

```powershell
python ai/scripts/train_baseline.py
```
