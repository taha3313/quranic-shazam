# Rejected early memory profile

These files record an early experiment that kept the active ONNX session cached across HTTP requests. The long-reciter matrix eventually OOM-killed that version. It was replaced by the request-scoped model lifecycle validated in the parent report. This is retained to distinguish the failed prototype from the final profile.
