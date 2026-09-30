import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from spec_review.extraction import extract_document,validate_model_proposal,classify_cell,document_envelope
from spec_review.comparison import compare_documents,fingerprint
ROOT=Path(__file__).resolve().parents[1]
class AnnotationTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads((ROOT/"data/documents.json").read_text());self.docs={d["id"]:d for d in self.data["documents"]}
 def altered(self,did,replacements):
  doc=copy.deepcopy(self.docs[did])
  for before,after in replacements:doc["content"]=doc["content"].replace(before,after)
  doc["source_hash"]=hashlib.sha256(doc["content"].encode()).hexdigest()
  return doc
 def proposal(self,doc):
  e=extract_document(doc)
  return {"fields":{name:{"raw_value":cell["raw_value"],"quote":cell["quote"]} for name,cell in e["fields"].items()}}
 def test_frozen_gold_pair_p001(self):
  r=compare_documents(self.docs["SRC-001"],self.docs["SRC-002"],"P001")
  self.assertEqual(r["overall"],"annotations_match")
  self.assertEqual(r["required_coverage"]["observed"],3)
 def test_frozen_gold_pair_p002_grade_is_different_not_substring(self):
  r=compare_documents(self.docs["SRC-003"],self.docs["SRC-004"],"P002")
  self.assertEqual(r["checks"][0]["state"],"notation_difference");self.assertEqual(r["overall"],"needs_review")
 def test_frozen_gold_pair_p003_finish_and_missing_thickness(self):
  r=compare_documents(self.docs["SRC-005"],self.docs["SRC-006"],"P003")
  self.assertEqual([x["state"] for x in r["checks"]],["same_notation","notation_difference","information_missing"])
 def test_declared_decimal_units_are_equal(self):
  self.assertEqual(classify_cell("coating_thickness","10 µm")["normalized_um"],classify_cell("coating_thickness","0.010 mm")["normalized_um"])
 def test_missing_is_not_zero(self):
  self.assertIsNone(classify_cell("coating_thickness","")["value"])
  self.assertEqual(classify_cell("coating_thickness","0 µm")["normalized_um"],"0")
 def test_unsupported_unit_is_not_converted(self):
  self.assertEqual(classify_cell("coating_thickness","10 mil")["state"],"unsupported_unit")
 def test_bounds_are_not_nominal(self):
  for raw in ("10 µm以上","10 µm 이상",">=10 µm","10 µm maximum","10 µm 이하","10 µm以下"):
   with self.subTest(raw=raw):self.assertEqual(classify_cell("coating_thickness",raw)["state"],"needs_review")
 def test_ranges_tolerance_gdt_need_review(self):
  for raw in ("8–12 µm","10 ± 2 µm","10~12 µm","10 µm GD&T"):
   with self.subTest(raw=raw):self.assertEqual(classify_cell("coating_thickness",raw)["state"],"needs_review")
 def test_alternative_grade_cannot_be_partial(self):
  doc=self.altered("SRC-003",[("Material grade: SUS304","Material grade: SUS304 or SUS316")])
  p=self.proposal(doc);p["fields"]["material_grade"]["raw_value"]="SUS304"
  with self.assertRaisesRegex(ValueError,"unsupported_full_cell"):validate_model_proposal(doc,p)
 def test_grade_suffix_cannot_be_partial(self):
  p=self.proposal(self.docs["SRC-004"]);p["fields"]["material_grade"]["raw_value"]="SUS304"
  with self.assertRaisesRegex(ValueError,"unsupported_full_cell"):validate_model_proposal(self.docs["SRC-004"],p)
 def test_original_quote_line_and_span_are_server_derived(self):
  doc=self.docs["SRC-001"];e=validate_model_proposal(doc,self.proposal(doc));c=e["fields"]["coating_thickness"]
  self.assertEqual(c["line"],5);self.assertEqual(doc["content"][c["span_start"]:c["span_end"]],c["quote"])
  self.assertEqual(e["provenance"]["source_hash"],doc["source_hash"])
 def test_hallucinated_quote_is_rejected(self):
  p=self.proposal(self.docs["SRC-001"]);p["fields"]["material_grade"]["quote"]="Material grade: STEEL"
  with self.assertRaisesRegex(ValueError,"quote_not_full"):validate_model_proposal(self.docs["SRC-001"],p)
 def test_partial_quote_cannot_hide_qualifier(self):
  doc=self.altered("SRC-001",[("Coating thickness: 10 µm","Coating thickness: 10 µm以上")]);p=self.proposal(doc)
  p["fields"]["coating_thickness"]={"raw_value":"10 µm","quote":"Coating thickness: 10 µm"}
  with self.assertRaises(ValueError):validate_model_proposal(doc,p)
 def test_duplicate_quote_is_ambiguous(self):
  doc=self.altered("SRC-001",[("Finish code: BLACK_ANODIZE","Finish code: BLACK_ANODIZE\nFinish code: BLACK_ANODIZE")])
  self.assertEqual(extract_document(doc)["fields"]["finish_code"]["reason"],"ambiguous_field_or_quote")
  with self.assertRaisesRegex(ValueError,"ambiguous"):validate_model_proposal(doc,self.proposal(doc))
 def test_conflicting_field_values_are_not_selected_arbitrarily(self):
  doc=self.altered("SRC-001",[("Material grade: AL5052","Material grade: AL5052\nMaterial grade: AL6061")])
  self.assertEqual(extract_document(doc)["fields"]["material_grade"]["state"],"needs_review")
 def test_required_model_fields_cannot_be_missing_or_empty(self):
  for p in ({"fields":{}},{"fields":{"material_grade":None}}):
   with self.assertRaisesRegex(ValueError,"coverage"):validate_model_proposal(self.docs["SRC-001"],p)
 def test_missing_whole_field_prevents_all_match(self):
  ref=self.altered("SRC-001",[("Coating thickness: 10 µm\n","")]);cand=self.altered("SRC-002",[("Coating thickness: 0.010 mm\n","")])
  r=compare_documents(ref,cand,"P001");self.assertEqual(r["overall"],"needs_review");self.assertFalse(r["required_coverage"]["complete"])
 def test_empty_documents_cannot_all_match(self):
  ref=self.altered("SRC-001",[(self.docs["SRC-001"]["content"],"")]);cand=self.altered("SRC-002",[(self.docs["SRC-002"]["content"],"")])
  self.assertEqual(compare_documents(ref,cand,"P001")["overall"],"needs_review")
 def test_reference_draft_rejected_candidate_draft_retained(self):
  ref=copy.deepcopy(self.docs["SRC-001"]);ref["approval_state"]="draft"
  with self.assertRaisesRegex(ValueError,"reference_not_approved"):compare_documents(ref,self.docs["SRC-002"],"P001")
  self.assertEqual(compare_documents(self.docs["SRC-001"],self.docs["SRC-002"],"P001")["candidate"]["approval_state"],"draft")
 def test_different_part_rejected(self):
  with self.assertRaisesRegex(ValueError,"different_part"):compare_documents(self.docs["SRC-001"],self.docs["SRC-004"],"P001")
 def test_part_revision_is_not_document_revision(self):
  cand=copy.deepcopy(self.docs["SRC-002"]);cand["document_revision"]=99
  self.assertEqual(compare_documents(self.docs["SRC-001"],cand,"P001")["overall"],"annotations_match")
  cand["part_revision"]="B"
  with self.assertRaisesRegex(ValueError,"different_part_revision"):compare_documents(self.docs["SRC-001"],cand,"P001")
 def test_source_hash_mismatch_rejected(self):
  doc=copy.deepcopy(self.docs["SRC-001"]);doc["content"]+="changed"
  with self.assertRaisesRegex(ValueError,"source_hash"):extract_document(doc)
 def test_changed_content_changes_fingerprint(self):
  old=fingerprint(self.docs["SRC-001"],self.docs["SRC-002"],"P001")
  cand=self.altered("SRC-002",[("AL5052","AL6061")])
  self.assertNotEqual(old,fingerprint(self.docs["SRC-001"],cand,"P001"))
 def test_field_negation_is_not_nominal(self):
  self.assertEqual(classify_cell("material_grade","NOT SUS304")["state"],"needs_review")
 def test_model_metadata_cannot_override_server_envelope(self):
  p=self.proposal(self.docs["SRC-001"]);p["source_hash"]="fake"
  with self.assertRaisesRegex(ValueError,"invalid_proposal_shape"):validate_model_proposal(self.docs["SRC-001"],p)
 def test_precise_decimal_no_rounding_equivalence(self):
  a=classify_cell("coating_thickness","0.0100000000000000000000000000001 mm")
  b=classify_cell("coating_thickness","10 µm")
  self.assertNotEqual(a["normalized_um"],b["normalized_um"])
 def test_forged_extraction_fields_cannot_override_sources(self):
  ref=self.docs["SRC-003"];cand=self.docs["SRC-004"];ex=[extract_document(ref),extract_document(cand)]
  ex[1]["fields"]["material_grade"]["value"]="SUS304"
  with self.assertRaisesRegex(ValueError,"source_mismatch"):compare_documents(ref,cand,"P002",ex)
 def test_source_part_header_cannot_disagree_with_envelope(self):
  for before,after in (("Part number: P001","Part number: P999"),("Part revision: A","Part revision: B")):
   doc=self.altered("SRC-001",[(before,after)])
   with self.assertRaisesRegex(ValueError,"source_identity_conflict"):extract_document(doc)
 def test_duplicated_source_identity_is_ambiguous(self):
  doc=self.altered("SRC-001",[("Part number: P001","Part number: P001\nPart number: P001")])
  with self.assertRaisesRegex(ValueError,"source_identity_conflict"):extract_document(doc)
 def test_optional_equivalent_forbidden_and_na_never_all_clear(self):
  for field,raw in (("material_grade","SUS304 or equivalent"),("finish_code","NI optional"),("finish_code","NI 금지"),("coating_thickness","N/A")):
   with self.subTest(raw=raw):
    self.assertNotIn(classify_cell(field,raw)["state"],("observed","nominal"))
 def test_exact_quote_from_other_field_cannot_validate(self):
  p=self.proposal(self.docs["SRC-001"])
  p["fields"]["material_grade"]["quote"]=p["fields"]["finish_code"]["quote"]
  with self.assertRaisesRegex(ValueError,"quote_not_full"):validate_model_proposal(self.docs["SRC-001"],p)
if __name__=="__main__":unittest.main()
