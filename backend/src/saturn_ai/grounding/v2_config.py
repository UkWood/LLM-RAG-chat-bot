"""Versioned local ontology; never loads evaluation cases."""
from hashlib import sha256
import json
from pathlib import Path
from ..ingestion.registry import unique_object

CONFIG_PATH=Path(__file__).resolve().parents[4]/'config/planner-v2.json'


def load_config():
    raw=CONFIG_PATH.read_bytes()
    if len(raw)>20000:raise ValueError('Planner config size limit')
    config=json.loads(raw,object_pairs_hook=unique_object)
    if config.get('schema_version')!=2:raise ValueError('Unsupported planner config')
    return config,sha256(raw).hexdigest()
