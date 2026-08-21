import type { Stamp } from "../types";

interface Props {
  stamps: Stamp[];
  revokedPath: string | null;
  busy: boolean;
  onPull: (path: string) => void;
}

export function StampRow({ stamps, revokedPath, busy, onPull }: Props) {
  if (stamps.length === 0 && !revokedPath) {
    return <p className="nothing">Nothing was handed over. This answer used no memories.</p>;
  }

  return (
    <div className="stamps">
      {revokedPath && (
        <span className="stamp gone" title="revoked, and not offered to the model again">
          {revokedPath} <span className="flag">revoked</span>
        </span>
      )}
      {stamps.map((stamp) =>
        stamp.kind === "refused" ? (
          <span className="stamp refused" key={stamp.path} title={stamp.reason}>
            {stamp.path} <span className="flag">refused</span>
          </span>
        ) : (
          <span
            className={`stamp ${stamp.kind}`}
            key={stamp.path}
            title={stamp.purpose ? `asked for: ${stamp.purpose}` : stamp.note}
          >
            {stamp.path}
            {stamp.kind === "proof" && (
              <>
                <span className="redact" aria-hidden="true" />
                <span className="flag">proof only</span>
              </>
            )}
            <button
              className="pull"
              type="button"
              disabled={busy}
              onClick={() => onPull(stamp.path)}
              title={
                busy
                  ? "Wait for the answer to finish"
                  : "Revoke this memory and answer again without it"
              }
              aria-label={`Revoke ${stamp.path}`}
            >
              &times;
            </button>
          </span>
        ),
      )}
    </div>
  );
}
