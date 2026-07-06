// WebSocket client with auto-reconnect (exponential backoff). Feeds the store.

import { applySnapshots, setConn } from "./store";

let socket: WebSocket | null = null;
let backoff = 500;
const MAX_BACKOFF = 10000;

export function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws`;
  setConn("connecting");
  socket = new WebSocket(url);

  socket.onopen = () => { backoff = 500; setConn("open"); };

  socket.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "snapshot" && msg.data) {
        applySnapshots(msg.data, msg.active_source || "");
      }
    } catch {
      /* ignore malformed frame */
    }
  };

  socket.onclose = () => {
    setConn("closed");
    setTimeout(connectWS, backoff);
    backoff = Math.min(backoff * 2, MAX_BACKOFF);
  };

  socket.onerror = () => socket?.close();
}
