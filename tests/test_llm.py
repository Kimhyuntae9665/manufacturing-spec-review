import unittest
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch
from spec_review import llm
class ModelPolicyTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.lock_root=Path(temporary.name)
        lease_patch=patch.object(llm,"INFERENCE_LOCK",self.lock_root/"inference.lock")
        lease_patch.start()
        self.addCleanup(lease_patch.stop)
    def test_single_flight_rejects_without_queue(self):
        llm._lock.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError,"inference_busy"):llm.request_json([],{})
        finally:llm._lock.release()
    def test_cross_process_inference_lease_blocks_duplicate(self):
        import tempfile,subprocess,sys
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            lock=Path(temp)/"inference.lock"
            script="import fcntl,sys;f=open(sys.argv[1],\"a\");fcntl.flock(f,fcntl.LOCK_EX);print(\"ready\",flush=True);sys.stdin.read()"
            process=subprocess.Popen([sys.executable,"-c",script,str(lock)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(),"ready")
                with patch.object(llm,"INFERENCE_LOCK",lock),patch.object(llm.urllib.request,"urlopen") as call,self.assertRaisesRegex(RuntimeError,"inference_busy"):llm.request_json([],{})
                call.assert_not_called()
            finally:
                process.stdin.close();process.wait(timeout=5);process.stdout.close()
    def test_default_lock_same_for_shallow_and_deep_clones(self):
        import importlib.util
        source=Path(llm.__file__).read_text(encoding="utf-8")
        home=self.lock_root/"user"
        paths=[]
        for relative in ("clone/workbench/llm.py","very/deep/projects/clone/workbench/llm.py"):
            clone=self.lock_root/relative
            clone.parent.mkdir(parents=True)
            clone.write_text(source,encoding="utf-8")
            spec=importlib.util.spec_from_file_location("clone_client",clone)
            module=importlib.util.module_from_spec(spec)
            with patch.dict(os.environ,{},clear=True),patch.object(Path,"home",return_value=home):
                spec.loader.exec_module(module)
            paths.append(module.INFERENCE_LOCK)
        self.assertEqual(paths[0],paths[1])
        self.assertEqual(paths[0],home/".cache/ax-lab/runtime/inference.lock")
        self.assertFalse(paths[0].exists())

    def test_default_user_cache_creation_private_and_writable(self):
        home=self.lock_root/"user"
        home.mkdir()
        lock=llm._configured_inference_lock({},home)
        with patch.object(llm,"INFERENCE_LOCK",lock):
            lease=llm._open_inference_lease()
            lease.write("synthetic lock test")
            lease.close()
        self.assertEqual(lock.read_text(),"synthetic lock test")
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode),0o600)
        for directory in (home/".cache",home/".cache/ax-lab",lock.parent):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode),0o700)

    def test_absolute_lock_override_and_relative_rejection(self):
        configured=self.lock_root/"explicit"/"inference.lock"
        self.assertEqual(llm._configured_inference_lock({"AX_LAB_INFERENCE_LOCK":str(configured)},self.lock_root),configured)
        for value in ("relative/inference.lock","~/inference.lock",""):
            with self.subTest(value=value),self.assertRaisesRegex(RuntimeError,"inference_lock_configuration_invalid"):
                llm._configured_inference_lock({"AX_LAB_INFERENCE_LOCK":value},self.lock_root)
        with patch.object(llm,"INFERENCE_LOCK",Path("relative.lock")),patch.object(llm.urllib.request,"urlopen") as call:
            with self.assertRaisesRegex(RuntimeError,"inference_lock_configuration_invalid"):
                llm.request_json([],{})
        call.assert_not_called()

    def test_lock_permission_failure_is_safe_and_never_calls_network(self):
        with patch.object(llm.os,"open",side_effect=PermissionError("secret filesystem path")),patch.object(llm.urllib.request,"urlopen") as call:
            with self.assertRaisesRegex(RuntimeError,"^inference_lock_unavailable$"):
                llm.request_json([],{})
        call.assert_not_called()
        self.assertFalse(llm._lock.locked())

    def test_lock_symlink_refused_without_network_or_target_change(self):
        target=self.lock_root/"target"
        target.write_text("unchanged")
        lock=self.lock_root/"symlink.lock"
        lock.symlink_to(target)
        with patch.object(llm,"INFERENCE_LOCK",lock),patch.object(llm.urllib.request,"urlopen") as call:
            with self.assertRaisesRegex(RuntimeError,"inference_lock_unavailable"):
                llm.request_json([],{})
        call.assert_not_called()
        self.assertEqual(target.read_text(),"unchanged")

    def test_lock_directory_creation_bounded_and_private_parent_required(self):
        too_deep=self.lock_root/"one"/"two"/"three"/"four"/"lock"
        with patch.object(llm,"INFERENCE_LOCK",too_deep):
            with self.assertRaisesRegex(RuntimeError,"inference_lock_unavailable"):
                llm._open_inference_lease()
        self.assertFalse((self.lock_root/"one").exists())
        public=self.lock_root/"public"
        public.mkdir(mode=0o755)
        with patch.object(llm,"INFERENCE_LOCK",public/"lock"),patch.object(llm.urllib.request,"urlopen") as call:
            with self.assertRaisesRegex(RuntimeError,"inference_lock_unavailable"):
                llm.request_json([],{})
        call.assert_not_called()
        self.assertFalse((public/"lock").exists())

    def test_fifo_lock_fails_promptly_before_network(self):
        import subprocess
        import sys
        import time
        lock=self.lock_root/"fifo.lock"
        os.mkfifo(lock,0o600)
        # Subprocess timeout guards the regression itself against a blocking open.
        script=("from pathlib import Path; from unittest.mock import patch; "
                "from spec_review import llm; import sys; llm.INFERENCE_LOCK=Path(sys.argv[1]); "
                "network=patch.object(llm.urllib.request,'urlopen'); call=network.start(); "
                "\ntry: llm.request_json([],{})"
                "\nexcept RuntimeError as error: assert str(error)=='inference_lock_unavailable'"
                "\nelse: raise AssertionError('FIFO lease accepted')"
                "\nassert not call.called")
        started=time.monotonic()
        result=subprocess.run([sys.executable,"-c",script,str(lock)],capture_output=True,text=True,timeout=3)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertLess(time.monotonic()-started,3)
        self.assertTrue(stat.S_ISFIFO(lock.stat().st_mode))

    def test_timeout_latches_and_prevents_duplicate_request(self):
        original=llm._disabled_reason;llm._disabled_reason=None
        try:
            with patch.object(llm.urllib.request,"urlopen",side_effect=TimeoutError("test")) as call:
                with self.assertRaises(TimeoutError):llm.request_json([],{})
                with self.assertRaisesRegex(RuntimeError,"inference_disabled"):llm.request_json([],{})
                self.assertEqual(call.call_count,1)
        finally:llm._disabled_reason=original
    def test_timeout_barrier_survives_restart_and_prevents_network(self):
        import subprocess,sys
        original=llm._disabled_reason;llm._disabled_reason=None
        try:
            with patch.object(llm.urllib.request,"urlopen",side_effect=TimeoutError("test")):
                with self.assertRaises(TimeoutError):llm.request_json([],{})
            marker=Path(str(llm.INFERENCE_LOCK)+".blocked")
            self.assertTrue(marker.is_file())
            self.assertEqual(stat.S_IMODE(marker.stat().st_mode),0o600)
            package=llm.__package__
            script=("from pathlib import Path; from unittest.mock import patch; "
                    "from "+package+" import llm; import sys; llm.INFERENCE_LOCK=Path(sys.argv[1]); "
                    "network=patch.object(llm.urllib.request,'urlopen'); call=network.start(); "
                    "\ntry: llm.request_json([],{})"
                    "\nexcept RuntimeError as error: assert str(error).startswith('inference_blocked_after_timeout')"
                    "\nelse: raise AssertionError('restart bypassed timeout barrier')"
                    "\nassert not call.called")
            result=subprocess.run([sys.executable,"-c",script,str(llm.INFERENCE_LOCK)],capture_output=True,text=True,timeout=3)
            self.assertEqual(result.returncode,0,result.stderr)
        finally:llm._disabled_reason=original

    def test_any_existing_timeout_marker_fails_closed_without_following(self):
        target=self.lock_root/"unchanged"
        target.write_text("not a runtime marker")
        Path(str(llm.INFERENCE_LOCK)+".blocked").symlink_to(target)
        with patch.object(llm.urllib.request,"urlopen") as call:
            with self.assertRaisesRegex(RuntimeError,"inference_blocked_after_timeout"):llm.request_json([],{})
        call.assert_not_called()
        self.assertEqual(target.read_text(),"not a runtime marker")

    def setUpDocument(self):
        import json
        root=Path(__file__).resolve().parents[1]
        self.document=json.loads((root/"data/documents.json").read_text())["documents"][0]
    def valid_proposal(self):
        from spec_review.extraction import extract_document
        actual=extract_document(self.document)
        return {"fields":{name:{"raw_value":cell["raw_value"],"quote":cell["quote"]} for name,cell in actual["fields"].items()}}
    def test_adapter_uses_one_document_without_metadata_or_gold(self):
        self.setUpDocument()
        with patch.object(llm,"request_json",return_value=(self.valid_proposal(),{"latency_ms":12}, {},{})) as request:
            output=llm.extract_document_with_model(self.document)
        self.assertEqual(output["model_state"],"source_verified")
        self.assertEqual(output["metrics"]["latency_ms"],12)
        self.assertFalse(output["metrics"]["thinking_off_verified"])
        import json
        messages=request.call_args.args[0]
        self.assertEqual(json.loads(messages[1]["content"]),{"source_text":self.document["content"]})
        self.assertEqual(request.call_args.kwargs["num_predict"],512)
    def test_adapter_rejects_partial_cell_or_unrelated_quote(self):
        self.setUpDocument()
        for field,value in (("raw_value","AL50"),("quote","Finish code: BLACK_ANODIZE")):
            proposal=self.valid_proposal();proposal["fields"]["material_grade"][field]=value
            with patch.object(llm,"request_json",return_value=(proposal,{}, {},{})):
                with self.assertRaisesRegex(RuntimeError,"model_proposal_rejected"):llm.extract_document_with_model(self.document)
    def test_context_budget_prevents_http(self):
        import hashlib
        self.setUpDocument()
        self.document["content"]="x"*6001
        self.document["source_hash"]=hashlib.sha256(self.document["content"].encode()).hexdigest()
        with patch.object(llm,"request_json") as request:
            with self.assertRaisesRegex(RuntimeError,"document_context_budget_exceeded"):llm.extract_document_with_model(self.document)
        request.assert_not_called()
if __name__=="__main__":unittest.main()
