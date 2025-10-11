from digest_core.llm.schemas import Digest
import json, pathlib

def test_contract_example():
    p = pathlib.Path("examples/digest-YYYY-MM-DD.json")
    if not p.exists(): return
    data = json.loads(p.read_text())
    Digest(**data)
