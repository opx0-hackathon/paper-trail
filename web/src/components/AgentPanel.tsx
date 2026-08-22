import { useState } from "react";
import type { Grant, PendingRequest } from "../types";

interface Props {
  token: string | null;
  pending: PendingRequest[];
  grants: Grant[];
  requestsOnly?: boolean;
  onConnect: () => void;
  onKnock: () => void;
  onSettle: (id: string, paths: string[], standing: boolean) => void;
  onUngrant: (id: string) => void;
}

export function AgentPanel({
  token,
  pending,
  grants,
  requestsOnly = false,
  onConnect,
  onKnock,
  onSettle,
  onUngrant,
}: Props) {
  const [shown, setShown] = useState(false);
  const live = grants.filter((grant) => !grant.revoked && grant.expires_at * 1000 > Date.now());

  const requests = pending.map((request) => (
    <div className="card pending turn" key={request.id}>
      <div className="why">{request.app} is asking</div>
      <div className="purpose" style={{ marginTop: 6 }}>
        {request.purpose || "no reason given"}
      </div>
      <div className="stamps">
        {request.paths.map((path) => (
          <span className="stamp" key={path}>
            {path}
          </span>
        ))}
      </div>
      <div className="row" style={{ marginTop: 13 }}>
        <button
          className="primary"
          type="button"
          onClick={() => onSettle(request.id, request.paths, true)}
        >
          Allow this session
        </button>
        <button
          className="ghost"
          type="button"
          onClick={() => onSettle(request.id, request.paths, false)}
        >
          Once
        </button>
        <button className="ghost" type="button" onClick={() => onSettle(request.id, [], false)}>
          Refuse
        </button>
      </div>
    </div>
  ));

  if (requestsOnly) return <>{requests}</>;

  return (
    <>
      {requests}
      <div className="panel">
        <div className="foot" style={{ borderTop: 0, display: "block" }}>
          <span className="eyebrow">assistants elsewhere</span>
          {!token ? (
            <>
              <p className="privacy">
                Mount this file in Claude or any MCP client. It gets subjects, never values, and
                every read still needs your say-so.
              </p>
              <div className="row" style={{ marginTop: 12 }}>
                <button className="ghost" type="button" onClick={onConnect}>
                  Connect an assistant
                </button>
                <button className="ghost" type="button" onClick={onKnock}>
                  Watch one ask
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="ghost" type="button" onClick={() => setShown((on) => !on)}>
                  {shown ? "Hide" : "Show"} endpoint
                </button>
                <button className="ghost" type="button" onClick={onKnock}>
                  Watch one ask
                </button>
              </div>
              {shown && (
                <p className="privacy mono" style={{ wordBreak: "break-all" }}>
                  {window.location.origin}/mcp/{token}/
                </p>
              )}
            </>
          )}

          {live.map((grant) => (
            <div className="memory" key={grant.id}>
              <div className="note">
                <span className="value">{grant.app}</span>
                <span className="about">
                  {grant.paths.join(", ")} · read {grant.reads}{" "}
                  {grant.reads === 1 ? "time" : "times"}
                </span>
              </div>
              <button className="ghost" type="button" onClick={() => onUngrant(grant.id)}>
                Revoke
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
