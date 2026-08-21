import type { Memory } from "../types";

interface Props {
  memories: Memory[];
  holder: string;
  onTrace: (path: string) => void;
}

export function MemoryFile({ memories, holder, onTrace }: Props) {
  return (
    <div className="panel">
      <div className="scroll">
        {memories.length === 0 ? (
          <p className="empty">
            Nothing here yet. {holder ? `This is ${holder}\u2019s file.` : "Bring something."}
          </p>
        ) : (
          memories.map((memory) => (
            <div className={`memory${memory.revoked ? " gone" : ""}`} key={memory.path}>
              <button
                className="note"
                type="button"
                onClick={() => onTrace(memory.path)}
                title={`everything that has touched ${memory.path}`}
              >
                <span className="value">{memory.value}</span>
                <span className="about">
                  {memory.note} <span className="path">{memory.path}</span>
                  {memory.source !== "seeded" && (
                    <span className="source" title={`came from: ${memory.source}`}>
                      {" \u00b7 "}
                      {memory.source}
                    </span>
                  )}
                </span>
              </button>
              {memory.revoked && <span className="revoked-stamp">revoked</span>}
              {!memory.revoked && memory.attested && (
                <span
                  className="tag proof"
                  title="the model is told this is confirmed, never the value"
                >
                  proof only
                </span>
              )}
              {!memory.revoked && memory.sensitive && (
                <span className="tag special" title="needs a request of its own; never rides along">
                  special
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
