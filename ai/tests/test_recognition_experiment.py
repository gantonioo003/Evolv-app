import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_nlp.recognition_experiment import RecognitionFeatures, intent_strata, selective, scores
from evolv_nlp.recognition_pipeline import RecognitionPipeline


class RecognitionExperimentTests(unittest.TestCase):
    def test_validation_terms_do_not_enter_fitted_vocabulary(self):
        train=[{"text":"trocar refeição", "context":"plano atual", "input":"trocar refeição no plano atual"},
               {"text":"explicar treino", "context":"pergunta anterior", "input":"explicar treino e contexto"}]
        feat=RecognitionFeatures().fit(train)
        before=dict(feat.message.transformer_list[0][1].vocabulary_)
        val=[{"text":"termoexclusivovalidação", "context":"novoconteexto", "input":"termoexclusivovalidação"}]
        views=feat.transform(val,np.zeros((1,384),dtype=np.float32))
        self.assertEqual(before,feat.message.transformer_list[0][1].vocabulary_)
        self.assertNotIn("termoexclusivovalidacao",before)
        self.assertEqual(1,views["hybrid"].shape[0])
        self.assertEqual(views["focus"].shape[1]+384,views["hybrid"].shape[1])

    def test_strata_do_not_hide_synthetic_errors_in_combined_average(self):
        rows=[{"label":"a"},{"label":"a"},{"label":"b"}]
        values=np.asarray([[.9,.1],[.8,.2],[.7,.3]])
        metrics=intent_strata(values,rows,["a","b"],2)
        self.assertEqual(1.,metrics["legacy"]["accuracy"])
        self.assertEqual(0.,metrics["actions_synthetic"]["accuracy"])
        self.assertAlmostEqual(2/3,metrics["combined"]["accuracy"])

    def test_high_margin_does_not_override_missing_validation_support(self):
        values=np.asarray([[.99,.01],[.01,.99]])
        rows=[{"label":"a"},{"label":"b"}]
        policy={"margin_threshold":.1,"validation_label_support":{"a":5,"b":0},"minimum_label_validation_support":5}
        result=selective(values,rows,["a","b"],policy,1)
        self.assertEqual(1,result["legacy"]["accepted"])
        self.assertEqual(0,result["actions_synthetic"]["accepted"])
        self.assertIsNone(result["actions_synthetic"]["accepted_accuracy"])

    def test_scores_are_normalized_without_calling_them_calibrated_probabilities(self):
        class Model:
            def decision_function(self,X):return np.asarray([[3.,1.,-2.]])
        result=scores(Model(),np.zeros((1,1)))
        self.assertAlmostEqual(1.,float(result.sum()))
        self.assertEqual(0,int(result.argmax()))

    def test_runtime_rejects_unsafe_or_changed_artifact_before_deserializing(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/"artifacts/baseline/1.9.0";out.mkdir(parents=True)
            (out/"manifest.json").write_text(json.dumps({"private_models":{"../../escape.joblib":"bad"}}))
            with self.assertRaisesRegex(ValueError,"path/checksum"):
                RecognitionPipeline(root)

    def test_runtime_input_validation_precedes_prediction(self):
        pipeline=RecognitionPipeline.__new__(RecognitionPipeline)
        for text,context in [("", ""),("x"*8001,""),("ok","x"*16001),(None,"")]:
            with self.subTest(text_type=type(text)),self.assertRaises(ValueError):
                pipeline.analyze(text,context)


if __name__=="__main__":unittest.main()
