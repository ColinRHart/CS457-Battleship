# AI Prompting and Constraint Strategy
AI generated code and help must follow the protocol and FSM defined in:

- `protocol_blueprint.md`
- `fsm_specification.md`

## Prompt Rules
AI rules(must do):

- TCP only.
- JSON for messages.
- End each JSON message with `\n`.
- Use the exact message names defined in `protocol_blueprint.md`.
- Use server states defined in `fsm_specification.md`.
- Reject invalid moves and out-of-turn moves with an `ERROR` message.
- Handle client disconnects without crashing the server.
- Do not assume one `recv()` call contains exactly one full message.
- Validate ship placement, including boundaries, ship length, and overlapping ships. Return `ERROR` for invalid placements.
- Handle disconnects during the lobby, ship placement, and gameplay according to the FSM.
- Use `threading.Lock` when accessing or changing shared game information.
