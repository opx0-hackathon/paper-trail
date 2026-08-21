import { useEffect, useState } from "react";
import "./styles/app.css";

interface Shared {
  path: string;
  note: string;
  value: string;
  attested: boolean;
  source: string;
}

export default function SharedView({ token }: { token: string }) {
  const [memories, setMemories] = useState<Shared[] | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    fetch(`/api/shared/${encodeURIComponent(token)}`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((data: { memories: Shared[] }) => setMemories(data.memories))
      .catch(() => setGone(true));
  }, [token]);

  return (
    <>
      <header>
        <div className="mark">
          Paper<em>·</em>Trail
        </div>
        <div className="tagline">a slice of someone&rsquo;s memory file</div>
      </header>

      <main style={{ gridTemplateColumns: "minmax(0, 1fr)" }}>
        <div className="column">
          <div className="thesis">
            <div className="kicker">shared with you</div>
            <p>Only what they chose to hand over, and nothing else.</p>
            <div className="fine">
              They picked these memories one at a time. A special category cannot travel on a link
              at all. They can see that you opened this, and they can revoke it whenever they like —
              at which point this page goes empty.
            </div>
          </div>

          <section>
            <h2>What they shared</h2>
            <div className="card">
              {gone && (
                <p className="empty">
                  This link has expired or been revoked. There is nothing here.
                </p>
              )}
              {!gone && memories === null && <p className="empty">Opening…</p>}
              {!gone && memories?.length === 0 && (
                <p className="empty">Everything this link covered has since been revoked.</p>
              )}
              {memories?.map((memory) => (
                <div className="memory" key={memory.path}>
                  <div className="note">
                    <span className="value">{memory.attested ? "Confirmed" : memory.value}</span>
                    <span className="about">
                      {memory.note} <span className="path">{memory.path}</span>
                    </span>
                  </div>
                  {memory.attested && <span className="tag proof">proof only</span>}
                </div>
              ))}
            </div>
          </section>
        </div>
      </main>

      <footer>
        <span>Paper Trail</span>
        <a href="/">Make your own memory file</a>
      </footer>
    </>
  );
}
