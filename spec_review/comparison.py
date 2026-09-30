"""Declared annotation comparison rules; no engineering suitability judgement."""
import hashlib,json
from .extraction import FIELDS,extract_document,document_envelope
POLICY_VERSION="annotation-v1"
def pair_envelope(reference,candidate,target_part):
 ref=document_envelope(reference);cand=document_envelope(candidate)
 if ref["part_number"]!=target_part or cand["part_number"]!=target_part:raise ValueError("different_part")
 if ref["part_revision"]!=cand["part_revision"]:raise ValueError("different_part_revision")
 if ref["document_role"]!="reference_spec" or cand["document_role"]!="candidate_drawing":raise ValueError("invalid_document_roles")
 if ref["approval_state"]!="approved":raise ValueError("reference_not_approved")
 if cand["approval_state"] not in ("draft","approved"):raise ValueError("invalid_candidate_state")
 if ref["site"]!=cand["site"]:raise ValueError("different_site")
 return ref,cand

def fingerprint(reference,candidate,target_part):
 ref,cand=pair_envelope(reference,candidate,target_part)
 canonical=json.dumps({"policy":POLICY_VERSION,"target_part":target_part,"reference":ref,"candidate":cand},sort_keys=True,separators=(",",":"))
 return hashlib.sha256(canonical.encode()).hexdigest()

def compare_documents(reference,candidate,target_part,extractions=None):
 ref,cand=pair_envelope(reference,candidate,target_part)
 if extractions is None:extractions=[extract_document(reference),extract_document(candidate)]
 if len(extractions)!=2 or [e["provenance"] for e in extractions]!=[ref,cand]:raise ValueError("extraction_provenance_mismatch")
 if any(e["fields"]!=extract_document(d)["fields"] for e,d in zip(extractions,(reference,candidate))):raise ValueError("extraction_source_mismatch")
 checks=[];coverage=0
 for field in FIELDS:
  left,right=(e["fields"][field] for e in extractions)
  states=(left["state"],right["state"])
  if "information_missing" in states:state="information_missing";text="필수 표기 정보가 없거나 미정입니다. 누락을 0이나 적용 없음으로 해석하지 않습니다."
  elif "unsupported_unit" in states:state="unsupported_unit";text="선언한 mm/µm 변환 범위 밖의 단위입니다."
  elif any(s not in ("observed","nominal") for s in states):state="needs_review";text="한정어·대안·범위·공차·충돌 또는 지원하지 않는 표기입니다."
  else:
   coverage+=1
   if field=="coating_thickness":
    equal=left["normalized_um"]==right["normalized_um"]
    state="same_declared_nominal" if equal else "notation_difference"
    text="선언한 명목 mm/µm 환산값을 대조했습니다. 공차나 제조 적합성은 판단하지 않습니다."
   else:
    equal=left["value"]==right["value"]
    state="same_notation" if equal else "notation_difference"
    text="전체 코드 표기의 동일성만 대조했습니다. 재질 대체·공학적 동등성은 판단하지 않습니다."
  checks.append({"field":field,"state":state,"reference_value":left["raw_value"],"candidate_value":right["raw_value"],"explanation":text})
 matched=coverage==len(FIELDS) and all(x["state"] in ("same_notation","same_declared_nominal") for x in checks)
 return {"target_part":target_part,"reference":ref,"candidate":cand,"extractions":extractions,"checks":checks,"overall":"annotations_match" if matched else "needs_review","required_coverage":{"observed":coverage,"required":len(FIELDS),"complete":coverage==len(FIELDS)},"fingerprint":fingerprint(reference,candidate,target_part),"policy_version":POLICY_VERSION,"scope":"document_notation_only_not_engineering_or_manufacturing_approval"}
