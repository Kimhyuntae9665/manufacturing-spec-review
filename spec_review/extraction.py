"""Exact, whole-cell synthetic annotation extraction. No gold or model access."""
import hashlib,re
from decimal import Decimal,InvalidOperation,localcontext
FIELDS=("material_grade","finish_code","coating_thickness")
HEADERS={
 "material_grade":r"(?:Material grade|Material|재질)",
 "finish_code":r"(?:Finish code|Finish|Surface finish|표면처리)",
 "coating_thickness":r"(?:Coating thickness|Nominal coating thickness|도금 두께|피막 두께)"
}
LIMIT=32768
QUALIFIERS=re.compile(r"\b(?:or|and|not|optional|equivalent|min(?:imum)?|max(?:imum)?|at\s+least|at\s+most|GD\s*&\s*T)\b|또는|아님|금지|선택|이상|이하|以上|以下|至少|最多|[<>≥≤±~～∅Ø]|(?:\d\s*[-–—]\s*\d)",re.I)
UNKNOWN=re.compile(r"^(?:TBD|UNKNOWN|미정|확인필요)$",re.I)

def document_envelope(document):
 if not isinstance(document,dict):raise ValueError("invalid_document")
 content=document.get("content")
 if not isinstance(content,str) or len(content)>LIMIT:raise ValueError("invalid_content")
 digest=hashlib.sha256(content.encode("utf-8")).hexdigest()
 if document.get("source_hash")!=digest:raise ValueError("source_hash_mismatch")
 for key in ("id","part_number","part_revision","document_role","approval_state","site"):
  if not isinstance(document.get(key),str) or not 1<=len(document[key])<=200:raise ValueError("invalid_metadata")
 revision=document.get("document_revision")
 if not isinstance(revision,int) or isinstance(revision,bool) or revision<1:raise ValueError("invalid_document_revision")
 return {key:document[key] for key in ("id","part_number","part_revision","document_revision","document_role","approval_state","site")}|{"source_hash":digest}

def classify_cell(field,raw):
 if not raw or UNKNOWN.fullmatch(raw):return {"state":"information_missing","value":None,"unit":None}
 if QUALIFIERS.search(raw):return {"state":"needs_review","value":None,"unit":None,"reason":"qualified_or_alternative_cell"}
 if field!="coating_thickness":
  if not re.fullmatch(r"[A-Z][A-Z0-9_]*",raw):return {"state":"needs_review","value":None,"unit":None,"reason":"unsupported_code_notation"}
  return {"state":"observed","value":raw,"unit":None}
 match=re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([^\s]+)",raw)
 if not match:return {"state":"needs_review","value":None,"unit":None,"reason":"not_a_declared_nominal"}
 numeral,unit=match.groups()
 if unit not in ("mm","µm"):return {"state":"unsupported_unit","value":None,"unit":unit}
 try:value=Decimal(numeral)
 except InvalidOperation:return {"state":"needs_review","value":None,"unit":unit,"reason":"invalid_decimal"}
 if not value.is_finite():return {"state":"needs_review","value":None,"unit":unit}
 with localcontext() as context:
  context.prec=max(28,len(numeral.replace(".",""))+4)
  normalized=value*(1000 if unit=="mm" else 1)
  normalized_text=format(normalized.normalize(),"f")
 return {"state":"nominal","value":numeral,"unit":unit,"normalized_um":normalized_text}

def extract_document(document):
 envelope=document_envelope(document);content=document["content"];lines=content.splitlines(keepends=True)
 rows=[];offset=0
 for number,line in enumerate(lines,1):
  body=line.rstrip("\r\n");rows.append((number,body,offset));offset+=len(line)
 for metadata,header in (("part_number","Part number"),("part_revision","Part revision")):
  found=[re.fullmatch(r"\s*"+header+r"\s*[:：]\s*(.*?)\s*",line,re.I) for _,line,_ in rows]
  values=[match.group(1) for match in found if match]
  if values and (len(values)!=1 or values[0]!=envelope[metadata]):
   raise ValueError("source_identity_conflict")
 fields={}
 for field in FIELDS:
  matches=[]
  pattern=re.compile(r"^\s*"+HEADERS[field]+r"\s*[:：]\s*(.*?)\s*$",re.I)
  for number,line,start in rows:
   found=pattern.fullmatch(line)
   if found:matches.append((number,line,start,found.group(1).strip()))
  if not matches:
   fields[field]={"raw_value":None,"value":None,"unit":None,"state":"information_missing","quote":None,"line":None,"span_start":None,"span_end":None,"reason":"field_not_present"}
   continue
  number,line,start,raw=matches[0]
  cell={"raw_value":raw,"quote":line,"line":number,"span_start":start,"span_end":start+len(line)}
  cell.update(classify_cell(field,raw))
  if len(matches)!=1 or content.count(line)!=1:
   cell.update(state="needs_review",value=None,reason="ambiguous_field_or_quote",occurrence_count=len(matches))
  fields[field]=cell
 return {"document_id":envelope["id"],"provenance":envelope,"fields":fields,"extraction_state":"deterministic_observed","model_state":"not_requested"}

def validate_model_proposal(document,proposal):
 """Return server-derived spans only; never trust model metadata or partial quotes."""
 observed=extract_document(document)
 if not isinstance(proposal,dict) or set(proposal)!={"fields"}:raise ValueError("invalid_proposal_shape")
 fields=proposal["fields"]
 if not isinstance(fields,dict) or set(fields)!=set(FIELDS):raise ValueError("required_field_coverage_missing")
 for field in FIELDS:
  cell=fields[field];actual=observed["fields"][field]
  if not isinstance(cell,dict) or set(cell)!={"raw_value","quote"}:raise ValueError("invalid_field_proposal")
  if cell["raw_value"] is not None and not isinstance(cell["raw_value"],str):raise ValueError("invalid_raw_value_type")
  if cell["quote"] is not None and not isinstance(cell["quote"],str):raise ValueError("invalid_quote_type")
  if cell["raw_value"]!=actual["raw_value"]:raise ValueError("unsupported_full_cell_value")
  if cell["quote"]!=actual["quote"]:raise ValueError("quote_not_full_original_field")
  if actual.get("reason")=="ambiguous_field_or_quote":raise ValueError("ambiguous_quote")
  if cell["quote"] is not None and document["content"].count(cell["quote"])!=1:raise ValueError("ambiguous_quote")
 observed["extraction_state"]="model_proposal_source_verified"
 observed["model_state"]="source_verified"
 return observed
