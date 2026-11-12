"""Regression tests for integrity failures and preservation of human score files."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dialectollm import analysis
from dialectollm import indicadores_objetivos as indicators

ROOT = Path(__file__).resolve().parents[2]


def dump_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def dump_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


class IncrementalAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'runs', prefix='regresion-analisis-')
        self.run = Path(self.temp.name)
        (self.run / 'inputs').mkdir()
        self.out = self.run / 'analisis'
        self.models = [{'alias': name, 'requested_model_id': 'api-' + name,
                        'input_usd_per_million': 1, 'output_usd_per_million': 2}
                       for name in ('a', 'b')]
        bank = [{'item_id': item, 'category': 'calculo', 'answer_key': answer,
                 **{'prompt_' + dialect: f'Pregunta {item} {dialect}' for dialect in ('co', 'mx', 'rio', 'std')}}
                for item, answer in [('I001', '36 minutos'), ('I002', '15 litros')]]
        config = {'control_dialect': 'std'}
        dump_json(self.run / 'inputs/item_bank.json', bank)
        dump_json(self.run / 'inputs/study_config.json', config)
        self.schedule, self.records = [], []
        for item in bank:
            for dialect in ('co', 'mx', 'rio', 'std'):
                prompt = item['prompt_' + dialect]
                for repetition in range(1, 4):
                    for model in self.models:
                        alias = model['alias']
                        row = {'item_id': item['item_id'], 'dialect': dialect, 'replicate': repetition,
                               'model_alias': alias, 'model_id': model['requested_model_id'],
                               'call_key': f"{item['item_id']}:{dialect}:{alias}:r{repetition}",
                               'pair_id': f"{item['item_id']}:{dialect}:r{repetition}", 'prompt': prompt,
                               'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
                        self.schedule.append(row)
                        self.records.append({**row, 'requested_model_id': row['model_id'], 'returned_model_id': row['model_id'],
                            'response_id': 'response-' + row['call_key'], 'status': 'completed', 'api_status': 'completed',
                            'output_text': item['answer_key'], 'latency_ms': 100, 'estimated_cost_usd': 0.00005,
                            'usage': {'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30,
                                      'output_tokens_details': {'reasoning_tokens': 5}}})
        dump_jsonl(self.run / 'schedule.jsonl', self.schedule)
        manifest = {'items': ['I001', 'I002'], 'dialects': ['co', 'mx', 'rio', 'std'],
                    'models': self.models, 'repetitions': 3, 'analysis_eligible': False,
                    'input_hashes': {label + '_sha256': analysis.sha(self.run / name)
                        for label, name in [('config', 'inputs/study_config.json'), ('bank', 'inputs/item_bank.json'), ('schedule', 'schedule.jsonl')]}}
        dump_json(self.run / 'manifest.json', manifest)
        self.save(self.records[:24])

    def tearDown(self):
        self.temp.cleanup()

    def save(self, rows):
        dump_jsonl(self.run / 'responses.jsonl', rows)

    def execute(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return analysis.main(self.run)

    def score_path(self, slot=1):
        return self.out / f'evaluador_{slot}_calificaciones.csv'

    def test_updates_preserve_scores_and_extra_columns(self):
        self.assertEqual(self.execute(), 0)
        codes = analysis.readj(self.out / 'clave_privada.json')
        path = self.score_path()
        rows = analysis.csvread(path)
        rows[0].update(rater_id=' R1 ', score=' 4 ', nota_adicional='Conservar')
        analysis.csvwrite(path, analysis.RATING_FIELDS + ['nota_adicional'], rows)
        self.save(self.records)
        self.assertEqual(self.execute(), 0)
        result = analysis.csvread(path)
        self.assertEqual(result[0]['score'], ' 4 ')
        self.assertEqual(result[0]['nota_adicional'], 'Conservar')
        self.assertEqual(len(result), 48 * 3)
        valid = analysis.csvread(self.out / 'calificaciones_validadas_PRIVADAS.csv')
        self.assertEqual(valid[0]['score'], '4')
        self.assertEqual(valid[0]['rater_id'], 'R1')
        self.assertTrue(all(analysis.readj(self.out / 'clave_privada.json')[key] == code for key, code in codes.items()))
        before = path.read_bytes()
        self.assertEqual(self.execute(), 0)
        self.assertEqual(path.read_bytes(), before)

    def test_pending_rows_can_already_identify_the_rater(self):
        self.execute()
        rows = analysis.csvread(self.score_path())
        for row in rows:
            row['rater_id'] = 'R1'
        analysis.csvwrite(self.score_path(), analysis.RATING_FIELDS, rows)
        self.assertEqual(self.execute(), 0)
        self.assertEqual(analysis.readj(self.out / 'resumen.json')['calificaciones_validas'], 0)

    def test_invalid_header_does_not_overwrite_human_file(self):
        self.execute()
        self.score_path().write_text('codigo,score\nkeep,4\n', encoding='utf-8')
        before = self.score_path().read_bytes()
        self.save(self.records)
        self.assertEqual(self.execute(), 1)
        self.assertEqual(before, self.score_path().read_bytes())
        self.assertEqual(analysis.csvread(self.out / 'calificaciones_validadas_PRIVADAS.csv'), [])

    def test_blank_unknown_and_duplicate_rows_are_rejected(self):
        self.execute()
        rows = analysis.csvread(self.score_path())
        rows.append(dict(rows[0]))
        rows.append(dict(rows[0], codigo='unknown'))
        analysis.csvwrite(self.score_path(), analysis.RATING_FIELDS, rows)
        self.assertEqual(self.execute(), 1)
        self.assertEqual(len(analysis.csvread(self.out / 'errores_calificaciones.csv')), 2)

    def test_duplicate_ids_fail_before_blind_export(self):
        self.records[1]['response_id'] = self.records[0]['response_id']
        self.save(self.records[:24])
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.score_path().exists())
        with self.assertRaises(ValueError):
            indicators.analizar(self.run)
        self.assertEqual(analysis.readj(self.out / 'indicadores_objetivos.json')['estado_validacion'], 'error')

    def test_fractional_tokens_are_not_silently_truncated(self):
        self.records[0]['usage']['input_tokens'] = 10.5
        self.save(self.records[:24])
        self.assertEqual(self.execute(), 1)
        self.assertFalse((self.out / 'clave_privada.json').exists())

    def test_no_evaluable_is_not_counted_as_score(self):
        self.execute()
        rows = analysis.csvread(self.score_path())
        rows[0].update(rater_id='R1', no_evaluable='si', justificacion='Fuera de alcance')
        analysis.csvwrite(self.score_path(), analysis.RATING_FIELDS, rows)
        self.assertEqual(self.execute(), 0)
        summary = analysis.readj(self.out / 'resumen.json')
        self.assertEqual(summary['calificaciones_validas'], 0)
        self.assertEqual(summary['decisiones_no_evaluables'], 1)

    def test_shared_rater_identity_invalidates_comparison(self):
        self.execute()
        for slot in (1, 2):
            path = self.score_path(slot)
            rows = analysis.csvread(path)
            rows[0].update(rater_id='R1', score='4')
            analysis.csvwrite(path, analysis.RATING_FIELDS, rows)
        self.assertEqual(self.execute(), 1)
        self.assertEqual(analysis.csvread(self.out / 'calificaciones_pares_exploratorios.csv'), [])

    def test_incomplete_snapshot_has_empty_item_analysis(self):
        self.save(self.records[:1])
        result = indicators.analizar(self.run)
        self.assertEqual(result['pareado']['items'], 0)
        self.assertEqual(result['items_con_respuestas_incompletos'], ['I001'])
        self.assertEqual(analysis.csvread(self.out / 'indicadores_pares.csv'), [])

    def test_lock_and_atomic_update_protect_existing_artifact(self):
        self.out.mkdir()
        with analysis.analysis_lock(self.out):
            with self.assertRaises(RuntimeError):
                self.execute()
        path = self.out / 'human.csv'
        path.write_bytes(b'human edit')
        with self.assertRaises(RuntimeError):
            analysis.atomic_write(path, b'new rows', expected=b'old snapshot')
        self.assertEqual(path.read_bytes(), b'human edit')
        with patch('dialectollm.analysis.os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                analysis.atomic_write(path, b'new rows')
        self.assertEqual(path.read_bytes(), b'human edit')

    def test_indicator_results_are_repeatable_and_sources_unchanged(self):
        inputs = [self.run / name for name in ('manifest.json', 'responses.jsonl', 'schedule.jsonl', 'inputs/item_bank.json', 'inputs/study_config.json')]
        before = {path: path.read_bytes() for path in inputs}
        result = indicators.analizar(self.run)
        self.assertEqual(result['pareado']['pares'], 12)
        self.assertEqual(result['marcadores']['ambos_presentes'], 12)
        outputs = {path: path.read_bytes() for path in self.out.glob('indicadores*')}
        self.assertEqual(result, indicators.analizar(self.run))
        self.assertEqual(outputs, {path: path.read_bytes() for path in outputs})
        self.assertEqual(before, {path: path.read_bytes() for path in inputs})


if __name__ == '__main__':
    unittest.main()
