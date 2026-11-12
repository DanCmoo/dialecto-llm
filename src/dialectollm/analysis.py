from __future__ import annotations
import csv, hashlib, json, secrets, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

DIMS=('precision','comprehension','relevance')
def readj(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def jsonl(p):
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(p, fields, rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def main(run):
    run=Path(run); out=run/'analisis'; out.mkdir(exist_ok=True)
    manifest=readj(run/'manifest.json'); bank=readj(run/'inputs/item_bank.json'); config=readj(run/'inputs/study_config.json')
    schedule=jsonl(run/'schedule.jsonl'); response_hash=sha(run/'responses.jsonl'); records=jsonl(run/'responses.jsonl')
    if sha(run/'responses.jsonl') != response_hash: raise RuntimeError('Respuestas cambiaron durante lectura; vuelva a ejecutar con la recolección en pausa.')
    problems=[]
    def issue(kind, key, detail): problems.append(dict(tipo=kind,clave=str(key),detalle=str(detail)))
    for label, path in [('config',run/'inputs/study_config.json'),('bank',run/'inputs/item_bank.json'),('schedule',run/'schedule.jsonl')]:
        if sha(path)!=manifest['input_hashes'][label+'_sha256']: issue('hash_archivo',label,'No coincide con manifiesto')
    sch={}; coords=set(); pair_s=defaultdict(set)
    for s in schedule:
        k=s['call_key']; coord=(s['item_id'],s['dialect'],s['model_alias'],s['replicate'])
        if k in sch or coord in coords: issue('duplicado_calendario',k,coord)
        sch[k]=s; coords.add(coord); pair_s[s['pair_id']].add(s['model_alias'])
        if hashlib.sha256(s['prompt'].encode()).hexdigest()!=s['prompt_sha256']: issue('hash_prompt_calendario',k,'No coincide')
        b=next((b for b in bank if b['item_id']==s['item_id']),None)
        if not b or b.get('prompt_'+s['dialect'])!=s['prompt']: issue('prompt_banco',k,'No coincide con banco congelado')
    expected={(i,d,m['alias'],r) for i in manifest['items'] for d in manifest['dialects'] for m in manifest['models'] for r in range(1,manifest['repetitions']+1)}
    if coords!=expected: issue('cobertura_calendario','global',f'faltan {len(expected-coords)}, sobran {len(coords-expected)}')
    complete={}; ids={}; historical=[]; costs=defaultdict(lambda: Counter()); returned=Counter()
    for n,r in enumerate(records,1):
        k=r.get('call_key'); s=sch.get(k)
        if not s: issue('clave_no_programada',k,n); continue
        for field in ('item_id','dialect','model_alias','replicate','pair_id'):
            if r.get(field)!=s.get(field): issue('metadatos',k,field)
        if r.get('requested_model_id')!=s['model_id']: issue('modelo_solicitado',k,r.get('requested_model_id'))
        if r.get('status')!='completed': historical.append(r); continue
        if k in complete: issue('duplicado_completado',k,n); continue
        complete[k]=r
        rid=r.get('response_id')
        if not rid: issue('id_vacio',k,n)
        elif rid in ids: issue('id_duplicado',rid,f'{ids[rid]} / {k}')
        else: ids[rid]=k
        if r.get('api_status')!='completed': issue('estado_api',k,r.get('api_status'))
        if not isinstance(r.get('output_text'),str) or not r['output_text'].strip(): issue('salida_vacia',k,n)
        if r.get('prompt_sha256')!=s['prompt_sha256']: issue('hash_prompt_respuesta',k,'No coincide')
        if not r.get('returned_model_id'): issue('modelo_devuelto_vacio',k,n)
        returned[(r['model_alias'],r.get('returned_model_id',''))]+=1
        u=r.get('usage') or {}; model=next(m for m in manifest['models'] if m['alias']==r['model_alias'])
        try:
            inp=int(u['input_tokens']); otp=int(u['output_tokens']); total=int(u['total_tokens']); reason=int((u.get('output_tokens_details') or {}).get('reasoning_tokens',0))
            if min(inp,otp,total,reason)<0 or total!=inp+otp or reason>otp: raise ValueError('tokens inconsistentes')
            cost=(inp*model['input_usd_per_million']+otp*model['output_usd_per_million'])/1e6
            if abs(float(r['estimated_cost_usd'])-cost)>0.000000011: issue('costo',k,'No coincide con tarifas congeladas')
            c=costs[r['model_alias']]; c.update({'respuestas':1,'input_tokens':inp,'output_tokens':otp,'reasoning_tokens':reason,'total_tokens':total,'costo_usd':cost})
        except (KeyError,TypeError,ValueError) as e: issue('uso',k,e)
    pilot_info=manifest.get('pilot_reuse') or {}; pilot_dir=run.parent / pilot_info.get('source_run_id','__missing__')
    if pilot_info:
        if not (pilot_dir/'manifest.json').exists() or not (pilot_dir/'responses.jsonl').exists():
            issue('piloto_origen',pilot_dir,'No disponible para auditar procedencia')
        else:
            pm=readj(pilot_dir/'manifest.json'); pr=jsonl(pilot_dir/'responses.jsonl')
            if sha(pilot_dir/'manifest.json')!=pilot_info.get('source_manifest_sha256') or sha(pilot_dir/'responses.jsonl')!=pilot_info.get('source_responses_sha256'): issue('hash_piloto','origen','El origen actual difiere de la instantánea importada')
            if pm.get('generation')!=manifest.get('generation'): issue('parametros_piloto','generacion','Difieren')
            sources={r['call_key']:r for r in pr if r.get('status')=='completed'}
            imported=[r for r in complete.values() if r.get('reused_from_pilot')]
            if len(imported)!=pilot_info.get('imported_completed_calls'): issue('conteo_piloto','importados',len(imported))
            for r in imported:
                orig=sources.get(r['call_key'])
                for field in ('response_id','prompt_sha256','requested_model_id','returned_model_id','output_text','usage','estimated_cost_usd'):
                    if not orig or r.get(field)!=orig.get(field): issue('procedencia_piloto',r['call_key'],field)
    hist=[]
    for r in historical: hist.append({'clave':r.get('call_key'),'estado':r.get('status'),'hora':r.get('attempted_at_utc'),'resolucion':'resuelto' if r.get('call_key') in complete else 'pendiente','error':r.get('error','')})
    csvwrite(out/'incidencias.csv',['tipo','clave','detalle'],problems)
    csvwrite(out/'intentos_historicos.csv',['clave','estado','hora','resolucion','error'],hist)
    counts=Counter((r['item_id'],r['dialect'],r['model_alias']) for r in complete.values())
    coverage=[{'item_id':i,'dialect':d,'model_alias':m['alias'],'completadas':counts[(i,d,m['alias'])],'esperadas':manifest['repetitions']} for i in manifest['items'] for d in manifest['dialects'] for m in manifest['models']]
    csvwrite(out/'cobertura.csv',['item_id','dialect','model_alias','completadas','esperadas'],coverage)
    pairs=defaultdict(dict)
    for r in complete.values(): pairs[r['pair_id']][r['model_alias']]=r
    models=[m['alias'] for m in manifest['models']]; paired=[]; incomplete=[]
    for pid in sorted(pair_s):
        p=pairs[pid]; row={'pair_id':pid,'modelos_completados':len(p),'estado':'completo' if len(p)==2 else ('sin_respuestas' if not p else 'incompleto')}
        if len(p)==2:
            a,b=(p[m] for m in models); row.update(item_id=a['item_id'],dialect=a['dialect'],replicate=a['replicate'],tokens_salida_a=a['usage']['output_tokens'],tokens_salida_b=b['usage']['output_tokens'],diferencia_tokens_b_menos_a=b['usage']['output_tokens']-a['usage']['output_tokens'],caracteres_a=len(a['output_text']),caracteres_b=len(b['output_text']),diferencia_caracteres_b_menos_a=len(b['output_text'])-len(a['output_text'])); paired.append(row)
        else: incomplete.append(row)
    csvwrite(out/'pares_completos.csv',['pair_id','item_id','dialect','replicate','tokens_salida_a','tokens_salida_b','diferencia_tokens_b_menos_a','caracteres_a','caracteres_b','diferencia_caracteres_b_menos_a'],paired)
    csvwrite(out/'pares_pendientes.csv',['pair_id','modelos_completados','estado'],incomplete)
    # Stable random codes; key never leaves the ignored run. Existing assignments are immutable.
    keypath=out/'clave_privada.json'; key=readj(keypath) if keypath.exists() else {}
    for k in sorted(complete):
        if k not in key:
            code=secrets.token_hex(8)
            while code in key.values(): code=secrets.token_hex(8)
            key[k]=code
    keypath.write_text(json.dumps(key,ensure_ascii=False,indent=2),encoding='utf-8')
    mapping=[{'codigo':key[k],'call_key':k,'response_id':r['response_id'],'item_id':r['item_id'],'dialect':r['dialect'],'model_alias':r['model_alias'],'replicate':r['replicate']} for k,r in complete.items()]
    csvwrite(out/'clave_correspondencia_PRIVADA.csv',['codigo','call_key','response_id','item_id','dialect','model_alias','replicate'],mapping)
    bankidx={b['item_id']:b for b in bank}
    packet=[{'codigo':key[k],'consulta':sch[k]['prompt'],'respuesta':r['output_text'],'criterios_referencia':bankidx[r['item_id']]['answer_key']} for k,r in complete.items()]
    packet.sort(key=lambda r:r['codigo'])
    for slot in ('evaluador_1','evaluador_2'):
        csvwrite(out/(slot+'_material.csv'),['codigo','consulta','respuesta','criterios_referencia'],packet)
        path=out/(slot+'_calificaciones.csv')
        existing=csvread(path) if path.exists() else []
        present={(r.get('codigo'),r.get('dimension')) for r in existing}
        new=[{'codigo':r['codigo'],'dimension':d,'rater_id':'','score':'','no_evaluable':'','justificacion':''} for r in packet for d in DIMS if (r['codigo'],d) not in present]
        if new or not path.exists(): csvwrite(path,['codigo','dimension','rater_id','score','no_evaluable','justificacion'],existing+new)
    # Validate any submitted human ratings; blank template is valid and does not count as a rating.
    errors=[]; ratings=[]; seen=set(); slot_ids=defaultdict(set); codes={v:k for k,v in key.items() if k in complete}
    for slot in ('evaluador_1','evaluador_2'):
        for n,row in enumerate(csvread(out/(slot+'_calificaciones.csv')),2):
            code=row.get('codigo','').strip(); dim=row.get('dimension','').strip(); rid=row.get('rater_id','').strip(); score=row.get('score','').strip(); ne=row.get('no_evaluable','').strip().lower()
            if not rid and not score and not ne and not row.get('justificacion','').strip(): continue
            err=[]
            if code not in codes: err.append('codigo desconocido')
            if dim not in DIMS: err.append('dimension desconocida')
            if not rid: err.append('falta rater_id')
            if ne not in ('','si','sí','no'): err.append('no_evaluable debe ser si o no')
            if ne in ('si','sí'):
                if score: err.append('no evaluable no admite score')
                if not row.get('justificacion','').strip(): err.append('falta justificacion')
            elif score not in ('1','2','3','4','5'): err.append('score debe ser entero 1-5')
            t=(code,dim,rid)
            if t in seen: err.append('calificacion duplicada')
            seen.add(t)
            if rid: slot_ids[slot].add(rid)
            if err: errors.append({'archivo':slot,'linea':n,'errores':'; '.join(err)})
            else: ratings.append(dict(row,slot=slot))
    for slot, rids in slot_ids.items():
        if len(rids)>1: errors.append({'archivo':slot,'linea':'','errores':'Más de un rater_id en un archivo de evaluador'})
    if slot_ids['evaluador_1'] & slot_ids['evaluador_2']: errors.append({'archivo':'ambos','linea':'','errores':'Los dos evaluadores deben tener identidades distintas'})
    csvwrite(out/'errores_calificaciones.csv',['archivo','linea','errores'],errors)
    csvwrite(out/'calificaciones_validadas_PRIVADAS.csv',['codigo','dimension','rater_id','score','no_evaluable','justificacion','slot','response_id','item_id','dialect','model_alias','replicate'],[dict(r,**next(x for x in mapping if x['codigo']==r['codigo'])) for r in ratings] if not errors else [])
    # Exploratory score comparisons require two independently identified valid ratings per response.
    grouped=defaultdict(list)
    if not errors:
        for r in ratings:
            if r['score'].strip(): grouped[(r['codigo'],r['dimension'])].append(int(r['score']))
    scored_pairs=[]; score_pending=[]
    for pid in sorted(pair_s):
        p=pairs[pid]
        if len(p)!=2: continue
        for dim in DIMS:
            a,b=(p[m] for m in models); ga=grouped[(key[a['call_key']],dim)]; gb=grouped[(key[b['call_key']],dim)]
            row={'pair_id':pid,'item_id':a['item_id'],'dialect':a['dialect'],'replicate':a['replicate'],'dimension':dim,'n_evaluadores_a':len(ga),'n_evaluadores_b':len(gb)}
            if len(ga)>=2 and len(gb)>=2:
                row.update(media_a=statistics.mean(ga),media_b=statistics.mean(gb),diferencia_b_menos_a=statistics.mean(gb)-statistics.mean(ga)); scored_pairs.append(row)
            else: score_pending.append(row)
    csvwrite(out/'calificaciones_pares_exploratorios.csv',['pair_id','item_id','dialect','replicate','dimension','n_evaluadores_a','n_evaluadores_b','media_a','media_b','diferencia_b_menos_a'],scored_pairs)
    csvwrite(out/'calificaciones_pares_pendientes.csv',['pair_id','item_id','dialect','replicate','dimension','n_evaluadores_a','n_evaluadores_b'],score_pending)
    summary={'registros':len(records),'programadas':len(schedule),'completadas':len(complete),'reutilizadas_piloto':sum(bool(r.get('reused_from_pilot')) for r in complete.values()),'por_modelo':{m:sum(r['model_alias']==m for r in complete.values()) for m in models},'modelos_devueltos':[{'alias':a,'devuelto':b,'n':n} for (a,b),n in sorted(returned.items())],'items_completos':sum(all(counts[(i,d,m)]==3 for d in manifest['dialects'] for m in models) for i in manifest['items']),'pares_completos':len(paired),'pares_incompletos':sum(x['estado']=='incompleto' for x in incomplete),'pares_sin_respuestas':sum(x['estado']=='sin_respuestas' for x in incomplete),'fallos_historicos':len(hist),'fallos_pendientes':sum(x['resolucion']=='pendiente' for x in hist),'incidencias':len(problems),'uso':{k:dict(v) for k,v in costs.items()},'calificaciones_validas':len(ratings) if not errors else 0,'errores_calificaciones':len(errors),'modelos_orden_pares':models,'media_diferencia_tokens_b_menos_a':statistics.mean(x['diferencia_tokens_b_menos_a'] for x in paired) if paired else None,'mediana_diferencia_tokens_b_menos_a':statistics.median(x['diferencia_tokens_b_menos_a'] for x in paired) if paired else None,'media_diferencia_caracteres_b_menos_a':statistics.mean(x['diferencia_caracteres_b_menos_a'] for x in paired) if paired else None,'analysis_eligible_manifiesto':manifest['analysis_eligible'],'sha256_respuestas_leidas':response_hash}
    (out/'resumen.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if problems or errors: print('ATENCION: revisar incidencias/errores.',file=sys.stderr); return 1
    return 0
if __name__=='__main__': sys.exit(main(sys.argv[1] if len(sys.argv)>1 else 'runs/experimento-completo-2026-11-12'))
