"""Evaluator-only frozen synthetic truth; never imported by runtime service."""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from spec_review.extraction import classify_cell,extract_document,validate_model_proposal
from spec_review.comparison import compare_documents
def main():
 gold_path=ROOT/"evaluations/gold_v1.json"
 manifest=json.loads((ROOT/"evaluations/freeze_manifest.json").read_text())
 gold=json.loads(gold_path.read_text())
 corpus_path=ROOT/"data/documents.json"
 if hashlib.sha256(gold_path.read_bytes()).hexdigest()!=manifest["gold_sha256"]:raise RuntimeError("frozen_gold_changed")
 if hashlib.sha256(corpus_path.read_bytes()).hexdigest()!=manifest["corpus_sha256"]:raise RuntimeError("frozen_corpus_changed")
 docs=json.loads(corpus_path.read_text())["documents"]
 pairs={part:[next(d for d in docs if d["part_number"]==part and d["document_role"]==role) for role in ("reference_spec","candidate_drawing")] for part in ("P001","P002","P003")}
 outcomes=[]
 for case in gold["cases"]:
  kind=case["kind"];actual={}
  if kind=="pair":
   r=compare_documents(*pairs[case["part"]],case["part"])
   actual=dict(zip(("material","finish","thickness"),[row["state"] for row in r["checks"]]),overall=r["overall"])
  elif kind=="field":actual=classify_cell("coating_thickness",case["raw"])
  elif kind=="material":
   doc=copy.deepcopy(pairs["P002"][0]);doc["content"]=doc["content"].replace("Material grade: SUS304","Material grade: "+case["raw"]);doc["source_hash"]=hashlib.sha256(doc["content"].encode()).hexdigest()
   obs=extract_document(doc);proposal={"fields":{name:{"raw_value":cell["raw_value"],"quote":cell["quote"]} for name,cell in obs["fields"].items()}}
   proposal["fields"]["material_grade"]["raw_value"]=case["proposal"]
   actual["state"]=obs["fields"]["material_grade"]["state"]
   try:validate_model_proposal(doc,proposal);actual["valid"]=True
   except ValueError:actual["valid"]=False
  else:
   ref,cand=copy.deepcopy(pairs["P001"])
   if kind=="policy":(ref if case["name"]=="reference_is_draft" else cand)["approval_state"]="draft"
   elif kind=="identity":cand=copy.deepcopy(pairs[case["candidate_part"]][1])
   elif kind=="revision":cand["part_revision"]=case["candidate_part_revision"]
   try:compare_documents(ref,cand,"P001");actual["comparison_allowed"]=True
   except ValueError:actual["comparison_allowed"]=False
  expected=case["expected"];passed=all(actual.get(k)==v for k,v in expected.items())
  outcomes.append({"id":case["id"],"kind":kind,"expected":expected,"actual":actual,"passed":passed})
 result={"scope":"16 predeclared synthetic gold cases, not heldout industrial performance","synthetic":True,"expert_validated":False,"model_calls":0,"cases":outcomes,"passed":sum(x["passed"] for x in outcomes),"total":len(outcomes)}
 (ROOT/"artifacts").mkdir(parents=True,exist_ok=True)
 (ROOT/"artifacts/frozen-gold-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!="cases"},ensure_ascii=False))
 return 0 if result["passed"]==result["total"] else 1
if __name__=="__main__":raise SystemExit(main())
