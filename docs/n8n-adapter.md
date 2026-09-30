# n8n adapter — design only
The official gallery community [document compliance template](https://n8n.io/workflows/7662-automated-document-compliance-validation-with-ai-and-vector-database/) informed intake/evidence/human-review separation.
n8n is not installed or activated; no account connection. Future adapter accepts IDs, calls backend comparison, waits for human review, and drafts handover.
ACL/hash/revision/source validation, extraction, comparison, shared inference and audit remain backend. Confidence is not calibrated probability or compliance verdict. No credentials/external write/control.
