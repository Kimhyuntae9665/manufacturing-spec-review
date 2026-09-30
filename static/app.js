"use strict";
(() => {
  const byId = id => document.getElementById(id);
  const labels = {
    roles: {engineer:"설계·품질 담당", reviewer:"검토자"},
    fields: {material_grade:"재질", finish_code:"표면처리", coating_thickness:"명목 코팅 두께"},
    check: {same_notation:"표기 일치", same_declared_nominal:"선언 명목값 일치", notation_difference:"표기 차이", information_missing:"정보 누락", unsupported_unit:"지원하지 않는 단위", needs_review:"추가 검토 필요"},
    extraction: {not_requested:"추출 대기", model_verified:"모델 제안 · 원문 검증됨", source_verified:"원문 검증됨", deterministic:"규칙 원문 검사", deterministic_observed:"규칙 원문 관측", model_proposal_source_verified:"모델 제안 · 원문 검증됨", observed:"원문 표기 확인", baseline:"규칙 원문 검사", failed:"모델 검증 실패", needs_review:"추가 검토 필요", missing:"정보 누락", present:"표기 있음", nominal:"선언 명목값"}
  };
  const fieldOrder = ["material_grade","finish_code","coating_thickness"];
  const state = {token:"", principal:null, profiles:[], parts:[], part:null, documents:[], reference:null, candidate:null, comparison:null, events:[], loading:false, working:false, sourceBusy:false, auditBusy:false, comparing:false, profileReady:false, generation:0};
  const storageKey = "nota-spec-demo-v1";
  const reads = new Set();

  function make(tag, text, className) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }
  function list(value) { return Array.isArray(value) ? value : []; }
  function display(value, empty="—") {
    if (value === null || value === undefined || value === "") return empty;
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  }
  function date(value) {
    if (!value) return "시각 없음";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : new Intl.DateTimeFormat("ko-KR", {month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23",timeZone:"UTC"}).format(parsed) + " UTC";
  }
  function tell(text, severity="") {
    byId("message").textContent = text;
    byId("message").className = "message" + (severity ? " " + severity : "");
    byId("message").hidden = !text;
  }
  function save() {
    try {
      if (state.token && state.principal) sessionStorage.setItem(storageKey,JSON.stringify({token:state.token,principal:state.principal}));
      else sessionStorage.removeItem(storageKey);
    } catch (_) { /* A memory-only session is sufficient when storage is unavailable. */ }
  }
  function restore() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (saved && typeof saved.token === "string" && saved.token && saved.principal && typeof saved.principal.role === "string" && typeof saved.principal.site === "string") {
        state.token = saved.token;
        state.principal = saved.principal;
      }
    } catch (_) { /* Invalid saved demo sessions are ignored. */ }
  }
  function cancelReads() { reads.forEach(controller => controller.abort()); reads.clear(); }
  function disconnect() {
    cancelReads();
    state.generation += 1;
    Object.assign(state,{token:"",principal:null,parts:[],part:null,documents:[],reference:null,candidate:null,comparison:null,events:[],loading:false,sourceBusy:false,auditBusy:false});
    save();
    renderPrincipal();
    renderParts();
    byId("work").hidden = true;
    byId("welcome").hidden = false;
  }
  async function request(path, options={}) {
    const method = options.method || "GET";
    const controller = new AbortController();
    if (method === "GET") reads.add(controller);
    let timedOut = false;
    const timer = setTimeout(() => { timedOut=true; controller.abort(); }, options.timeout || 15000);
    const headers = {Accept:"application/json"};
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (!options.public && state.token) headers.Authorization = "Bearer " + state.token;
    try {
      const response = await fetch(path,{method,headers,body:options.body === undefined ? undefined : JSON.stringify(options.body),signal:controller.signal,cache:"no-store",credentials:"same-origin"});
      let payload;
      try { payload = await response.json(); }
      catch (_) { throw new Error("응답을 읽을 수 없습니다. 워크벤치 연결을 확인해 주세요."); }
      if (!response.ok) {
        const messages = {400:"문서 선택 또는 입력 내용을 확인해 주세요.",401:"데모 세션이 만료되었거나 유효하지 않습니다. 다시 접속해 주세요.",403:"현재 사이트·역할에서 허용되지 않은 작업입니다.",404:"접근 가능한 현재 문서나 대조 기록을 찾을 수 없습니다.",409:"원문 또는 문서 상태가 변경되어 이 대조 기록을 사용할 수 없습니다. 현재 원문으로 다시 대조해 주세요.",413:"요청이 허용된 크기를 초과했습니다.",429:"다른 요청을 처리하고 있습니다. 잠시 뒤 확인해 주세요.",503:"추출 서비스를 사용할 수 없습니다."};
        const error = new Error(messages[response.status] || "서버에서 요청을 완료하지 못했습니다.");
        error.status = response.status;
        if (response.status === 401 && !options.public) { disconnect(); tell(error.message,"error"); }
        throw error;
      }
      return payload;
    } catch (error) {
      if (timedOut) {
        const timeout = new Error(method === "GET" ? "응답 대기 시간이 초과되었습니다. 현재 상태를 다시 확인해 주세요." : "응답 대기 시간이 초과되었습니다. 서버 처리는 계속될 수 있습니다. 이력을 확인한 뒤 새 실행 여부를 판단해 주세요.");
        timeout.timeout = true;
        throw timeout;
      }
      if (error instanceof TypeError) throw new Error("로컬 워크벤치에 연결할 수 없습니다.");
      throw error;
    } finally { clearTimeout(timer); reads.delete(controller); }
  }
  function errorMessage(error) { if (error.name !== "AbortError") tell(error.message || "요청을 처리하지 못했습니다.",error.timeout ? "warning" : "error"); }
  function docId(envelope) { return typeof envelope === "string" ? envelope : envelope && (envelope.id || envelope.document_id); }
  function partId(target) { return typeof target === "string" ? target : target && (target.id || target.part_number); }
  function invalidated(comparison) { return !!comparison && (comparison.stale === true || comparison.review_state === "invalidated" || comparison.status === "invalidated"); }
  function modelFailed(comparison) { return !!comparison && comparison.model_state === "failed"; }
  function pairProblem() {
    const reference = state.reference, candidate = state.candidate;
    if (!state.part || !reference || !candidate) return "접근 가능한 기준 사양과 후보 도면이 모두 필요합니다.";
    if (reference.part_number !== state.part.id || candidate.part_number !== state.part.id) return "두 문서가 선택한 부품에 속하지 않습니다.";
    if (reference.part_revision !== candidate.part_revision || reference.part_revision !== state.part.revision) return "부품 개정이 서로 다릅니다. 자동으로 다른 개정을 대체하지 않습니다.";
    if (reference.document_role !== "reference_spec" || candidate.document_role !== "candidate_drawing") return "문서 역할이 기준 사양·후보 도면 조합과 다릅니다.";
    if (reference.approval_state !== "approved") return "기준 사양이 승인 상태가 아닙니다. 대조할 수 없습니다.";
    if (!["draft","approved"].includes(candidate.approval_state)) return "후보 문서가 검토 가능한 초안 또는 승인 상태가 아닙니다.";
    if (reference.site !== candidate.site || reference.site !== state.principal.site) return "두 문서의 사이트가 현재 접근 범위와 다릅니다.";
    return "";
  }
  function sync() {
    const blocked = state.loading || state.working;
    byId("profile").disabled = blocked || !state.profileReady;
    byId("connect").disabled = blocked || !state.profileReady || !byId("profile").value;
    byId("connect").textContent = state.token ? "프로필로 재접속" : "세션 시작";
    byId("reference-select").disabled = blocked || state.sourceBusy || !state.part;
    byId("candidate-select").disabled = blocked || state.sourceBusy || !state.part;
    byId("compare").disabled = blocked || state.sourceBusy || !!pairProblem() || !state.token;
    document.querySelectorAll('input[name="mode"]').forEach(input => { input.disabled = blocked || state.sourceBusy || !state.part; });
    document.querySelectorAll(".part-button").forEach(button => { button.disabled = blocked; });
    document.querySelectorAll(".quote-button").forEach(button => { button.disabled = state.sourceBusy || state.loading; });
    document.querySelectorAll("#audit-list .text-button").forEach(button => { button.disabled = blocked; });
    byId("refresh-audit").disabled = blocked || state.auditBusy || !state.part;
    const canReview = state.principal && state.principal.role === "reviewer" && state.comparison && !state.comparison.review && !invalidated(state.comparison) && !state.sourceBusy;
    const acknowledged = !modelFailed(state.comparison) || byId("manual-confirmation").checked;
    byId("manual-confirmation").disabled = blocked || !canReview;
    byId("review-comment").disabled = blocked || !canReview;
    byId("reviewed").disabled = blocked || !canReview || !acknowledged;
    byId("followup").disabled = blocked || !canReview || !acknowledged;
  }
  function renderPrincipal() {
    byId("principal").textContent = state.principal ? "사이트 " + state.principal.site + " / " + (labels.roles[state.principal.role] || state.principal.role) : "연결된 세션 없음";
    byId("permission-note").textContent = state.principal ? (state.principal.role === "reviewer" ? "검토 기록·후속 확인 요청 가능 · 설계 승인 권한 아님" : "원문 확인·대조 가능 · 결정 기록은 검토자 역할 필요") + " / 데모 로그인" : "합성 데모 로그인 · 기업 인증 아님";
    sync();
  }
  function renderParts() {
    const target = byId("parts");
    target.replaceChildren();
    byId("part-count").textContent = String(state.parts.length);
    if (!state.parts.length) target.append(make("p",state.token ? "현재 사이트에서 접근 가능한 부품이 없습니다." : "세션을 시작하면 접근 가능한 부품을 확인할 수 있습니다.","rail-empty"));
    state.parts.forEach(part => {
      const button = make("button",undefined,"part-button" + (state.part && state.part.id === part.id ? " selected" : ""));
      button.type = "button";
      button.setAttribute("aria-current",String(!!state.part && state.part.id === part.id));
      const top = make("div",undefined,"item-top");
      top.append(make("span",part.id),make("span","PART REV. " + display(part.revision)));
      button.append(top,make("strong",part.name),make("small",display(part.equipment_id) + " / " + display(part.line_id)));
      button.addEventListener("click",() => selectPart(part));
      target.append(button);
    });
    sync();
  }
  function renderPart() {
    if (!state.part) return;
    byId("part-id").textContent = display(state.part.id);
    byId("part-revision").textContent = "부품 개정 " + display(state.part.revision);
    byId("part-name").textContent = display(state.part.name);
    byId("part-purpose").textContent = display(state.part.purpose,"검토 목적이 기록되지 않았습니다.");
    byId("equipment").textContent = display(state.part.equipment_id);
    byId("line").textContent = display(state.part.line_id);
  }
  function selectors() {
    ["reference","candidate"].forEach(side => {
      const target = byId(side+"-select");
      target.replaceChildren();
      const role = side === "reference" ? "reference_spec" : "candidate_drawing";
      const options = state.documents.filter(document => document.document_role === role);
      options.sort((a,b) => Number(b.document_revision)-Number(a.document_revision));
      options.forEach(document => {
        const option = make("option",display(document.title) + " · 문서 개정 " + display(document.document_revision) + " / 부품 " + display(document.part_revision));
        option.value = document.id;
        target.append(option);
      });
      if (!options.length) target.append(make("option","접근 가능한 문서 없음"));
      const current = state[side];
      if (current) target.value = current.id;
      else if (options.length) target.value = options[0].id;
    });
  }
  function provenanceEntry(target,label,value) { target.append(make("dt",label),make("dd",display(value))); }
  function renderSource(side, field=null) {
    const source = state[side];
    const content = byId(side+"-original");
    const meta = byId(side+"-meta");
    const provenance = byId(side+"-provenance");
    content.replaceChildren(); meta.replaceChildren(); provenance.replaceChildren();
    byId(side+"-empty").hidden = !!source;
    content.hidden = !source;
    byId(side+"-approval").textContent = !source ? "문서 대기" : source.approval_state === "approved" ? (side === "reference" ? "승인된 기준" : "승인 상태") : source.approval_state === "draft" ? "검토용 초안" : display(source.approval_state);
    byId(side+"-approval").className = "pill" + (source ? " " + (source.approval_state === "approved" ? "approved" : source.approval_state === "draft" ? "draft" : "") : "");
    byId(side+"-span").className = "span-status";
    byId(side+"-span").textContent = "필드의 원문 참조를 선택하면 해당 위치를 확인합니다.";
    if (!source) return;
    meta.append(make("span","부품 개정 " + display(source.part_revision),"pill"),make("span","문서 개정 " + display(source.document_revision),"pill"),make("span","SITE " + display(source.site),"pill"));
    const raw = display(source.content,"");
    const lines = raw.split("\n").map(line => line.endsWith("\r") ? line.slice(0,-1) : line);
    const points = Array.from(raw);
    const validSpan = field && Number.isInteger(field.line) && Number.isInteger(field.span_start) && Number.isInteger(field.span_end) && field.span_start >= 0 && field.span_end >= field.span_start && field.span_end <= points.length && typeof field.quote === "string" && points.slice(field.span_start,field.span_end).join("") === field.quote && lines[field.line-1] === field.quote;
    lines.forEach((text,index) => {
      if (index === lines.length-1 && text === "") return;
      const row = make("span",undefined,"original-line" + (validSpan && index === field.line-1 ? " highlighted" : ""));
      row.append(make("span",index+1,"line-number"));
      const line = make("span",undefined,"line-text");
      line.append(validSpan && index === field.line-1 ? make("mark",text) : document.createTextNode(text || " "));
      row.append(line); content.append(row);
    });
    provenanceEntry(provenance,"문서 ID",source.id);
    provenanceEntry(provenance,"문서 역할",source.document_role);
    provenanceEntry(provenance,"부품 / 개정",display(source.part_number) + " / " + display(source.part_revision));
    provenanceEntry(provenance,"문서 개정",source.document_revision);
    provenanceEntry(provenance,"승인 상태",source.approval_state);
    provenanceEntry(provenance,"읽기 역할",list(source.roles).map(role=>labels.roles[role]||role).join(" · "));
    provenanceEntry(provenance,"추출 상태",labels.extraction[source.extraction_state]||source.extraction_state);
    provenanceEntry(provenance,"검토 상태",source.review_state);
    provenanceEntry(provenance,"서버 원문 SHA-256",source.source_hash);
    if (field) {
      byId(side+"-span").className = "span-status " + (validSpan ? "valid" : "invalid");
      byId(side+"-span").textContent = validSpan ? "✓ 원문 전체 행 일치 · L" + field.line + " / Unicode span [" + field.span_start + ", " + field.span_end + ")" : "원문 행·span을 확인할 수 없습니다. 현재 문서와 검토 기록을 다시 확인하세요.";
      if (validSpan) content.querySelector(".highlighted").scrollIntoView({behavior:"smooth",block:"nearest"});
    }
  }
  function renderPair() {
    const problem = pairProblem();
    byId("pair-status").textContent = problem || "동일 부품 개정 · 승인된 기준 / 후보 초안 유지 · 문서 개정은 역할별로 구분합니다.";
    byId("pair-status").className = problem ? "invalid" : "";
    sync();
  }
  function extractionFor(side) {
    const source = state[side];
    return source && state.comparison ? list(state.comparison.extractions).find(extraction=>extraction.document_id === source.id) : null;
  }
  function fieldCell(side, fieldName, check) {
    const cell = make("div",undefined,"field-cell");
    const extraction = extractionFor(side);
    const field = extraction && extraction.fields && extraction.fields[fieldName];
    const value = field ? field.raw_value : check && check[side+"_value"];
    const missing = value === null || value === undefined || value === "";
    cell.append(make("div",missing ? "정보 없음 · 0으로 해석하지 않음" : display(value),"field-value" + (missing ? " empty" : "")));
    cell.append(make("div",field ? (labels.extraction[field.state] || labels.check[field.state] || display(field.state)) + (field.unit ? " · 선언 단위 " + field.unit : "") : "추출 필드 없음","field-state"));
    if (field && typeof field.quote === "string" && field.quote && Number.isInteger(field.line)) {
      const button = make("button",field.quote,"quote-button");
      button.type = "button";
      button.append(make("small","원문 L" + field.line + " / [" + display(field.span_start) + ", " + display(field.span_end) + ") ↗"));
      button.setAttribute("aria-label",(side === "reference" ? "기준" : "후보") + " " + labels.fields[fieldName] + " 원문 전체 행 확인");
      button.addEventListener("click",()=>showSourceField(side,field));
      cell.append(button);
    } else cell.append(make("div","검증할 전체 원문 행이 없습니다.","field-state"));
    return cell;
  }
  function renderComparison() {
    const comparison = state.comparison;
    byId("result").hidden = !comparison;
    byId("review-section").hidden = !comparison;
    byId("pending").hidden = !state.comparing;
    if (!comparison) { sync(); return; }
    const stale = invalidated(comparison);
    if (stale) {
      state.reference=null; state.candidate=null;
      renderSource("reference"); renderSource("candidate");
    }
    const failed = modelFailed(comparison);
    const verified = comparison.model_state === "source_verified";
    byId("mode-badge").textContent = stale ? "현재 원문 재대조 필요" : failed ? "모델 실패 · 수동 원문 검토" : verified ? "모델 제안 · 문서별 원문 검증" : "규칙 기준선 · 모델 추론 없음";
    byId("mode-badge").style.color = failed || stale ? "var(--red)" : verified ? "var(--amber)" : "var(--green)";
    const match = comparison.overall === "annotations_match" && !failed && !stale;
    byId("overall").textContent = match ? "표기·선언 명목값 일치" : "추가 검토 필요";
    byId("overall").className = "overall" + (match ? " matched" : "");
    byId("comparison-id").textContent = display(comparison.id);
    const coverage = comparison.required_coverage;
    byId("coverage").textContent = coverage && Number.isInteger(coverage.observed) && Number.isInteger(coverage.required) ? "필수 필드 " + coverage.observed + " / " + coverage.required + " 확인" : "필수 필드 3개 · 누락 상태 확인";
    byId("comparison-review-state").textContent = stale ? "원문 변경 · 기록 무효화" : comparison.review_state === "reviewed" ? "확인 기록 있음" : comparison.review_state === "needs_followup" ? "후속 확인 필요" : "검토 대기";
    byId("model-notice").hidden = !(stale || failed || verified);
    byId("model-notice").textContent = stale ? "원문·개정·역할·승인 상태 또는 출처가 변경되었습니다. 과거 필드·인용·검토 결정을 현재 근거로 표시하지 않습니다. 부품을 다시 선택해 현재 원문으로 대조하세요." : failed ? "모델 제안의 검증에 실패했습니다. 아래 원문·필드는 규칙 기반 검사 자료입니다. 검토를 기록하려면 원문을 직접 확인했다는 명시적 확인이 필요합니다." : "기준 문서와 후보 문서를 각각 독립적으로 추출하고 원문 지원을 검증했습니다. 모델이 식별자·해시·승인 상태를 결정하지 않습니다. 공학적 동등성 판단이 아닙니다.";
    const rows = byId("field-rows");
    rows.replaceChildren();
    if (stale) rows.append(make("p","유효하지 않은 대조의 필드와 인용은 표시하지 않습니다.","empty-note"));
    else fieldOrder.forEach(fieldName => {
      const check = list(comparison.checks).find(item=>item.field === fieldName);
      const row = make("div",undefined,"field-row");
      const name = make("div",undefined,"field-name");
      name.append(make("b",labels.fields[fieldName]),make("small",fieldName));
      const outcome = make("div",undefined,"field-outcome");
      const stateName = check ? check.state : "information_missing";
      const matchClass = ["same_notation","same_declared_nominal"].includes(stateName) ? " match" : stateName === "notation_difference" ? " difference" : "";
      outcome.append(make("span",labels.check[stateName] || display(stateName),"status"+matchClass),make("p",check ? display(check.explanation,"추가 원문 확인이 필요합니다.") : "이 필드의 대조 결과가 없습니다. 전체 일치로 해석하지 않습니다."));
      row.append(name,fieldCell("reference",fieldName,check),fieldCell("candidate",fieldName,check),outcome);
      rows.append(row);
    });
    const details = byId("extraction-states");
    details.replaceChildren();
    if (!stale) ["reference","candidate"].forEach(side => {
      const extraction = extractionFor(side);
      const box = make("div",undefined,"extraction-status");
      box.append(make("strong",side === "reference" ? "기준 문서" : "후보 문서"),make("span",state[side] ? state[side].id : "현재 문서 없음"),make("span",extraction ? labels.extraction[extraction.state || extraction.extraction_state] || display(extraction.state || extraction.extraction_state,"원문 검사 자료") : "추출 결과 없음"));
      const metadata = extraction && (extraction.model_metadata || extraction.model || extraction.metrics);
      if (metadata && typeof metadata === "object") {
        const info=[];
        if (typeof metadata.model === "string") info.push(metadata.model);
        if (typeof metadata.latency_ms === "number") info.push("처리 " + Math.round(metadata.latency_ms) + " ms");
        if (info.length) box.append(make("p",info.join(" · ")));
      }
      details.append(box);
    });
    if (comparison.fingerprint && !stale) details.append(make("p","대조 fingerprint / " + display(comparison.fingerprint),"empty-note mono"));
    renderReview();
    sync();
  }
  function renderReview() {
    const comparison = state.comparison;
    if (!comparison) return;
    const reviewer = state.principal && state.principal.role === "reviewer";
    const stale = invalidated(comparison);
    byId("review-permission").textContent = reviewer ? "검토자 · 기록 권한" : "읽기·대조 권한";
    byId("review-form").hidden = !!comparison.review || stale;
    byId("existing-review").hidden = !comparison.review || stale;
    byId("manual-block").hidden = !modelFailed(comparison) || stale;
    if (comparison.review && !stale) {
      const review = comparison.review;
      const label = review.decision === "reviewed" ? "확인 기록됨" : review.decision === "needs_followup" ? "후속 확인 요청 기록됨" : "검토 기록 있음";
      byId("existing-review").replaceChildren(make("strong",label + " · " + date(review.timestamp)));
      if (review.comment) byId("existing-review").append(make("p",review.comment));
      if (review.manual_confirmation === true) byId("existing-review").append(make("p","모델 실패를 확인하고 원문을 직접 검토한 기록입니다. 모델 검증 성공으로 변경되지 않습니다."));
    }
    byId("review-help").textContent = stale ? "현재 출처가 변경되어 이전 대조에는 새 검토를 기록할 수 없습니다." : !reviewer ? "설계·품질 담당은 원문과 대조 결과를 확인할 수 있습니다. 검토 기록은 검토자 프로필이 필요합니다." : comparison.review ? "이 대조 기록에는 결정이 이미 남아 있습니다. 재요청은 같은 기록을 반환합니다." : modelFailed(comparison) ? "모델 실패 상태입니다. 원문·필드를 직접 확인한 후 아래 확인 항목을 체크해야 기록할 수 있습니다." : "표기 차이, 누락, 단위와 미확인 사항을 확인하고 판단 근거를 기록하세요. 설계 승인을 생성하지 않습니다.";
    sync();
  }
  function renderAudit() {
    const target = byId("audit-list");
    target.replaceChildren();
    byId("audit-count").textContent = String(state.events.length);
    if (!state.events.length) target.append(make("p","현재 접근 범위에 검토 이력이 없습니다.","empty-note"));
    list(state.events).slice().reverse().forEach(event => {
      const row = make("div",undefined,"audit-event");
      const description = make("div");
      const action = {comparison_created:"대조 기록 생성", comparison_reviewed:"검토 기록", review_recorded:"검토 기록", comparison_invalidated:"원문 변경 · 대조 무효화"};
      description.append(make("strong",action[event.action] || display(event.action,"작업 기록")));
      const info = [event.comparison_id,event.actor_id ? "담당 " + event.actor_id : "",event.decision === "reviewed" ? "확인 기록" : event.decision === "needs_followup" ? "후속 확인 필요" : "",event.model_state === "failed" ? "모델 실패" : ""].filter(Boolean);
      description.append(make("p",info.join(" · ")));
      if (event.comment) description.append(make("p",event.comment));
      row.append(make("time",date(event.timestamp)),description);
      if (event.comparison_id) {
        const open = make("button","대조 열기 ↗","text-button"); open.type="button";
        open.addEventListener("click",()=>openComparison(event.comparison_id)); row.append(open);
      }
      target.append(row);
    });
    sync();
  }

  async function loadProfiles() {
    try {
      const payload = await request("/api/profiles",{public:true});
      state.profiles = list(payload.profiles);
      byId("profile").replaceChildren();
      state.profiles.forEach(profile => {
        const option = make("option",display(profile.label,"사이트 "+profile.site+" / "+(labels.roles[profile.role]||profile.role)));
        option.value=profile.id; byId("profile").append(option);
      });
      const selected = state.principal && state.principal.id || "A-engineer";
      if (state.profiles.some(profile=>profile.id===selected)) byId("profile").value=selected;
      state.profileReady=state.profiles.length>0;
      if (!state.profileReady) tell("사용 가능한 데모 프로필이 없습니다.","warning");
    } catch (error) { byId("profile").replaceChildren(make("option","프로필 연결 실패")); errorMessage(error); }
    sync();
  }
  async function health() {
    try {
      const payload=await request("/api/health",{public:true});
      byId("health").textContent=payload.ok ? "로컬 워크벤치 연결됨" : "상태 확인 필요";
      byId("health-dot").style.background=payload.ok ? "#97b392" : "#c8ab78";
    } catch (_) { byId("health").textContent="워크벤치 연결 실패"; byId("health-dot").style.background="#c79179"; }
  }
  async function connect() {
    if (state.loading || state.working || !byId("profile").value) return;
    state.loading=true; sync(); tell("데모 세션에 접속하고 있습니다.");
    try {
      const payload=await request("/api/session",{method:"POST",public:true,body:{profile:byId("profile").value}});
      if (typeof payload.token!=="string" || !payload.principal) throw new Error("세션 응답이 올바르지 않습니다.");
      disconnect(); state.loading=true;
      state.token=payload.token; state.principal=payload.principal; save(); renderPrincipal();
      await loadParts();
    } catch (error) { errorMessage(error); }
    finally { state.loading=false; sync(); }
  }
  async function loadParts() {
    const payload=await request("/api/parts");
    state.parts=list(payload.parts); renderParts();
    if (state.parts.length) await selectPart(state.parts[0],true);
    else tell("현재 사이트에서 접근 가능한 부품이 없습니다.","warning");
  }
  async function selectPart(part, initial=false) {
    if (state.working || state.loading && !initial) return;
    cancelReads();
    const generation=++state.generation;
    Object.assign(state,{part,documents:[],reference:null,candidate:null,comparison:null,events:[],loading:true});
    byId("manual-confirmation").checked=false; byId("review-comment").value="";
    byId("welcome").hidden=true; byId("work").hidden=false;
    renderParts(); renderPart(); selectors(); renderSource("reference"); renderSource("candidate"); renderPair(); renderComparison(); renderAudit();
    tell("부품과 최신 접근 가능한 문서를 불러오고 있습니다.");
    try {
      const results=await Promise.allSettled([request("/api/parts/"+encodeURIComponent(part.id)),request("/api/audit?part_number="+encodeURIComponent(part.id))]);
      if (generation!==state.generation) return;
      let error=null;
      if (results[0].status==="fulfilled") {
        state.part=results[0].value.part; state.documents=list(results[0].value.documents);
        renderPart(); selectors();
        const sourceError=await loadPair(generation);
        if (generation!==state.generation) return;
        error=sourceError||error;
      } else error=results[0].reason;
      if (results[1].status==="fulfilled") { state.events=list(results[1].value.events); renderAudit(); }
      else error=error||results[1].reason;
      if (error) errorMessage(error); else tell("");
    } catch (error) { if (generation===state.generation) errorMessage(error); }
    finally { if (generation===state.generation) { state.loading=false; renderParts(); renderPair(); sync(); } }
  }
  async function loadPair(generation=state.generation) {
    const choices=["reference","candidate"].map(side=>({side,id:byId(side+"-select").value}));
    state.sourceBusy=true;
    state.reference=null; state.candidate=null;
    renderSource("reference"); renderSource("candidate"); renderPair(); sync();
    try {
      const results=await Promise.allSettled(choices.map(choice=>choice.id ? request("/api/documents/"+encodeURIComponent(choice.id)) : Promise.resolve({document:null})));
      if (generation!==state.generation) return;
      let error=null;
      results.forEach((result,index)=>{
        if (result.status==="fulfilled") { state[choices[index].side]=result.value.document; renderSource(choices[index].side); }
        else error=error||result.reason;
      });
      if (error) errorMessage(error);
      return error;
    } finally { state.sourceBusy=false; renderPair(); sync(); }
  }
  async function changeSources() {
    if (state.working || state.loading || state.sourceBusy) return;
    state.comparison=null; byId("manual-confirmation").checked=false; byId("review-comment").value="";
    renderComparison(); await loadPair(); renderPair();
  }
  async function compare() {
    if (state.working || state.loading || state.sourceBusy || pairProblem() || !state.token) return;
    const generation=state.generation;
    const mode=document.querySelector('input[name="mode"]:checked').value;
    state.working=true; state.comparing=true; state.comparison=null;
    byId("manual-confirmation").checked=false; byId("review-comment").value="";
    renderSource("reference"); renderSource("candidate"); renderComparison();
    byId("compare").firstElementChild.textContent=" 대조 중…";
    sync();
    tell(mode==="model" ? "기준·후보 원문을 각각 독립적으로 추출하도록 실제 모델에 요청했습니다." : "규칙 기준선으로 원문 표기를 대조합니다. 모델 추론은 사용하지 않습니다.");
    try {
      const payload=await request("/api/parts/"+encodeURIComponent(state.part.id)+"/compare",{method:"POST",timeout:180000,body:{reference_id:state.reference.id,candidate_id:state.candidate.id,mode}});
      if (generation!==state.generation) return;
      if (!payload.comparison || !payload.comparison.id) throw new Error("대조 응답이 올바르지 않습니다.");
      state.comparison=payload.comparison; renderComparison();
      tell(modelFailed(state.comparison) ? "모델 검증에 실패했습니다. 원문 기반 수동 검토 상태를 확인해 주세요." : "대조 기록이 생성되었습니다. 전체 원문 행과 미확인 항목을 검토하세요.",modelFailed(state.comparison) ? "warning" : "");
      await refreshAudit(true);
    } catch (error) { if (generation===state.generation) { errorMessage(error); if(error.timeout) await refreshAudit(true); } }
    finally { state.working=false; state.comparing=false; byId("pending").hidden=true; byId("compare").firstElementChild.textContent="사양 대조"; renderComparison(); sync(); }
  }
  async function showSourceField(side,field) {
    if (state.sourceBusy || state.loading || !state[side] || invalidated(state.comparison)) return;
    const generation=state.generation, previous=state[side];
    state.sourceBusy=true; sync();
    try {
      const payload=await request("/api/documents/"+encodeURIComponent(previous.id));
      if (generation!==state.generation) return;
      const current=payload.document;
      if (!current || current.source_hash!==previous.source_hash || current.document_revision!==previous.document_revision || current.part_revision!==previous.part_revision) {
        state[side]=current||null; renderSource(side);
        state.comparison={id:state.comparison.id,target_part:state.part.id,stale:true,review_state:"invalidated",status:"invalidated",checks:[],extractions:[],overall:"needs_review",review:null};
        renderComparison(); throw new Error("원문 출처가 변경되었습니다. 현재 원문으로 다시 대조해 주세요.");
      }
      state[side]=current; renderSource(side,field);
      byId(side+"-original").scrollIntoView({behavior:"smooth",block:"nearest"});
    } catch (error) {
      if (generation===state.generation) {
        if(error.status===403 || error.status===404) {
          state[side]=null; renderSource(side);
          if(state.comparison) state.comparison={id:state.comparison.id,stale:true,review_state:"invalidated",checks:[],extractions:[],overall:"needs_review",review:null};
          renderComparison();
        }
        errorMessage(error);
      }
    } finally { state.sourceBusy=false; sync(); }
  }
  async function openComparison(id) {
    if (state.working || state.loading || !state.part) return;
    const generation=state.generation;
    state.loading=true; state.comparison=null; renderComparison(); sync();
    byId("manual-confirmation").checked=false; byId("review-comment").value="";
    try {
      const payload=await request("/api/comparisons/"+encodeURIComponent(id));
      if (generation!==state.generation) return;
      const comparison=payload.comparison;
      if(!comparison || partId(comparison.target_part)!==state.part.id) throw new Error("현재 부품의 대조 기록을 찾을 수 없습니다.");
      if (!invalidated(comparison)) {
        const referenceId=docId(comparison.reference),candidateId=docId(comparison.candidate);
        if(referenceId) byId("reference-select").value=referenceId;
        if(candidateId) byId("candidate-select").value=candidateId;
        const sourceError=await loadPair(generation);
        if (sourceError) throw sourceError;
      } else { renderSource("reference"); renderSource("candidate"); }
      if (generation!==state.generation) return;
      state.comparison=comparison; renderComparison();
      tell(invalidated(comparison) ? "이전 대조가 무효화되었습니다. 현재 원문으로 다시 대조해 주세요." : "",invalidated(comparison) ? "warning" : "");
      byId("result").scrollIntoView({behavior:"smooth",block:"start"});
    } catch (error) { if(generation===state.generation) errorMessage(error); }
    finally { state.loading=false; sync(); }
  }
  async function refreshAudit(quiet=false) {
    if (!state.part || !state.token || state.auditBusy) return;
    const generation=state.generation;
    state.auditBusy=true; sync();
    try {
      const payload=await request("/api/audit?part_number="+encodeURIComponent(state.part.id));
      if(generation!==state.generation) return;
      state.events=list(payload.events); renderAudit();
      if(!quiet) tell("현재 접근 범위의 검토 이력을 갱신했습니다.");
    } catch(error) { if(generation===state.generation && !quiet) errorMessage(error); }
    finally { state.auditBusy=false; sync(); }
  }
  async function review(decision) {
    if(state.working || state.loading || state.sourceBusy || !state.comparison || state.comparison.review || invalidated(state.comparison) || !state.principal || state.principal.role!=="reviewer") return;
    if(modelFailed(state.comparison) && !byId("manual-confirmation").checked) { tell("모델 실패 후에는 원문을 직접 검토했다는 명시적 확인이 필요합니다.","warning"); return; }
    const generation=state.generation,id=state.comparison.id;
    state.working=true; sync(); tell("검토 확인 기록을 저장하고 있습니다.");
    try {
      const payload=await request("/api/comparisons/"+encodeURIComponent(id)+"/review",{method:"POST",body:{decision,comment:byId("review-comment").value.trim(),manual_confirmation:byId("manual-confirmation").checked}});
      if(generation!==state.generation) return;
      state.comparison.review=payload.review;
      if(payload.review) state.comparison.review_state=payload.review.decision;
      renderComparison();
      tell(payload.duplicate ? "기존 검토 기록을 표시했습니다. 새 결정은 중복 생성되지 않았습니다." : "검토 기록이 저장되었습니다. 후보 문서의 설계 승인으로 변경되지 않습니다.");
      await refreshAudit(true);
    } catch(error) {
      if(generation===state.generation) {
        errorMessage(error);
        if(error.status===409 || error.timeout) {
          try {
            const payload=await request("/api/comparisons/"+encodeURIComponent(id));
            if(generation===state.generation) { state.comparison=payload.comparison; renderComparison(); }
          } catch(_) { /* Reconcile uncertain state using reads only; never repeat a write. */ }
        }
      }
    } finally { state.working=false; byId("pending").hidden=true; renderComparison(); sync(); }
  }

  byId("profile").addEventListener("change",sync);
  byId("connect").addEventListener("click",connect);
  byId("reference-select").addEventListener("change",changeSources);
  byId("candidate-select").addEventListener("change",changeSources);
  byId("compare").addEventListener("click",compare);
  byId("manual-confirmation").addEventListener("change",sync);
  byId("review-form").addEventListener("submit",event=>{event.preventDefault(); review("reviewed");});
  byId("followup").addEventListener("click",()=>review("needs_followup"));
  byId("refresh-audit").addEventListener("click",()=>refreshAudit());
  restore(); renderPrincipal();
  Promise.allSettled([loadProfiles(),health()]).then(async()=>{
    if(state.token) {
      state.loading=true; sync();
      try { await loadParts(); }
      catch(error) { errorMessage(error); }
      finally { state.loading=false; sync(); }
    }
  });
})();