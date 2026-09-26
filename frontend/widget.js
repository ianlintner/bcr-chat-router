/**
 * BCR Chat Router — embeddable chat widget (Web Component, no build step).
 *
 * Usage:
 *   <script src="widget.js"></script>
 *   <bcr-chat-widget ws-url="ws://localhost:8000/ws/chat"></bcr-chat-widget>
 *
 * Modeled loosely on langflow-embedded-chat's drop-in <script> pattern, but
 * with zero framework dependency: plain Custom Element + WebSocket.
 */
class BcrChatWidget extends HTMLElement {
  connectedCallback() {
    this.sessionId = crypto.randomUUID();
    this.wsUrl = this.getAttribute("ws-url") || "ws://localhost:8000/ws/chat";
    this.attachShadow({ mode: "open" });
    this._render();
    this._connect();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { all: initial; }
        .card { font-family: system-ui, sans-serif; width: 340px; border: 1px solid #d0d5dd;
          border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); overflow: hidden;
          display: flex; flex-direction: column; height: 460px; background: #fff; }
        .header { background: #1d3557; color: #fff; padding: 10px 14px; font-weight: 600; font-size: 14px; }
        .badge { font-weight: 400; font-size: 11px; opacity: 0.85; display: block; }
        .messages { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
        .msg { max-width: 80%; padding: 8px 10px; border-radius: 8px; font-size: 13px; line-height: 1.35; }
        .citizen { align-self: flex-end; background: #457b9d; color: #fff; }
        .system { align-self: flex-start; background: #f1f1f1; color: #222; }
        .routing { align-self: center; font-size: 11px; color: #888; text-align: center; }
        .input-row { display: flex; border-top: 1px solid #e5e5e5; }
        input { flex: 1; border: none; padding: 10px; font-size: 13px; outline: none; }
        button { border: none; background: #1d3557; color: #fff; padding: 0 16px; cursor: pointer; }
      </style>
      <div class="card">
        <div class="header">Bureau of Citizen Response
          <span class="badge" id="status">connecting…</span>
        </div>
        <div class="messages" id="messages"></div>
        <div class="input-row">
          <input id="input" type="text" placeholder="Describe your issue..." />
          <button id="send">Send</button>
        </div>
      </div>
    `;
    this.shadowRoot.getElementById("send").addEventListener("click", () => this._send());
    this.shadowRoot.getElementById("input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._send();
    });
  }

  _connect() {
    this.ws = new WebSocket(this.wsUrl);
    const status = this.shadowRoot.getElementById("status");
    this.ws.onopen = () => (status.textContent = "connected");
    this.ws.onclose = () => (status.textContent = "disconnected");
    this.ws.onerror = () => (status.textContent = "connection error");
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "routing_decision") {
        this._appendRouting(data);
      } else if (data.type === "message") {
        this._appendMessage(data.sender, data.text);
      }
    };
  }

  _appendMessage(sender, text) {
    const el = document.createElement("div");
    el.className = `msg ${sender === "citizen" ? "citizen" : "system"}`;
    el.textContent = text;
    const box = this.shadowRoot.getElementById("messages");
    box.appendChild(el);
    box.scrollTop = box.scrollHeight;
  }

  _appendRouting(data) {
    const el = document.createElement("div");
    el.className = "routing";
    const dept = data.department.replace("_", " ");
    el.textContent = `→ routed to ${dept} (${(data.confidence * 100).toFixed(0)}% conf, ${data.source})${
      data.escalated ? " · escalated to human" : ""
    }`;
    const box = this.shadowRoot.getElementById("messages");
    box.appendChild(el);
    box.scrollTop = box.scrollHeight;
  }

  _send() {
    const input = this.shadowRoot.getElementById("input");
    const text = input.value.trim();
    if (!text || this.ws.readyState !== WebSocket.OPEN) return;
    this._appendMessage("citizen", text);
    this.ws.send(JSON.stringify({ session_id: this.sessionId, sender: "citizen", text }));
    input.value = "";
  }
}

customElements.define("bcr-chat-widget", BcrChatWidget);
