"""Versioned V3 experiment settings, no datasets/runtime downloads."""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from ..ingestion.registry import unique_object

def revision(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def load_v3_config():
    raw=(Path(__file__).resolve().parents[4]/'config/planner-v3.json').read_bytes()
    cfg=json.loads(raw,object_pairs_hook=unique_object)
    if cfg.get('schema_version')!=3:raise ValueError('Invalid V3 settings')
    return cfg,revision(cfg)

def checked_settings(settings):
    baseline,_=load_v3_config()
    if set(settings)!=set(baseline) or any(settings[k]!=v for k,v in baseline.items() if k not in ('score_min','margin_min')):
        raise ValueError('Unpinned V3 settings')
    for key,grid in (('score_min','score_grid'),('margin_min','margin_grid')):
        if type(settings[key]) not in (float,int) or not isfinite(settings[key]) or settings[key] not in baseline[grid]:raise ValueError('Invalid declared threshold')
    return dict(settings,score_min=float(settings['score_min']),margin_min=float(settings['margin_min']))
