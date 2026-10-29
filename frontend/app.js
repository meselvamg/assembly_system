(() => {
  const API_BASE = (window.APP_CONFIG?.apiBase || "http://127.0.0.1:8000").replace(/\/$/, "");
  const SESSION_KEY = "assemblyQaSession";
  const REFRESH_MS = 10000;

  const ROLE_NAMES = {
    SUPERVISOR: "Supervisor",
    OPERATOR: "Manual Operator",
    TECHNICIAN: "Technician",
    ENGINEER: "Engineer",
  };

  // value -> [label, status class, icon]; colour is never the only signal
  const STATES = {
    status: {
      RUNNING: ["Running", "info", "▶"],
      COMPLETED: ["Completed", "good", "✓"],
      ERROR: ["Error", "critical", "✕"],
      UNKNOWN: ["No line status", "neutral", "?"],
    },
    qa: {
      PASS: ["Pass", "good", "✓"],
      FAIL: ["Fail", "critical", "✕"],
    },
    cloud: {
      SENT: ["Sent", "good", "✓"],
      PENDING: ["Pending", "warning", "…"],
      FAILED: ["Failed", "critical", "✕"],
    },
    entry: {
      ASSEMBLY: ["Assembly", "info", "A"],
      QA: ["QA", "info", "Q"],
      SCADA: ["Line status", "info", "S"],
    },
  };

  // One entry per screen. `roles` mirrors the backend permissions; the backend still enforces them.
  const VIEWS = [
    {
      id: "assemble",
      tab: "Assemble",
      title: "Assemble component",
      help: "Scan or type the mobile base and the component you fitted. The base ID stays filled so you can fit the next part.",
      roles: ["OPERATOR", "SUPERVISOR"],
      endpoint: "/api/assemble_component/",
      submit: "Save assembly",
      fields: [
        { name: "MobileBaseID", label: "Mobile base ID", placeholder: "MB001", keep: true },
        { name: "ComponentID", label: "Component ID", placeholder: "CAM-01" },
      ],
      describe: (d) => [`${d.ComponentID} fitted on ${d.MobileBaseID}`, "good", "✓"],
    },
    {
      id: "qa",
      tab: "QA check",
      title: "QA verification",
      help: "Check the fitted component and record the result.",
      roles: ["TECHNICIAN", "ENGINEER", "SUPERVISOR"],
      endpoint: "/api/verify_component/",
      submit: "Save QA result",
      fields: [
        { name: "MobileBaseID", label: "Mobile base ID", placeholder: "MB001", keep: true },
        { name: "ComponentID", label: "Component ID", placeholder: "CAM-01" },
        { name: "VerificationStatus", label: "Result", choices: STATES.qa },
      ],
      describe: (d) => {
        const [label, cls, icon] = STATES.qa[d.VerificationStatus];
        return [`${d.ComponentID} on ${d.MobileBaseID}: ${label}`, cls, icon];
      },
    },
    {
      id: "scada",
      tab: "Line status",
      title: "Assembly line status",
      help: "Update the SCADA status of a mobile base on the line.",
      roles: ["TECHNICIAN", "ENGINEER", "SUPERVISOR"],
      endpoint: "/api/scada_integration/",
      submit: "Update status",
      fields: [
        { name: "MobileBaseID", label: "Mobile base ID", placeholder: "MB001" },
        { name: "AssemblyStatus", label: "Status", choices: pick(STATES.status, ["RUNNING", "COMPLETED", "ERROR"]) },
      ],
      describe: (d) => {
        const [label, cls, icon] = STATES.status[d.AssemblyStatus];
        return [`${d.MobileBaseID} is ${label.toLowerCase()}`, cls, icon];
      },
    },
    {
      id: "report",
      tab: "Cloud report",
      title: "Report to cloud",
      help: "Send all records of one type for a mobile base to the central cloud.",
      roles: ["ENGINEER", "SUPERVISOR"],
      endpoint: "/api/report_to_cloud/",
      submit: "Send report",
      fields: [
        { name: "MobileBaseID", label: "Mobile base ID", placeholder: "MB001" },
        { name: "EntryType", label: "Data to send", choices: STATES.entry },
      ],
      describe: (d, res) => {
        const [label, cls, icon] = STATES.cloud[res.sync_status] || STATES.cloud.FAILED;
        return [`${STATES.entry[d.EntryType][0]} data for ${d.MobileBaseID}: ${label}`, cls, icon];
      },
    },
    { id: "dashboard", tab: "Dashboard", roles: "all" },
  ];

  const recent = {};      // view id -> recent actions in this browser tab
  let session = loadSession();
  let currentView = null;
  let refreshTimer = null;

  // ---------- helpers ----------

  function pick(obj, keys) {
    return Object.fromEntries(keys.map((k) => [k, obj[k]]));
  }

  function el(tag, { dataset, ...props } = {}, children = []) {
    const node = Object.assign(document.createElement(tag), props);
    Object.assign(node.dataset, dataset);
    node.append(...children);
    return node;
  }

  function badge([label, cls, icon]) {
    return el("span", { className: "pill" }, [
      el("span", { className: `icon ${cls}`, textContent: icon, ariaHidden: "true" }),
      label,
    ]);
  }

  function loadSession() {
    try {
      return JSON.parse(sessionStorage.getItem(SESSION_KEY));
    } catch {
      return null;
    }
  }

  function saveSession(value) {
    session = value;
    try {
      if (value) sessionStorage.setItem(SESSION_KEY, JSON.stringify(value));
      else sessionStorage.removeItem(SESSION_KEY);
    } catch {
      /* storage blocked: stay signed in for this page only */
    }
  }

  async function api(path, { method = "GET", body } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (session) headers.Authorization = `Token ${session.token}`;
    let response;
    try {
      response = await fetch(API_BASE + path, { method, headers, body: body && JSON.stringify(body) });
    } catch {
      throw new Error(`Cannot reach the server at ${API_BASE}. Is the backend running?`);
    }
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && session) {
      signOut("Your session has expired. Please sign in again.");
      throw new Error("Signed out");
    }
    return { ok: response.ok, status: response.status, data };
  }

  function errorText(data, status) {
    if (data.errors) {
      return Object.entries(data.errors)
        .map(([field, msgs]) => `${field}: ${[].concat(msgs).join(" ")}`)
        .join("\n");
    }
    return data.message || data.detail || `Request failed (${status})`;
  }

  function showMessage(node, text, kind) {
    node.textContent = text;
    node.className = `message ${kind}`;
    node.hidden = false;
  }

  function canSee(view) {
    // superusers have no role and may use every screen
    return view.roles === "all" || !session.userType || view.roles.includes(session.userType);
  }

  // ---------- sign in / out ----------

  const loginView = document.getElementById("login-view");
  const appView = document.getElementById("app-view");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = loginForm.querySelector("button");
    const body = Object.fromEntries(new FormData(loginForm));
    button.disabled = true;
    loginError.hidden = true;
    try {
      const { ok, status, data } = await api("/api/authorize_user/", { method: "POST", body });
      if (!ok) throw new Error(errorText(data, status));
      saveSession({ token: data.token, username: body.Username, userType: data.user_type });
      loginForm.reset();
      showApp();
    } catch (err) {
      showMessage(loginError, err.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  document.getElementById("logout").addEventListener("click", () => signOut());

  function signOut(reason) {
    clearInterval(refreshTimer);
    saveSession(null);
    appView.hidden = true;
    loginView.hidden = false;
    if (reason) showMessage(loginError, reason, "warning");
    loginForm.querySelector("input").focus();
  }

  function showApp() {
    loginView.hidden = true;
    appView.hidden = false;
    document.getElementById("who-name").textContent = session.username;
    document.getElementById("who-role").textContent = ROLE_NAMES[session.userType] || "Admin";

    const tabs = document.getElementById("tabs");
    const visible = VIEWS.filter(canSee);
    tabs.replaceChildren(
      ...visible.map((view) =>
        el("button", {
          type: "button",
          role: "tab",
          textContent: view.tab,
          onclick: () => openView(view),
          dataset: { view: view.id },
        })
      )
    );
    openView(visible[0]);
  }

  function openView(view) {
    currentView = view;
    clearInterval(refreshTimer);
    for (const tab of document.querySelectorAll("#tabs button")) {
      tab.setAttribute("aria-selected", String(tab.dataset.view === view.id));
    }
    if (view.id === "dashboard") renderDashboard();
    else renderForm(view);
  }

  // ---------- action screens ----------

  function renderForm(view) {
    const panel = document.getElementById("panel");
    const result = el("p", { className: "message", role: "status", hidden: true });
    const form = el("form", { autocomplete: "off" });

    for (const field of view.fields) {
      if (field.choices) {
        form.append(
          el("fieldset", {}, [
            el("legend", { textContent: field.label }),
            el(
              "div",
              { className: "choices" },
              Object.entries(field.choices).map(([value, state]) =>
                el("label", { className: "choice" }, [
                  el("input", { type: "radio", name: field.name, value, required: true }),
                  el("span", {}, [badge(state)]),
                ])
              )
            ),
          ])
        );
      } else {
        form.append(
          el("label", { className: "field" }, [
            el("span", { textContent: field.label }),
            el("input", { name: field.name, placeholder: field.placeholder, required: true, maxLength: 50 }),
          ])
        );
      }
    }
    const button = el("button", { className: "primary wide", type: "submit", textContent: view.submit });
    form.append(button, result);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const body = Object.fromEntries([...new FormData(form)].map(([k, v]) => [k, String(v).trim()]));
      button.disabled = true;
      try {
        const { ok, status, data } = await api(view.endpoint, { method: "POST", body });
        if (!ok) {
          showMessage(result, errorText(data, status), "error");
          return;
        }
        const [text, cls, icon] = view.describe(body, data);
        const pending = data.sync_status === "PENDING";
        showMessage(
          result,
          pending ? `${text}. Saved, waiting for cloud: the backend has no CLOUD_API_URL set.` : `Saved: ${text}`,
          pending ? "warning" : "success"
        );
        addRecent(view, [text, cls, icon]);
        for (const field of view.fields) {
          if (field.keep) continue;
          for (const input of form.querySelectorAll(`[name="${field.name}"]`)) {
            if (input.type === "radio") input.checked = false;
            else input.value = "";
          }
        }
        const next = view.fields.find((f) => !f.keep && !f.choices);
        if (next) form.querySelector(`[name="${next.name}"]`).focus();
      } catch (err) {
        if (err.message !== "Signed out") showMessage(result, err.message, "error");
      } finally {
        button.disabled = false;
      }
    });

    const list = el("ul", { className: "recent" });
    panel.replaceChildren(
      el("div", { className: "split" }, [
        el("section", { className: "card" }, [
          el("h2", { textContent: view.title }),
          el("p", { className: "muted", textContent: view.help }),
          form,
        ]),
        el("section", { className: "card" }, [el("h3", { textContent: "Recent in this session" }), list]),
      ])
    );
    renderRecent(view, list);
    form.querySelector("input:not([type=radio])").focus();
  }

  function addRecent(view, state) {
    const items = (recent[view.id] ||= []);
    items.unshift({ state, time: new Date() });
    items.length = Math.min(items.length, 10);
    renderRecent(view, document.querySelector(".recent"));
  }

  function renderRecent(view, list) {
    const items = recent[view.id] || [];
    if (!items.length) {
      list.replaceChildren(el("li", {}, [el("p", { className: "empty", textContent: "Nothing saved yet" })]));
      return;
    }
    list.replaceChildren(
      ...items.map(({ state, time }) =>
        el("li", {}, [badge(state), el("time", { textContent: time.toLocaleTimeString() })])
      )
    );
  }

  // ---------- dashboard ----------

  function renderDashboard() {
    const panel = document.getElementById("panel");
    panel.replaceChildren(
      el("div", { className: "dash-head" }, [
        el("h2", { textContent: "Live dashboard" }),
        el("span", { id: "updated", className: "muted", textContent: "Loading…" }),
      ]),
      el("p", { id: "dash-error", className: "message error", hidden: true }),
      el("div", { id: "dash-body" })
    );
    loadDashboard();
    refreshTimer = setInterval(loadDashboard, REFRESH_MS);
  }

  async function loadDashboard() {
    const errorBox = document.getElementById("dash-error");
    if (!errorBox) return;
    try {
      const { ok, status, data } = await api("/api/dashboard_data/");
      if (!ok) throw new Error(errorText(data, status));
      if (currentView.id !== "dashboard") return;
      document.getElementById("dash-body").replaceChildren(...dashboardContent(data));
      document.getElementById("updated").textContent =
        `Updated ${new Date().toLocaleTimeString()} · refreshes every ${REFRESH_MS / 1000} s`;
      errorBox.hidden = true;
    } catch (err) {
      if (err.message !== "Signed out") showMessage(errorBox, `${err.message}. Retrying…`, "error");
    }
  }

  function dashboardContent(data) {
    const s = data.summary;
    const qaTotal = s.qa.PASS + s.qa.FAIL;
    const tile = (label, value, hint) =>
      el("div", { className: "card tile" }, [
        el("div", { className: "label", textContent: label }),
        el("div", { className: "value", textContent: value }),
        el("div", { className: "hint", textContent: hint }),
      ]);

    const tiles = el("div", { className: "tiles" }, [
      tile("Mobile bases", s.mobile_bases, "on the line"),
      tile("Components assembled", s.components_assembled, "all time"),
      tile(
        "QA pass rate",
        qaTotal ? `${Math.round((s.qa.PASS / qaTotal) * 100)}%` : "–",
        qaTotal ? `${s.qa.PASS} of ${qaTotal} checks` : "no checks yet"
      ),
      tile("Waiting for cloud", s.cloud_sync.PENDING + s.cloud_sync.FAILED, "pending + failed entries"),
    ]);

    const breakdowns = el("div", { className: "breakdowns" }, [
      breakdown("Line status", STATES.status, s.status),
      breakdown("QA results", STATES.qa, s.qa),
      breakdown("Cloud sync", STATES.cloud, s.cloud_sync),
    ]);

    const rows = data.mobile_bases.map((b) =>
      el("tr", {}, [
        el("td", { textContent: b.MobileBaseID }),
        el("td", {}, [badge(STATES.status[b.current_status] || [b.current_status, "neutral", "?"])]),
        el("td", { className: "num", textContent: b.components_assembled }),
        el("td", { className: "num", textContent: b.qa.PASS }),
        el("td", { className: "num", textContent: b.qa.FAIL }),
        el("td", { textContent: new Date(b.updated_at).toLocaleString() }),
      ])
    );
    if (!rows.length) {
      rows.push(el("tr", {}, [el("td", { colSpan: 6, className: "empty", textContent: "No mobile bases yet" })]));
    }
    const table = el("section", { className: "card" }, [
      el("h3", { textContent: "Mobile bases" }),
      el("div", { className: "table-wrap" }, [
        el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { textContent: "Mobile base" }),
              el("th", { textContent: "Status" }),
              el("th", { className: "num", textContent: "Components" }),
              el("th", { className: "num", textContent: "QA pass" }),
              el("th", { className: "num", textContent: "QA fail" }),
              el("th", { textContent: "Last update" }),
            ]),
          ]),
          el("tbody", {}, rows),
        ]),
      ]),
    ]);

    return [tiles, el("div", { style: "height:16px" }), breakdowns, el("div", { style: "height:16px" }), table];
  }

  // Part-to-whole bar plus a legend with counts
  function breakdown(title, states, counts) {
    const card = el("section", { className: "card" }, [el("h3", { textContent: title })]);
    const entries = Object.entries(counts);
    const total = entries.reduce((sum, [, n]) => sum + n, 0);
    if (!total) {
      card.append(el("p", { className: "empty", textContent: "No data yet" }));
      return card;
    }
    const bar = el("div", { className: "bar", role: "img" });
    const legend = el("ul", { className: "legend" });
    const labels = [];
    for (const [value, n] of entries) {
      const state = states[value] || [value, "neutral", "?"];
      const pct = Math.round((n / total) * 100);
      labels.push(`${state[0]} ${n}`);
      if (n) {
        const color = state[1] === "info" ? "accent" : state[1];
        bar.append(el("span", { title: `${state[0]}: ${n} (${pct}%)`, style: `flex-grow:${n};background:var(--${color})` }));
      }
      legend.append(el("li", {}, [badge(state), el("span", { className: "count", textContent: `${n} · ${pct}%` })]));
    }
    bar.setAttribute("aria-label", labels.join(", "));
    card.append(bar, legend);
    return card;
  }

  // ---------- start ----------

  if (session?.token) showApp();
  else signOut();
})();
