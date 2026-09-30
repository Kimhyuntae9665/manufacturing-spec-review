"""Actual sandboxed-Chrome UI checks for synthetic manufacturing notation review.

This driver uses only loopback CDP and the project API. Comparisons triggered by this driver are
baseline-only; stored root-owned real-model results can be opened read-only. The failed-model checkbox case is a browser-response mock over
a real baseline comparison and is explicitly labelled in the page/artifact.
No actual model request is made.
"""
import argparse
import base64
import json
import os
import socket
import subprocess
import struct
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
APP = "http://127.0.0.1:19081"
DEBUG = "http://127.0.0.1:19085"


class Browser:
    """Small independently written RFC6455/CDP transport; no browser packages."""
    def __init__(self, address):
        location = urlsplit(address)
        self.connection = socket.create_connection((location.hostname,location.port),timeout=30)
        self.serial = 0
        self.frame_callback = None
        nonce = base64.b64encode(os.urandom(16)).decode("ascii")
        handshake = (
            f"GET {location.path} HTTP/1.1\r\nHost: {location.netloc}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.connection.sendall(handshake.encode("ascii"))
        response = bytearray()
        while not response.endswith(b"\r\n\r\n"):
            response.extend(self.read(1))
        if not bytes(response).startswith(b"HTTP/1.1 101"):
            raise RuntimeError("Chrome did not accept a local CDP WebSocket")
    def read(self, length):
        result = bytearray()
        while len(result)<length:
            fragment = self.connection.recv(length-len(result))
            if not fragment:
                raise RuntimeError("Chrome CDP connection ended")
            result.extend(fragment)
        return bytes(result)
    def frame(self, payload, opcode=1):
        size = len(payload)
        mask = os.urandom(4)
        prefix = bytes((0x80|opcode,0x80|size)) if size<126 else bytes((0x80|opcode,0x80|126))+struct.pack("!H",size) if size<65536 else bytes((0x80|opcode,0x80|127))+struct.pack("!Q",size)
        masked = bytes(byte^mask[index%4] for index,byte in enumerate(payload))
        self.connection.sendall(prefix+mask+masked)
    def message(self):
        chunks=[]
        while True:
            flags, length_byte = self.read(2)
            length=length_byte&0x7f
            if length==126:length=struct.unpack("!H",self.read(2))[0]
            elif length==127:length=struct.unpack("!Q",self.read(8))[0]
            mask=self.read(4) if length_byte&0x80 else None
            payload=self.read(length)
            if mask:payload=bytes(byte^mask[index%4] for index,byte in enumerate(payload))
            opcode=flags&0x0f
            if opcode==8:raise RuntimeError("Chrome closed CDP")
            if opcode==9:self.frame(payload,10);continue
            chunks.append(payload)
            if flags&0x80:return json.loads(b"".join(chunks).decode("utf-8"))
    def command(self, method, **parameters):
        self.serial+=1
        identity=self.serial
        self.frame(json.dumps({"id":identity,"method":method,"params":parameters},separators=(",",":")).encode("utf-8"))
        while True:
            result=self.message()
            if result.get("method")=="Page.screencastFrame":
                parameters=result["params"]
                if self.frame_callback:self.frame_callback(parameters)
                self.serial+=1
                self.frame(json.dumps({"id":self.serial,"method":"Page.screencastFrameAck","params":{"sessionId":parameters["sessionId"]}}).encode("utf-8"))
            if result.get("id")==identity:
                if result.get("error"):raise RuntimeError(result["error"])
                return result.get("result",{})
    def js(self, expression):
        reply=self.command("Runtime.evaluate",expression=expression,awaitPromise=True,returnByValue=True)
        if "exceptionDetails" in reply:raise RuntimeError(reply["exceptionDetails"].get("text","Browser evaluation failed"))
        return reply.get("result",{}).get("value")
    def until(self, condition, seconds=20):
        timeout=int(seconds*1000)
        script=f"(async()=>{{const end=Date.now()+{timeout};while(Date.now()<end){{if({condition})return true;await new Promise(done=>setTimeout(done,100));}}throw new Error('UI wait expired');}})()"
        return self.js(script)


def connect():
    with urllib.request.urlopen(DEBUG+"/json",timeout=10) as response:
        pages=json.load(response)
    address=next(page["webSocketDebuggerUrl"] for page in pages if page["type"]=="page")
    browser=Browser(address)
    browser.command("Page.enable")
    browser.command("Runtime.enable")
    return browser


def login(browser, profile):
    browser.until("!document.querySelector('#connect').disabled")
    browser.js("document.querySelector('#profile').value="+json.dumps(profile)+";document.querySelector('#profile').dispatchEvent(new Event('change'));document.querySelector('#connect').click()")
    expected=2 if profile.startswith("A-") else 1
    label="검토자" if profile.endswith("reviewer") else "설계·품질 담당"
    browser.until("document.querySelector('#principal').textContent.includes("+json.dumps(label)+") && document.querySelector('#part-count').textContent==="+json.dumps(str(expected))+" && !document.querySelector('#compare').disabled")


def select(browser, identifier):
    browser.js("Array.from(document.querySelectorAll('.part-button')).find(button=>button.textContent.includes("+json.dumps(identifier)+")).click()")
    browser.until("document.querySelector('#part-id').textContent==="+json.dumps(identifier)+" && !document.querySelector('#compare').disabled")


def compare(browser, mode="baseline"):
    old=browser.js("document.querySelector('#comparison-id').textContent")
    browser.js("document.querySelector('input[name=mode][value="+mode+"]').checked=true;document.querySelector('#compare').click()")
    browser.until("!document.querySelector('#result').hidden && !document.querySelector('#compare').disabled && document.querySelector('#comparison-id').textContent!=="+json.dumps(old))
    return browser.js("document.querySelector('#comparison-id').textContent")


def screenshot(browser, directory, filename, purpose, screenshots):
    page=browser.js("({part:document.querySelector('#part-id').textContent,profile:document.querySelector('#principal').textContent,mode:document.querySelector('#mode-badge').textContent,overall:document.querySelector('#overall').textContent,overflow:document.documentElement.scrollWidth>window.innerWidth,text:document.body.textContent})")
    private=[str(Path.home()),os.environ.get("USER","")]
    assert not any(marker and marker in page["text"] for marker in private),"Private path/account in rendered page"
    assert "Bearer " not in page["text"],"Authentication value in rendered page"
    page.pop("text")
    capture=browser.command("Page.captureScreenshot",format="png",captureBeyondViewport=False)
    (directory/filename).write_bytes(base64.b64decode(capture["data"]))
    screenshots.append({"file":filename,"purpose":purpose,"actual_browser":True,"synthetic":True,**page})
    print(json.dumps({"captured":filename,"part":page["part"]},ensure_ascii=False),flush=True)


def record_video(browser, output):
    """Keep native viewport frames and their acquisition timestamps, without overlays."""
    output.mkdir(parents=True,exist_ok=True)
    frames=output/"frames"
    frames.mkdir(exist_ok=True)
    captured=[]
    scenes=[]
    def receive(parameters):
        filename=f"frame-{len(captured)+1:06d}.jpg"
        (frames/filename).write_bytes(base64.b64decode(parameters["data"]))
        captured.append({"file":"frames/"+filename,"timestamp":parameters["metadata"]["timestamp"],"metadata":parameters["metadata"]})
    def hold(label):
        page=browser.js("({text:document.body.textContent,part:document.querySelector('#part-id').textContent})")
        assert "Bearer " not in page["text"]
        assert not any(marker and marker in page["text"] for marker in (str(Path.home()),os.environ.get("USER","")))
        scenes.append({"label":label,"part":page["part"],"timestamp":time.time()})
        browser.js("new Promise(done=>setTimeout(done,1600))")
    login(browser,"A-reviewer")
    select(browser,"P001")
    compare(browser)
    browser.js("document.querySelector('.source-grid').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
    browser.frame_callback=receive
    started=time.time()
    browser.command("Page.startScreencast",format="jpeg",quality=90,maxWidth=1600,maxHeight=1200,everyNthFrame=1)
    try:
        hold("P001 approved reference and draft candidate original text")
        select(browser,"P002")
        compare(browser)
        browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        hold("P002 whole material code notation difference")
        login(browser,"B-reviewer")
        select(browser,"P003")
        compare(browser)
        browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        hold("P003 finish difference and missing thickness")
        login(browser,"A-reviewer")
        select(browser,"P002")
        identifier="00e8f204d4be46f9b2e3e4b77113d8a1"
        browser.js("Array.from(document.querySelectorAll('#audit-list .audit-event')).find(row=>row.textContent.includes("+json.dumps(identifier)+")).querySelector('button').click()")
        browser.until("document.querySelector('#comparison-id').textContent==="+json.dumps(identifier)+" && !document.querySelector('#compare').disabled")
        assert browser.js("document.querySelector('#mode-badge').textContent.includes('문서별 원문 검증')")
        browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        hold("Read existing actual model P002 result; GET only")
        browser.js("document.querySelectorAll('#field-rows .quote-button')[1].click()")
        browser.until("document.querySelector('#candidate-span').textContent.includes('전체 행 일치')")
        browser.js("document.querySelector('.source-grid').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        hold("Candidate whole original line and Unicode span highlight")
    finally:
        ended=time.time()
        browser.command("Page.stopScreencast")
        browser.frame_callback=None
    assert len(captured)>5,"Chrome delivered insufficient native frames"
    assert all(right["timestamp"]>=left["timestamp"] for left,right in zip(captured,captured[1:])),"Native frame timestamps moved backwards"
    listing=[]
    for index,frame in enumerate(captured):
        next_timestamp=captured[index+1]["timestamp"] if index+1<len(captured) else ended
        duration=next_timestamp-frame["timestamp"]
        assert duration>=0
        listing.append("file '"+frame["file"]+"'")
        listing.append(f"duration {duration:.9f}")
    listing.append("file '"+captured[-1]["file"]+"'")
    (output/"native-frames.ffconcat").write_text("\n".join(listing)+"\n",encoding="utf-8")
    manifest={"actual_browser":True,"synthetic":True,"new_model_requests":0,"mock_cases":False,"audio":"silent","record_started":started,"record_ended":ended,"stored_model_comparison":identifier,"scenes":scenes,"frames":captured,"encoding":"native frame order and acquisition timestamps; even-dimension padding only"}
    (output/"native-frames.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    # Reconstruct PTS from native metadata. Older FFmpeg concat inputs quantize
    # JPEG timestamps to 25fps; explicit setpts keeps all native frames in order.
    origin=captured[0]["timestamp"]
    times=[frame["timestamp"]-origin for frame in captured]+[ended-origin]
    (frames/f"frame-{len(captured)+1:06d}.jpg").write_bytes((output/captured[-1]["file"]).read_bytes())
    expression=f"{times[-1]:.9f}/TB"
    for index in reversed(range(len(times)-1)):
        expression=f"if(eq(N,{index}),{times[index]:.9f}/TB,{expression})"
    expression=expression.replace(",","\\,")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate","1000","-i","frames/frame-%06d.jpg","-vf","settb=1/1000000,setpts="+expression+",pad=ceil(iw/2)*2:ceil(ih/2)*2","-vsync","0","-enc_time_base","1:1000000","-c:v","libx264","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart","nota-workflow.mp4"],cwd=output,check=True)
    probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_name,width,height,nb_frames","-of","json",str(output/"nota-workflow.mp4")]))
    assert 8<=float(probe["format"]["duration"])<=15,probe
    (output/"probe.json").write_text(json.dumps(probe,indent=2),encoding="utf-8")
    print(json.dumps({"video":str(output.relative_to(ROOT)/"nota-workflow.mp4"),"native_frames":len(captured),"duration":probe["format"]["duration"],"new_model_requests":0,"actual_browser":True}),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="artifacts/browser-check")
    parser.add_argument("--record-video",action="store_true")
    parser.add_argument("--stored-comparison",help="Read an existing root-owned comparison; never infer")
    parser.add_argument("--stored-part",default="P001")
    parser.add_argument("--stored-profile",default="A-reviewer")
    parser.add_argument("--stored-filename",default="stored-comparison.png")
    parser.add_argument("--expected-model-state",choices=("failed","source_verified"))
    args=parser.parse_args()
    output=ROOT/args.output
    output.mkdir(parents=True,exist_ok=True)
    browser=connect()
    screenshots=[]
    results={"actual_browser":True,"synthetic":True,"real_model_requests":0,"mock_failure_case":True,"screenshots":screenshots}
    try:
        browser.command("Emulation.setDeviceMetricsOverride",width=1600,height=1200,deviceScaleFactor=1,mobile=False)
        browser.command("Page.navigate",url=APP)
        browser.until("document.querySelectorAll('#profile option').length===4 && !document.querySelector('#connect').disabled")
        if args.record_video:
            record_video(browser,output)
            return
        if args.stored_comparison:
            login(browser,args.stored_profile)
            select(browser,args.stored_part)
            browser.js("Array.from(document.querySelectorAll('#audit-list .audit-event')).find(row=>row.textContent.includes("+json.dumps(args.stored_comparison)+")).querySelector('button').click()")
            browser.until("document.querySelector('#comparison-id').textContent==="+json.dumps(args.stored_comparison)+" && !document.querySelector('#compare').disabled")
            mode=browser.js("document.querySelector('#mode-badge').textContent")
            if args.expected_model_state=="failed":
                assert "모델 실패" in mode
                assert browser.js("!document.querySelector('#manual-block').hidden && document.querySelector('#reviewed').disabled && document.querySelector('#followup').disabled")
                purpose="실제 모델 검증 실패 결과를 읽기 전용으로 재조회: 명시적인 원문 수동 확인 필요"
            else:
                assert "문서별 원문 검증" in mode
                purpose="부모가 실행한 실제 모델의 정형 제안을 읽기 전용으로 재조회: 표기 대조이며 공학 판정 아님"
            browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
            screenshot(browser,output,args.stored_filename,purpose,screenshots)
            stored_result={"actual_browser":True,"synthetic":True,"new_model_requests":0,"read_only_stored_comparison":args.stored_comparison,"expected_model_state":args.expected_model_state,"screenshots":screenshots}
            (output/(Path(args.stored_filename).stem+".json")).write_text(json.dumps(stored_result,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps({key:value for key,value in stored_result.items() if key!="screenshots"},ensure_ascii=False),flush=True)
            return
        # Probe logs only endpoint/method, never session headers or response tokens.
        browser.js("""window.__notaProbe={calls:[],mockFailure:false};window.__notaOriginalFetch=window.fetch.bind(window);window.fetch=async function(path,options={}){const item={path:String(path),method:options.method||'GET'};window.__notaProbe.calls.push(item);let rewritten=options;if(window.__notaProbe.mockFailure&&String(path).endsWith('/compare')&&options.body){const body=JSON.parse(options.body);if(body.mode==='model'){body.mode='baseline';rewritten={...options,body:JSON.stringify(body)};item.browserFailureMock=true;}}const response=await window.__notaOriginalFetch(path,rewritten);if(item.browserFailureMock&&response.ok){const payload=await response.json();payload.comparison.mode='model';payload.comparison.model_state='failed';payload.comparison.status='pending_manual_review';payload.comparison.metrics={...payload.comparison.metrics,ui_failure_mock:true};return new Response(JSON.stringify(payload),{status:200,headers:{'Content-Type':'application/json'}});}return response;};""")
        login(browser,"A-engineer")
        select(browser,"P001")
        assert browser.js("document.querySelector('#reference-approval').textContent.includes('승인') && document.querySelector('#candidate-approval').textContent.includes('초안')")
        browser.js("document.querySelectorAll('.provenance').forEach(details=>details.open=true)")
        screenshot(browser,output,"01-reference-candidate-provenance.png","승인된 기준·초안 후보, 부품/문서 개정과 서버 원문 해시",screenshots)
        compare(browser)
        assert browser.js("document.querySelector('#overall').textContent.includes('일치')")
        assert browser.js("document.querySelector('#field-rows').textContent.includes('0.010 mm') && !document.querySelector('#field-rows').textContent.includes('mm mm')")
        assert browser.js("document.querySelector('#reviewed').disabled && document.querySelector('#followup').disabled")
        browser.js("document.querySelector('.quote-button').click()")
        browser.until("document.querySelector('#reference-span').textContent.includes('전체 행 일치') && document.querySelectorAll('#reference-original mark').length===1")
        browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        screenshot(browser,output,"02-declared-nominal-conversion.png","0.010 mm와10 µm의 선언 명목 환산·원문 필드",screenshots)
        results["p001_nominal_same"]=True
        results["engineer_write_disabled"]=True
        results["whole_original_line_highlight"]=True

        select(browser,"P002")
        compare(browser)
        assert browser.js("document.querySelector('#field-rows').textContent.includes('SUS304L') && document.querySelector('#field-rows').textContent.includes('표기 차이')")
        browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        screenshot(browser,output,"03-material-notation-difference.png","SUS304와SUS304L 전체 코드 표기 차이",screenshots)
        results["p002_material_difference"]=True

        login(browser,"B-reviewer")
        select(browser,"P003")
        compare(browser)
        assert browser.js("document.querySelector('#field-rows').textContent.includes('정보 누락') && document.querySelector('#overall').textContent.includes('추가 검토')")
        assert browser.js("document.querySelector('#field-rows').textContent.includes('ZN_NI') && document.querySelector('#field-rows').textContent.includes('NI')")
        browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        screenshot(browser,output,"04-finish-difference-missing-thickness.png","표면처리 차이·누락 두께를0으로 해석하지 않음",screenshots)
        results["p003_missing_and_difference"]=True

        login(browser,"A-reviewer")
        select(browser,"P002")
        reviewed_id=compare(browser)
        browser.js("document.querySelector('#review-comment').value='합성 브라우저 검토: 재질 표기가 다르므로 후속 확인이 필요합니다. 설계 승인이 아닙니다.';document.querySelector('#followup').click()")
        browser.until("document.querySelector('#existing-review').textContent.includes('후속 확인 요청 기록됨') && !document.querySelector('#compare').disabled")
        before=browser.js("window.__notaProbe.calls.filter(item=>item.path.endsWith('/review')).length")
        browser.js("document.querySelector('#followup').click();document.querySelector('#reviewed').click()")
        after=browser.js("window.__notaProbe.calls.filter(item=>item.path.endsWith('/review')).length")
        assert before==after,"UI repeated a stored review mutation"
        assert browser.js("document.querySelector('#candidate-approval').textContent.includes('초안')"),"Acknowledgement changed candidate approval state"
        browser.js("document.querySelector('#review-section').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        screenshot(browser,output,"05-followup-record-and-audit.png","후속 확인 기록·감사 이력; 후보는초안 유지",screenshots)
        results["review_not_design_approval"]=True
        results["duplicate_write_blocked"]=True
        results["reviewed_comparison_id"]=reviewed_id

        select(browser,"P001")
        browser.js("window.__notaProbe.mockFailure=true")
        compare(browser,"model")
        browser.js("document.querySelector('#model-notice').prepend(document.createTextNode('UI 회귀용 모의 모델 실패 · 실제 모델 요청 없음. '))")
        assert browser.js("!document.querySelector('#manual-block').hidden && document.querySelector('#reviewed').disabled && document.querySelector('#followup').disabled")
        browser.js("document.querySelector('#manual-confirmation').checked=true;document.querySelector('#manual-confirmation').dispatchEvent(new Event('change'))")
        assert browser.js("!document.querySelector('#reviewed').disabled && !document.querySelector('#followup').disabled")
        browser.js("document.querySelector('#result').scrollIntoView({block:'start'});window.scrollBy(0,-20)")
        screenshot(browser,output,"06-mock-failure-manual-confirmation.png","브라우저 응답 모의 실패·실제 모델 요청0회·직접 원문 확인 체크",screenshots)
        results["mock_failure_manual_checkbox_required"]=True
        browser.js("window.__notaProbe.mockFailure=false;window.fetch=window.__notaOriginalFetch")
        compare(browser,"baseline")
        browser.command("Emulation.setDeviceMetricsOverride",width=390,height=1100,deviceScaleFactor=1,mobile=True)
        browser.js("document.querySelector('#main').scrollIntoView({block:'start'})")
        screenshot(browser,output,"07-mobile-source-workspace.png","모바일 원문 검토와 가로 넘침 검사",screenshots)
        assert not screenshots[-1]["overflow"],"Mobile horizontal overflow"
        results["passed"]=True
        (output/"result.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({key:value for key,value in results.items() if key!="screenshots"},ensure_ascii=False),flush=True)
    finally:
        try:browser.js("if(window.__notaOriginalFetch)window.fetch=window.__notaOriginalFetch")
        except Exception:pass
        browser.connection.close()


if __name__=="__main__":
    main()
