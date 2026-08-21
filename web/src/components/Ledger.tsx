import type { Receipt } from "../types";

const clock = (seconds: number) =>
  new Date(seconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

interface Props {
  receipts: Receipt[];
  focus?: string | null;
  onClearFocus?: () => void;
}

export function Ledger({ receipts, focus = null, onClearFocus }: Props) {
  const shown = focus ? receipts.filter((receipt) => receipt.path === focus) : receipts;

  return (
    <div className="panel">
      {focus && (
        <div className="tracing">
          <span className="mono">{focus}</span>
          <span className="detail">
            {shown.length} {shown.length === 1 ? "entry" : "entries"}
          </span>
          <button className="ghost" type="button" onClick={onClearFocus}>
            Show all
          </button>
        </div>
      )}
      <div className="scroll">
        {shown.length === 0 ? (
          <p className="empty">
            {focus ? "Nothing has touched this one yet." : "Nothing read yet."}
          </p>
        ) : (
          shown.map((receipt, index) => (
            <div className="line" key={`${receipt.created_at}-${receipt.path}-${index}`}>
              <span className="when">{clock(receipt.created_at)}</span>
              <span className="what">
                <span className={`act ${receipt.action}`}>{receipt.action.replace("_", " ")}</span>
                <span className="mono">{receipt.path}</span>
                <span className="detail">{receipt.purpose || receipt.detail}</span>
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
