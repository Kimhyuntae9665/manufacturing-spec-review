"""Small serial actual-model check; synthetic documents only, no gold in prompts."""
import json,subprocess,time,threading,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:19081"
def req(path,body=None,token=None):
 headers={"Content-Type":"application/json"}
 if token:headers["Authorization"]="Bearer "+token
 data=None if body is None else json.dumps(body).encode()
 with urllib.request.urlopen(urllib.request.Request(BASE+path,data=data,headers=headers),timeout=150) as response:return json.load(response)
def main():
 samples=[];stop=threading.Event();started=time.monotonic()
 def sample():
  while not stop.is_set():
   gpu=subprocess.run(["nvidia-smi","--query-gpu=memory.used,utilization.gpu","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=3)
   mem={}
   for line in Path("/proc/meminfo").read_text().splitlines():
    key,rest=line.split(":",1)
    if key in ("MemTotal","MemAvailable"):mem[key+"_kib"]=int(rest.strip().split()[0])
   samples.append({"elapsed_s":round(time.monotonic()-started,3),"gpu_csv":gpu.stdout.strip(),"ram":mem})
   stop.wait(.3)
 thread=threading.Thread(target=sample);thread.start()
 outcomes=[]
 try:
  for part,ref,candidate,site in (("P001","SRC-001","SRC-002","A"),("P002","SRC-003","SRC-004","A"),("P003","SRC-005","SRC-006","B")):
   token=req("/api/session",{"profile":site+"-reviewer"})["token"]
   result=req("/api/parts/"+part+"/compare",{"reference_id":ref,"candidate_id":candidate,"mode":"model"},token)["comparison"]
   outcomes.append({"part":part,"result":result})
   print(json.dumps({"part":part,"model_state":result["model_state"],"overall":result["overall"],"metrics":result["metrics"]},ensure_ascii=False),flush=True)
   # A timeout or any model failure ends this run; no automatic repeat.
   if result["model_state"]!="source_verified":break
 finally:stop.set();thread.join(timeout=4)
 artifact={"scope":"3 fixed synthetic development pairs; not heldout or expert validation","synthetic":True,"request_strategy":"one document at a time, two independent calls per pair","outcomes":outcomes,"resource_samples":samples,"elapsed_s":time.monotonic()-started,"peak_vram_mib":max(int(x["gpu_csv"].split(",")[0]) for x in samples)}
 out=ROOT/"artifacts"/("live-model-pairs-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+".json")
 out.write_text(json.dumps(artifact,ensure_ascii=False,indent=2))
 print(json.dumps({"artifact":out.name,"pairs":len(outcomes),"source_verified":sum(x["result"]["model_state"]=="source_verified" for x in outcomes),"peak_vram_mib":artifact["peak_vram_mib"],"elapsed_s":artifact["elapsed_s"]}),flush=True)
 return 0 if len(outcomes)==3 and all(x["result"]["model_state"]=="source_verified" for x in outcomes) else 1
if __name__=="__main__":raise SystemExit(main())
