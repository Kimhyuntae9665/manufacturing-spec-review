import json,subprocess
from pathlib import Path
p=Path("artifacts/ui-video")
m=json.loads((p/"native-frames.json").read_text())
captured=m["frames"]
frames=p/"frames"
origin=captured[0]["timestamp"]
times=[f["timestamp"]-origin for f in captured]+[m["record_ended"]-origin]
(frames/f"frame-{len(captured)+1:06d}.jpg").write_bytes((p/captured[-1]["file"]).read_bytes())
expression=f"{times[-1]:.9f}/TB"
for i in reversed(range(len(times)-1)):
    expression=f"if(eq(N,{i}),{times[i]:.9f}/TB,{expression})"
expression=expression.replace(",","\\,")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate","1000","-i","frames/frame-%06d.jpg","-vf","settb=1/1000000,setpts="+expression+",pad=ceil(iw/2)*2:ceil(ih/2)*2","-vsync","0","-enc_time_base","1:1000000","-c:v","libx264","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart","nota-workflow.mp4"],cwd=p,check=True)
probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_name,width,height,nb_frames","-of","json",str(p/"nota-workflow.mp4")]))
(p/"probe.json").write_text(json.dumps(probe,indent=2))
print(json.dumps(probe))
