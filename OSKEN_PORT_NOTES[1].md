# OS-Ken port notes

- Replaced `ryu.*` imports with `os_ken.*`.
- Changed application base class from `RyuApp` to `OSKenApp`.
- Preserved the `/reservation` REST API and event JSON contract.
- Added a MAC-learning PacketIn handler; the previous controller installed a table-miss rule but did not process PacketIn messages.
- Kept OpenFlow meter and reservation lifecycle logic.
- This is a source-level port. It still requires live validation with the installed OS-Ken, Open vSwitch and Mininet versions.
