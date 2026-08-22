type Tone = "plain" | "key" | "gate";

interface BoxProps {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  lines: string[];
  tone?: Tone;
}

function Box({ x, y, w, h, title, lines, tone = "plain" }: BoxProps) {
  return (
    <g className={`n ${tone}`}>
      <rect x={x} y={y} width={w} height={h} rx="14" />
      <text className="nt" x={x + 18} y={y + 30}>
        {title}
      </text>
      {lines.map((line, i) => (
        <text className="nl" key={line} x={x + 18} y={y + 54 + i * 18}>
          {line}
        </text>
      ))}
    </g>
  );
}

function Band({ y, text }: { y: number; text: string }) {
  return (
    <text className="band" x={54} y={y}>
      {text}
    </text>
  );
}

const A = "url(#pt-arrow)";

/** The whole application as one wired diagram, then the same thing as worked examples. */
export function Flow() {
  return (
    <>
      <section className="flow">
        <div className="flow-head">
          <span className="eyebrow">the whole thing, end to end</span>
          <h2 className="big">Where every value goes, and what it leaves behind on the way.</h2>
          <p>
            Nothing below is a diagram of an intention. Each box is a function or a screen that
            exists, and each line is a value actually moving.
          </p>
        </div>

        <div className="flow-scroll">
          <svg viewBox="0 0 1560 1240" role="img" aria-labelledby="flow-title">
            <title id="flow-title">
              How Paper Trail works: building a memory file, running one turn under consent and
              receipts, revoking a memory and answering again, and the same rules over share links
              and MCP.
            </title>
            <defs>
              <marker
                id="pt-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path className="head" d="M0 0 L10 5 L0 10 Z" />
              </marker>
            </defs>

            {/* ── 1 · get a file ─────────────────────────────────────────── */}
            <Band y={34} text="1 — GET A FILE, IN ABOUT A MINUTE" />

            <Box
              x={54}
              y={66}
              w={118}
              h={104}
              title="You"
              lines={["anyone.", "no sign-up,", "no key"]}
            />
            <Box
              x={202}
              y={66}
              w={236}
              h={104}
              title="Paste anything"
              lines={[
                "a bio · a résumé · an export",
                "from another assistant · or",
                "five plain sentences",
              ]}
            />
            <Box
              x={468}
              y={66}
              w={228}
              h={104}
              title="extract"
              lines={[
                "one model call proposes",
                "candidates and classifies",
                "each one it proposes",
              ]}
            />
            <Box
              x={726}
              y={66}
              w={232}
              h={104}
              title="Candidates"
              lines={[
                "special categories flagged,",
                "figures marked attested.",
                "nothing is written yet",
              ]}
            />
            <Box
              x={988}
              y={66}
              w={252}
              h={104}
              title="You tick what stays"
              lines={["policy re-checks every flag —", "the model's word for it", "is not taken"]}
            />
            <Box
              x={1270}
              y={66}
              w={270}
              h={104}
              tone="key"
              title="Your memory file"
              lines={[
                "each memory: a path, a subject,",
                "and a value nothing has been",
                "handed yet",
              ]}
            />

            <Box
              x={202}
              y={196}
              w={236}
              h={80}
              title="Or try the ready-made file"
              lines={["Arjun · a hostel room · already", "filled in"]}
            />

            <path className="wire" markerEnd={A} d="M172 118 H196" />
            <path className="wire" markerEnd={A} d="M438 118 H462" />
            <path className="wire" markerEnd={A} d="M696 118 H720" />
            <path className="wire" markerEnd={A} d="M958 118 H982" />
            <path className="wire" markerEnd={A} d="M1240 118 H1264" />
            <path className="wire" markerEnd={A} d="M438 236 H1372 Q1400 236 1400 210 V178" />

            {/* ── 2 · one turn ───────────────────────────────────────────── */}
            <Band y={322} text="2 — ONE TURN, AND WHAT IT COST" />

            <Box
              x={54}
              y={356}
              w={214}
              h={92}
              title="You ask"
              lines={["“What should I cook", "tonight?”"]}
            />
            <Box
              x={298}
              y={342}
              w={306}
              h={120}
              tone="key"
              title="Scope call"
              lines={[
                "shown only what each memory is",
                "about — “a diagnosed medical",
                "condition” — never what it holds.",
                "It says what it needs, and why.",
              ]}
            />
            <Box
              x={634}
              y={356}
              w={226}
              h={92}
              title="Proposal"
              lines={["the paths it wants, and the", "reason it gave for each"]}
            />
            <Box
              x={890}
              y={368}
              w={190}
              h={68}
              tone="gate"
              title="ask me first?"
              lines={["your switch"]}
            />

            <Box
              x={1110}
              y={294}
              w={366}
              h={104}
              title="On — a consent card"
              lines={[
                "every memory with its reason, and",
                "nothing out of the database yet. The",
                "special category sits apart, unticked.",
              ]}
            />
            <Box
              x={1110}
              y={418}
              w={366}
              h={110}
              tone="gate"
              title="Off — ordinary through, special refused"
              lines={[
                "“a special category needs a request of",
                "its own.” The refusal is stamped in the",
                "ledger as well.",
              ]}
            />

            <path className="wire" markerEnd={A} d="M268 402 H292" />
            <path className="wire" markerEnd={A} d="M604 402 H628" />
            <path className="wire" markerEnd={A} d="M860 402 H884" />
            <path className="wire" markerEnd={A} d="M1080 392 H1094 V346 H1104" />
            <path className="wire" markerEnd={A} d="M1080 412 H1094 V470 H1104" />
            <text className="lab" x={1094} y={332} textAnchor="middle">
              on
            </text>
            <text className="lab" x={1094} y={498} textAnchor="middle">
              off
            </text>

            <path className="wire" markerEnd={A} d="M1476 346 H1500 V576 H1420 V590" />
            <path className="wire" d="M1476 470 H1500" />
            <text className="lab" x={1466} y={558} textAnchor="end">
              granted
            </text>

            <Box
              x={1300}
              y={600}
              w={240}
              h={104}
              tone="gate"
              title="validate_request"
              lines={[
                "unknown, revoked, or a special",
                "category riding along —",
                "every one refused",
              ]}
            />
            <Box
              x={1010}
              y={600}
              w={260}
              h={104}
              tone="key"
              title="read + receipt"
              lines={[
                "the ledger row is written in",
                "the same transaction as the",
                "read. It cannot not happen.",
              ]}
            />
            <Box
              x={718}
              y={600}
              w={262}
              h={104}
              tone="key"
              title="project()"
              lines={[
                "the only route a value takes to",
                "a model. attested yields",
                "confirmed: true, never ₹1,200",
              ]}
            />
            <Box
              x={462}
              y={600}
              w={226}
              h={104}
              title="Answer call"
              lines={["handed exactly that", "context, and nothing", "else at all"]}
            />
            <Box
              x={54}
              y={600}
              w={378}
              h={104}
              tone="key"
              title="Answer + stamp row"
              lines={[
                "stamps land at about 0.6s, before the first",
                "token — rendered from the rows written",
                "above, not claimed by the model afterwards",
              ]}
            />

            <path className="wire" markerEnd={A} d="M1300 652 H1276" />
            <path className="wire" markerEnd={A} d="M1010 652 H986" />
            <path className="wire" markerEnd={A} d="M718 652 H694" />
            <path className="wire" markerEnd={A} d="M462 652 H438" />

            <Box
              x={718}
              y={736}
              w={822}
              h={58}
              title="Ledger"
              lines={[
                "every ask, read, refusal, grant and open — in order, timestamped, and yours to export",
              ]}
            />
            <path className="wire soft" markerEnd={A} d="M1420 704 V730" />
            <path className="wire soft" markerEnd={A} d="M1140 704 V730" />

            {/* ── 3 · after the answer ───────────────────────────────────── */}
            <Band y={850} text="3 — AFTER THE ANSWER" />

            <Box
              x={54}
              y={884}
              w={282}
              h={104}
              title="Pull one off the row"
              lines={["one tap on a stamp. Not a", "settings page, and not all", "of it at once"]}
            />
            <Box
              x={362}
              y={884}
              w={196}
              h={104}
              tone="gate"
              title="revoke"
              lines={["the memory goes grey", "and is never offered", "to the model again"]}
            />
            <Box
              x={584}
              y={884}
              w={326}
              h={104}
              title="The same question, without it"
              lines={[
                "a microwave soup becomes a stir-fry in",
                "a pan he has not got. The answer gets",
                "worse in a way you can point at.",
              ]}
            />
            <Box
              x={936}
              y={884}
              w={286}
              h={104}
              title="It proposes a memory"
              lines={[
                "“gym on Tuesdays and Thursdays” —",
                "offered beside the answer, and",
                "never written by it",
              ]}
            />
            <Box
              x={1248}
              y={884}
              w={292}
              h={104}
              title="You keep it, or you don't"
              lines={[
                "kept goes up into the file.",
                "declined leaves nothing",
                "behind but a ledger row",
              ]}
            />

            <path className="wire" markerEnd={A} d="M336 936 H356" />
            <path className="wire" markerEnd={A} d="M558 936 H578" />
            <path className="wire" markerEnd={A} d="M1222 936 H1242" />
            <path className="wire" markerEnd={A} d="M575 704 V856 H1079 V878" />
            <path className="wire soft" markerEnd={A} d="M1540 884 H1550 V130 H1546" />
            <text className="lab" x={1494} y={252} textAnchor="end">
              kept
            </text>

            <path
              className="wire"
              markerEnd={A}
              d="M460 988 V1014 H44 Q30 1014 30 1000 V416 Q30 402 44 402 H48"
            />
            <text className="lab" x={72} y={1036}>
              the same question runs the whole turn again, without it
            </text>

            {/* ── 4 · elsewhere ──────────────────────────────────────────── */}
            <Band y={1078} text="4 — THE SAME RULES, OUTSIDE THIS PAGE" />

            <Box
              x={54}
              y={1120}
              w={482}
              h={104}
              title="Hand someone a slice"
              lines={[
                "a link over a subset you pick. Never a special category,",
                "never an attested value. One hour, every open counted,",
                "and dead the moment you revoke it.",
              ]}
            />
            <Box
              x={566}
              y={1120}
              w={482}
              h={104}
              title="Mount it in Claude, over MCP"
              lines={[
                "describe shows subjects, never values. request_context",
                "returns a projection, or a pending request. propose_memory",
                "offers a memory and never writes one.",
              ]}
            />
            <Box
              x={1078}
              y={1120}
              w={462}
              h={104}
              title="Take the whole thing with you"
              lines={[
                "the file and its ledger, as JSON or Markdown. Every",
                "session is purged after 24 hours, because there are",
                "no accounts here to keep it in.",
              ]}
            />

            <text className="lab" x={54} y={1108}>
              the same file →
            </text>
            <path className="wire soft" d="M164 1104 H1309" />
            <path className="wire soft" markerEnd={A} d="M295 1104 V1114" />
            <path className="wire soft" markerEnd={A} d="M807 1104 V1114" />
            <path className="wire soft" markerEnd={A} d="M1309 1104 V1114" />
          </svg>
        </div>
      </section>

      <section className="examples">
        <div className="flow-head">
          <span className="eyebrow">four turns, as they actually run</span>
          <h2 className="big">The same file, asked four different ways.</h2>
        </div>

        <div className="ex-grid">
          {EXAMPLES.map((example) => (
            <article className="card ex" key={example.q + example.tag}>
              <span className="ex-tag">{example.tag}</span>
              <p className="ex-q">{example.q}</p>
              <div className="stamps">
                {example.stamps.map((stamp) => (
                  <span className={`stamp ${stamp.kind}`} key={stamp.path} title={stamp.why}>
                    {stamp.path}
                    {stamp.kind === "proof" && (
                      <>
                        <span className="redact" aria-hidden="true" />
                        <span className="flag">proof only</span>
                      </>
                    )}
                    {stamp.kind === "refused" && <span className="flag">refused</span>}
                    {stamp.kind === "gone" && <span className="flag">revoked</span>}
                    {stamp.kind === "sensitive" && <span className="flag">sensitive read</span>}
                  </span>
                ))}
              </div>
              <p className="ex-a">{example.a}</p>
              <p className="ex-note">{example.note}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

interface ExStamp {
  path: string;
  kind: "value" | "proof" | "refused" | "gone" | "sensitive";
  why: string;
}

const EXAMPLES: { tag: string; q: string; stamps: ExStamp[]; a: string; note: string }[] = [
  {
    tag: "the ordinary case",
    q: "What should I cook tonight?",
    stamps: [
      { path: "diet.style", kind: "value", why: "asked for: to rule out meat and egg" },
      {
        path: "kitchen.equipment",
        kind: "value",
        why: "asked for: what can actually be cooked on",
      },
      {
        path: "budget.weekly",
        kind: "proof",
        why: "attested — the model gets confirmation, not ₹1,200",
      },
      {
        path: "health.condition",
        kind: "refused",
        why: "a special category needs a request of its own",
      },
    ],
    a: "Make a microwave vegetable and lentil soup. Toss lentils, canned tomatoes, frozen mixed vegetables, a splash of soy sauce, and a pinch of cumin into a bowl, microwave until hot, then stir and season. It’s quick, vegetarian, egg‑free, and inexpensive.",
    note: "It asked for four memories. Three were handed over and the medical one was refused on its way past — stamped, not silently dropped.",
  },
  {
    tag: "pull one off",
    q: "What should I cook tonight? — again, without the kitchen",
    stamps: [
      { path: "kitchen.equipment", kind: "gone", why: "revoked by you" },
      { path: "diet.style", kind: "value", why: "asked for: determine suitable recipes" },
    ],
    a: "Try a tofu and vegetable stir‑fry with bell peppers, broccoli, and snap peas in a garlic‑ginger sauce. It’s quick, vegetarian, and egg‑free.",
    note: "He has no pan and no hob. One memory came off the row, the model stopped asking for the rest, and the answer got worse in a way you can point at — which is the only proof it was being used at all.",
  },
  {
    tag: "ask me first, then grant",
    q: "What should I cook tonight? — with the medical one granted on purpose",
    stamps: [
      { path: "diet.style", kind: "value", why: "asked for: determine dietary restrictions" },
      { path: "kitchen.equipment", kind: "value", why: "asked for: know available cooking tools" },
      { path: "budget.weekly", kind: "proof", why: "attested — confirmation only" },
      {
        path: "health.condition",
        kind: "sensitive",
        why: "granted deliberately, read as its own request",
      },
    ],
    a: "Make a microwave tofu and vegetable stir‑fry with soy sauce, garlic, and a splash of coconut milk. It’s vegetarian, egg‑free, lactose‑free, and uses only your kettle and microwave.",
    note: "Lactose‑free is in the answer only because the special category was granted as a second, independent request — stamped sensitive_read in the ledger, apart from everything beside it.",
  },
  {
    tag: "a different question",
    q: "Plan my Saturday.",
    stamps: [
      { path: "diet.style", kind: "value", why: "asked for: plan meals" },
      { path: "kitchen.equipment", kind: "value", why: "asked for: determine cooking options" },
      { path: "budget.weekly", kind: "proof", why: "attested — confirmation only" },
      { path: "location.city", kind: "value", why: "asked for: plan local activities" },
      { path: "schedule.evenings", kind: "value", why: "asked for: know free Saturday evenings" },
    ],
    a: "On Saturday, after noon, visit Koramangala’s Green Tiffin for a hearty vegetarian lunch, then stroll to the nearby ISKCON temple for a peaceful afternoon. Return to your hostel, brew a cup of tea, and prepare a simple microwave stir‑fry with lentils and frozen veggies for dinner.",
    note: "A different question pulls a different row — where he lives and when he is free come in, and the medical one is not asked for at all.",
  },
];
