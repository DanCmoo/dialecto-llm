"""Offline audit, stable blinded materials, and partial human-rating validation."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import secrets
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

DIMS = ('precision', 'comprehension', 'relevance')
RATING_FIELDS = ['codigo', 'dimension', 'rater_id', 'score', 'no_evaluable', 'justificacion']
SLOTS = ('evaluador_1', 'evaluador_2')
UNSET = object()


def readj(path):
    return json.loads(path.read_bytes().decode('utf-8-sig'))


def jsonl(path):
    return [json.loads(line) for line in path.read_bytes().decode('utf-8-sig').splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, data, *, expected=UNSET):
    """Replace one artifact after fully writing it, preserving the old file on failure."""
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        current = path.read_bytes() if path.exists() else None
        if expected is not UNSET and current != expected:
            raise RuntimeError(f'{path.name} cambió durante el análisis; vuelva a ejecutar.')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def jsonwrite(path, value, *, expected=UNSET):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'), expected=expected)


def csvwrite(path, fields, rows, *, expected=UNSET):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(path, stream.getvalue().encode('utf-8-sig'), expected=expected)


def csvread(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


@contextmanager
def analysis_lock(out):
    """Serialize both analysis entry points for a run; never acquire API access."""
    lock = out / '.analisis.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError('Ya existe .analisis.lock. Espere al análisis activo. Si fue interrumpido, '
                           'compruebe que terminó antes de retirar ese archivo.') from exc
    try:
        with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def verify_sources(sources):
    for path, content in sources.items():
        if path.read_bytes() != content:
            raise RuntimeError(f'{path.name} cambió durante el análisis; vuelva a ejecutar con una instantánea estable.')


def audit_run(run):
    """Read one snapshot and validate all completed records before they are exported."""
    sources = {}

    def load(name, *, lines=False):
        path = run / name
        content = path.read_bytes()
        sources[path] = content
        text = content.decode('utf-8-sig')
        return [json.loads(line) for line in text.splitlines() if line.strip()] if lines else json.loads(text)

    manifest = load('manifest.json')
    bank = load('inputs/item_bank.json')
    config = load('inputs/study_config.json')
    schedule = load('schedule.jsonl', lines=True)
    records = load('responses.jsonl', lines=True)
    problems = []

    def issue(kind, key, detail):
        problems.append({'tipo': kind, 'clave': str(key), 'detalle': str(detail)})

    for label, name in [('config', 'inputs/study_config.json'), ('bank', 'inputs/item_bank.json'), ('schedule', 'schedule.jsonl')]:
        if hashlib.sha256(sources[run / name]).hexdigest() != manifest['input_hashes'][label + '_sha256']:
            issue('hash_archivo', label, 'No coincide con el manifiesto')
    bank_index = {item['item_id']: item for item in bank}
    if len(bank_index) != len(bank):
        issue('duplicado_banco', 'item_id', 'IDs repetidos')
    models = {model['alias']: model for model in manifest['models']}
    if len(models) != 2 or len(models) != len(manifest['models']):
        issue('modelos', 'manifiesto', 'Se requieren dos alias distintos')
    scheduled, coordinates, pair_models = {}, set(), defaultdict(set)
    for call in schedule:
        key = call['call_key']
        coordinate = (call['item_id'], call['dialect'], call['model_alias'], call['replicate'])
        expected_key = f"{call['item_id']}:{call['dialect']}:{call['model_alias']}:r{call['replicate']}"
        expected_pair = f"{call['item_id']}:{call['dialect']}:r{call['replicate']}"
        if key != expected_key or call['pair_id'] != expected_pair:
            issue('identificador_calendario', key, 'Clave o par incompatibles con las coordenadas')
        if key in scheduled or coordinate in coordinates:
            issue('duplicado_calendario', key, coordinate)
        scheduled[key] = call
        coordinates.add(coordinate)
        pair_models[call['pair_id']].add(call['model_alias'])
        if hashlib.sha256(call['prompt'].encode()).hexdigest() != call['prompt_sha256']:
            issue('hash_prompt_calendario', key, 'No coincide')
        item = bank_index.get(call['item_id'])
        if not item or item.get('prompt_' + call['dialect']) != call['prompt']:
            issue('prompt_banco', key, 'No coincide con el banco congelado')
        model = models.get(call['model_alias'])
        if not model or call['model_id'] != model['requested_model_id']:
            issue('modelo_calendario', key, 'No coincide con el manifiesto')
    expected = {(item, dialect, model, repetition)
                for item in manifest['items'] for dialect in manifest['dialects']
                for model in models for repetition in range(1, manifest['repetitions'] + 1)}
    if coordinates != expected:
        issue('cobertura_calendario', 'global', f'faltan {len(expected - coordinates)}, sobran {len(coordinates - expected)}')
    complete, ids, historical = {}, {}, []
    costs, returned = defaultdict(Counter), Counter()
    for number, record in enumerate(records, 1):
        key = record.get('call_key')
        call = scheduled.get(key)
        if not call:
            issue('clave_no_programada', key, number)
            continue
        for field in ('item_id', 'dialect', 'model_alias', 'replicate', 'pair_id'):
            if record.get(field) != call[field]:
                issue('metadatos', key, field)
        if record.get('requested_model_id') != call['model_id']:
            issue('modelo_solicitado', key, record.get('requested_model_id'))
        status = record.get('status')
        if status != 'completed':
            if status not in ('failed', 'incomplete'):
                issue('estado_registro', key, status)
            historical.append(record)
            continue
        if key in complete:
            issue('duplicado_completado', key, number)
            continue
        complete[key] = record
        response_id = record.get('response_id')
        if not isinstance(response_id, str) or not response_id.strip():
            issue('id_vacio', key, number)
        elif response_id in ids:
            issue('id_duplicado', response_id, f'{ids[response_id]} / {key}')
        else:
            ids[response_id] = key
        if record.get('api_status') != 'completed':
            issue('estado_api', key, record.get('api_status'))
        if not isinstance(record.get('output_text'), str) or not record['output_text'].strip():
            issue('salida_vacia', key, number)
        if record.get('prompt_sha256') != call['prompt_sha256']:
            issue('hash_prompt_respuesta', key, 'No coincide')
        returned_model = record.get('returned_model_id')
        if not isinstance(returned_model, str) or not returned_model.strip():
            issue('modelo_devuelto_vacio', key, number)
        returned[(call['model_alias'], str(returned_model))] += 1
        usage = record.get('usage') or {}
        model = models.get(call['model_alias'])
        try:
            input_tokens, output_tokens, total_tokens = (usage[field] for field in ('input_tokens', 'output_tokens', 'total_tokens'))
            reasoning_tokens = (usage.get('output_tokens_details') or {}).get('reasoning_tokens')
            values = (input_tokens, output_tokens, total_tokens, reasoning_tokens)
            if any(type(value) is not int or value < 0 for value in values):
                raise ValueError('Los conteos de tokens deben ser enteros no negativos, incluido razonamiento')
            if total_tokens != input_tokens + output_tokens or reasoning_tokens > output_tokens:
                raise ValueError('Tokens inconsistentes')
            estimated_cost = record['estimated_cost_usd']
            if isinstance(estimated_cost, bool) or not isinstance(estimated_cost, (int, float)) or not math.isfinite(estimated_cost):
                raise ValueError('Costo inválido')
            cost = (input_tokens * model['input_usd_per_million'] + output_tokens * model['output_usd_per_million']) / 1e6
            if abs(estimated_cost - cost) > 0.000000011:
                issue('costo', key, 'No coincide con tarifas congeladas')
            costs[call['model_alias']].update({'respuestas': 1, 'input_tokens': input_tokens,
                'output_tokens': output_tokens, 'reasoning_tokens': reasoning_tokens,
                'total_tokens': total_tokens, 'costo_usd': cost})
        except (KeyError, TypeError, ValueError) as exc:
            issue('uso', key, exc)
    pilot_info = manifest.get('pilot_reuse') or {}
    if pilot_info:
        pilot_dir = run.parent / pilot_info['source_run_id']
        if not (pilot_dir / 'manifest.json').exists() or not (pilot_dir / 'responses.jsonl').exists():
            issue('piloto_origen', pilot_dir, 'No disponible para auditar procedencia')
        else:
            pilot_manifest_path, pilot_responses_path = pilot_dir / 'manifest.json', pilot_dir / 'responses.jsonl'
            for path in (pilot_manifest_path, pilot_responses_path):
                sources[path] = path.read_bytes()
            pilot_manifest = json.loads(sources[pilot_manifest_path].decode('utf-8-sig'))
            pilot_records = [json.loads(line) for line in sources[pilot_responses_path].decode('utf-8-sig').splitlines() if line.strip()]
            for kind, path in [('manifest', pilot_manifest_path), ('responses', pilot_responses_path)]:
                if hashlib.sha256(sources[path]).hexdigest() != pilot_info.get('source_' + kind + '_sha256'):
                    issue('hash_piloto', kind, 'El origen difiere de la instantánea importada')
            if pilot_manifest.get('generation') != manifest.get('generation'):
                issue('parametros_piloto', 'generacion', 'Difieren')
            pilot_completed = {}
            for record in pilot_records:
                if record.get('status') == 'completed':
                    if record['call_key'] in pilot_completed:
                        issue('duplicado_piloto', record['call_key'], 'Clave completa repetida')
                    pilot_completed[record['call_key']] = record
            imported = [record for record in complete.values() if record.get('reused_from_pilot')]
            if len(imported) != pilot_info.get('imported_completed_calls'):
                issue('conteo_piloto', 'importados', len(imported))
            for record in imported:
                original = pilot_completed.get(record['call_key'])
                for field in ('response_id', 'prompt_sha256', 'requested_model_id', 'returned_model_id', 'output_text', 'usage', 'estimated_cost_usd'):
                    if not original or record.get(field) != original.get(field):
                        issue('procedencia_piloto', record['call_key'], field)
    verify_sources(sources)
    return dict(manifest=manifest, bank=bank_index, config=config, schedule=scheduled, records=records,
                complete=complete, historical=historical, costs=costs, returned=returned,
                pair_models=pair_models, problems=problems, sources=sources,
                response_hash=hashlib.sha256(sources[run / 'responses.jsonl']).hexdigest())


def load_ratings(out, codes):
    """Validate human files before adding rows or publishing normalized rating data."""
    errors, ratings, documents = [], [], {}
    identities = defaultdict(set)
    for slot in SLOTS:
        path = out / (slot + '_calificaciones.csv')
        content = path.read_bytes() if path.exists() else None
        if content is None:
            documents[slot] = (None, RATING_FIELDS, [])
            continue
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''))
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not set(RATING_FIELDS).issubset(headers):
            errors.append({'archivo': slot, 'linea': 1, 'errores': 'Cabeceras faltantes o repetidas'})
            continue
        rows = list(reader)
        documents[slot] = (content, headers, rows)
        seen = set()
        for line_number, raw in enumerate(rows, 2):
            if None in raw or any(raw[field] is None for field in headers):
                errors.append({'archivo': slot, 'linea': line_number, 'errores': 'Número de celdas incompatible con la cabecera'})
                continue
            row = {field: raw[field].strip() for field in RATING_FIELDS}
            code, dimension, identity = row['codigo'], row['dimension'], row['rater_id']
            score, not_evaluable = row['score'], row['no_evaluable'].casefold()
            row['no_evaluable'] = not_evaluable
            row_errors = []
            if code not in codes:
                row_errors.append('codigo desconocido')
            if dimension not in DIMS:
                row_errors.append('dimension desconocida')
            cell = (code, dimension)
            if cell in seen:
                row_errors.append('celda de calificacion duplicada')
            seen.add(cell)
            if identity:
                identities[slot].add(identity)
            if not_evaluable not in ('', 'si', 'sí', 'no'):
                row_errors.append('no_evaluable debe ser si o no')
            has_decision = bool(score) or not_evaluable in ('si', 'sí')
            if has_decision and not identity:
                row_errors.append('falta rater_id')
            if not_evaluable in ('si', 'sí'):
                if score:
                    row_errors.append('no evaluable no admite score')
                if not row['justificacion']:
                    row_errors.append('falta justificacion')
            elif score and score not in ('1', '2', '3', '4', '5'):
                row_errors.append('score debe ser entero 1-5')
            if row_errors:
                errors.append({'archivo': slot, 'linea': line_number, 'errores': '; '.join(row_errors)})
            elif has_decision:
                ratings.append(dict(row, slot=slot))
    for slot, values in identities.items():
        if len(values) > 1:
            errors.append({'archivo': slot, 'linea': '', 'errores': 'Más de un rater_id en un archivo de evaluador'})
    if identities[SLOTS[0]] & identities[SLOTS[1]]:
        errors.append({'archivo': 'ambos', 'linea': '', 'errores': 'Los dos evaluadores deben tener identidades distintas'})
    return documents, ratings, errors


def export_analysis(run, out):
    audit = audit_run(run)
    manifest, complete = audit['manifest'], audit['complete']
    response_hash = audit['response_hash']
    problems = audit['problems']
    csvwrite(out / 'incidencias.csv', ['tipo', 'clave', 'detalle'], problems)
    if problems:
        jsonwrite(out / 'resumen.json', {'estado_validacion': 'error', 'incidencias': len(problems),
                  'sha256_respuestas_leidas': response_hash, 'analisis_actualizado': False})
        print('ATENCION: auditoría fallida. Revise incidencias.csv; las tablas anteriores pertenecen a su corte previo.', file=sys.stderr)
        return 1
    models = [model['alias'] for model in manifest['models']]
    counts = Counter((row['item_id'], row['dialect'], row['model_alias']) for row in complete.values())
    historical = [{'clave': row['call_key'], 'estado': row['status'], 'hora': row.get('attempted_at_utc'),
                   'resolucion': 'resuelto' if row['call_key'] in complete else 'pendiente', 'error': row.get('error', '')}
                  for row in audit['historical']]
    coverage = [{'item_id': item, 'dialect': dialect, 'model_alias': model,
                 'completadas': counts[item, dialect, model], 'esperadas': manifest['repetitions']}
                for item in manifest['items'] for dialect in manifest['dialects'] for model in models]
    pairs = defaultdict(dict)
    for row in complete.values():
        pairs[row['pair_id']][row['model_alias']] = row
    paired, incomplete = [], []
    for pair_id in sorted(audit['pair_models']):
        pair = pairs[pair_id]
        if set(pair) == set(models):
            a, b = (pair[model] for model in models)
            paired.append({'pair_id': pair_id, 'item_id': a['item_id'], 'dialect': a['dialect'], 'replicate': a['replicate'],
                'tokens_salida_a': a['usage']['output_tokens'], 'tokens_salida_b': b['usage']['output_tokens'],
                'diferencia_tokens_b_menos_a': b['usage']['output_tokens'] - a['usage']['output_tokens'],
                'caracteres_a': len(a['output_text']), 'caracteres_b': len(b['output_text']),
                'diferencia_caracteres_b_menos_a': len(b['output_text']) - len(a['output_text'])})
        else:
            incomplete.append({'pair_id': pair_id, 'modelos_completados': len(pair),
                               'estado': 'incompleto' if pair else 'sin_respuestas'})
    keypath = out / 'clave_privada.json'
    key_before = keypath.read_bytes() if keypath.exists() else None
    key = json.loads(key_before.decode('utf-8-sig')) if key_before is not None else {}
    if not isinstance(key, dict) or any(not isinstance(value, str) or not value for value in key.values()) or len(set(key.values())) != len(key):
        raise ValueError('La clave privada debe contener códigos únicos y no vacíos. Restaure su copia original.')
    for call_key in sorted(complete):
        if call_key not in key:
            code = secrets.token_hex(8)
            while code in key.values():
                code = secrets.token_hex(8)
            key[call_key] = code
    codes = {key[call_key] for call_key in complete}
    documents, ratings, errors = load_ratings(out, codes)
    mapping = {key[call_key]: {'codigo': key[call_key], 'call_key': call_key, 'response_id': row['response_id'],
               'item_id': row['item_id'], 'dialect': row['dialect'], 'model_alias': row['model_alias'], 'replicate': row['replicate']}
               for call_key, row in complete.items()}
    packet = sorted([{'codigo': key[call_key], 'consulta': audit['schedule'][call_key]['prompt'],
                       'respuesta': row['output_text'], 'criterios_referencia': audit['bank'][row['item_id']]['answer_key']}
                      for call_key, row in complete.items()], key=lambda row: row['codigo'])
    verify_sources(audit['sources'])
    for slot, (content, _, _) in documents.items():
        path = out / (slot + '_calificaciones.csv')
        if (path.read_bytes() if path.exists() else None) != content:
            raise RuntimeError(f'{path.name} cambió durante la lectura; vuelva a ejecutar.')
    # Publish the key before templates so an interrupted update can reuse its assignments.
    if not errors:
        if key_before is None or json.loads(key_before.decode('utf-8-sig')) != key:
            jsonwrite(keypath, key, expected=key_before)
        for slot in SLOTS:
            before, headers, rows = documents[slot]
            existing = {(row['codigo'].strip(), row['dimension'].strip()) for row in rows}
            new_rows = [{'codigo': row['codigo'], 'dimension': dimension, 'rater_id': '', 'score': '',
                         'no_evaluable': '', 'justificacion': ''}
                        for row in packet for dimension in DIMS if (row['codigo'], dimension) not in existing]
            if new_rows or before is None:
                csvwrite(out / (slot + '_calificaciones.csv'), headers, rows + new_rows, expected=before)
            csvwrite(out / (slot + '_material.csv'), ['codigo', 'consulta', 'respuesta', 'criterios_referencia'], packet)
        csvwrite(out / 'clave_correspondencia_PRIVADA.csv', ['codigo', 'call_key', 'response_id', 'item_id', 'dialect', 'model_alias', 'replicate'], mapping.values())
    valid = [] if errors else ratings
    grouped = defaultdict(list)
    for row in valid:
        if row['score']:
            grouped[row['codigo'], row['dimension']].append(int(row['score']))
    scored_pairs, pending_scores = [], []
    for pair_id, pair in sorted(pairs.items()):
        if set(pair) != set(models):
            continue
        a, b = (pair[model] for model in models)
        for dimension in DIMS:
            ga, gb = grouped[key[a['call_key']], dimension], grouped[key[b['call_key']], dimension]
            row = {'pair_id': pair_id, 'item_id': a['item_id'], 'dialect': a['dialect'], 'replicate': a['replicate'],
                   'dimension': dimension, 'n_evaluadores_a': len(ga), 'n_evaluadores_b': len(gb)}
            if len(ga) == len(gb) == 2:
                row.update(media_a=statistics.mean(ga), media_b=statistics.mean(gb),
                           diferencia_b_menos_a=statistics.mean(gb) - statistics.mean(ga))
                scored_pairs.append(row)
            else:
                pending_scores.append(row)
    csvwrite(out / 'intentos_historicos.csv', ['clave', 'estado', 'hora', 'resolucion', 'error'], historical)
    csvwrite(out / 'cobertura.csv', ['item_id', 'dialect', 'model_alias', 'completadas', 'esperadas'], coverage)
    csvwrite(out / 'pares_completos.csv', ['pair_id', 'item_id', 'dialect', 'replicate', 'tokens_salida_a', 'tokens_salida_b',
             'diferencia_tokens_b_menos_a', 'caracteres_a', 'caracteres_b', 'diferencia_caracteres_b_menos_a'], paired)
    csvwrite(out / 'pares_pendientes.csv', ['pair_id', 'modelos_completados', 'estado'], incomplete)
    csvwrite(out / 'errores_calificaciones.csv', ['archivo', 'linea', 'errores'], errors)
    csvwrite(out / 'calificaciones_validadas_PRIVADAS.csv', RATING_FIELDS + ['slot', 'response_id', 'item_id', 'dialect', 'model_alias', 'replicate'],
             [dict(row, **mapping[row['codigo']]) for row in valid])
    pair_fields = ['pair_id', 'item_id', 'dialect', 'replicate', 'dimension', 'n_evaluadores_a', 'n_evaluadores_b']
    csvwrite(out / 'calificaciones_pares_exploratorios.csv', pair_fields + ['media_a', 'media_b', 'diferencia_b_menos_a'], scored_pairs)
    csvwrite(out / 'calificaciones_pares_pendientes.csv', pair_fields, pending_scores)
    summary = {'estado_validacion': 'error_calificaciones' if errors else 'valido', 'analisis_actualizado': True,
        'registros': len(audit['records']), 'programadas': len(audit['schedule']), 'completadas': len(complete),
        'reutilizadas_piloto': sum(bool(row.get('reused_from_pilot')) for row in complete.values()),
        'por_modelo': {model: sum(row['model_alias'] == model for row in complete.values()) for model in models},
        'modelos_devueltos': [{'alias': alias, 'devuelto': model, 'n': count} for (alias, model), count in sorted(audit['returned'].items())],
        'items_completos': sum(all(counts[item, dialect, model] == manifest['repetitions'] for dialect in manifest['dialects'] for model in models) for item in manifest['items']),
        'pares_completos': len(paired), 'pares_incompletos': sum(row['estado'] == 'incompleto' for row in incomplete),
        'pares_sin_respuestas': sum(row['estado'] == 'sin_respuestas' for row in incomplete),
        'fallos_historicos': len(historical), 'fallos_pendientes': sum(row['resolucion'] == 'pendiente' for row in historical),
        'incidencias': len(problems), 'uso': {model: dict(cost) for model, cost in audit['costs'].items()},
        'calificaciones_validas': sum(bool(row['score']) for row in valid),
        'decisiones_no_evaluables': sum(not row['score'] for row in valid),
        'errores_calificaciones': len(errors), 'modelos_orden_pares': models,
        'media_diferencia_tokens_b_menos_a': statistics.mean(row['diferencia_tokens_b_menos_a'] for row in paired) if paired else None,
        'mediana_diferencia_tokens_b_menos_a': statistics.median(row['diferencia_tokens_b_menos_a'] for row in paired) if paired else None,
        'media_diferencia_caracteres_b_menos_a': statistics.mean(row['diferencia_caracteres_b_menos_a'] for row in paired) if paired else None,
        'analysis_eligible_manifiesto': manifest['analysis_eligible'], 'sha256_respuestas_leidas': response_hash}
    jsonwrite(out / 'resumen.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        print('ATENCION: revise errores_calificaciones.csv. Las hojas humanas se conservaron intactas.', file=sys.stderr)
        return 1
    return 0


def main(run):
    run = Path(run)
    out = run / 'analisis'
    out.mkdir(exist_ok=True)
    with analysis_lock(out):
        jsonwrite(out / 'resumen.json', {'estado_validacion': 'en_proceso', 'analisis_actualizado': False})
        try:
            return export_analysis(run, out)
        except Exception as exc:
            jsonwrite(out / 'resumen.json', {'estado_validacion': 'error', 'analisis_actualizado': False,
                                           'error': str(exc)})
            raise


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'runs/experimento-completo-2026-11-12'))
