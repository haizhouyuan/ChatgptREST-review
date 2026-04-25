const runs = [
  {
    id: "LAB-0",
    label: "Strategy",
    agent: "product-innovation-director",
    run: "e39f9e35",
    title: "CEO strategy approval",
    detail: "Freezes the demo promise, approval model, and blocked external actions before any design work starts.",
  },
  {
    id: "LAB-1",
    label: "Data Truth",
    agent: "data-truth-guard",
    run: "bf517d57",
    title: "Claim-safe foundation",
    detail: "Separates verified facts, user-provided context, demo samples, and forbidden claims for every downstream agent.",
  },
  {
    id: "LAB-2",
    label: "Radar",
    agent: "competitive-radar-analyst",
    run: "dca03f55",
    title: "Opportunity clusters",
    detail: "Turns local review and competitor samples into conservative opportunity clusters with explicit missing evidence.",
  },
  {
    id: "LAB-3",
    label: "VOC",
    agent: "voc-intelligence-analyst",
    run: "68bbc593",
    title: "SpaceSmart concept brief",
    detail: "Translates compact-kitchen pain points into a reviewable foldable learning tower concept.",
  },
  {
    id: "LAB-4",
    label: "Routes",
    agent: "design-strategy-agent",
    run: "1caed56d",
    title: "Four design routes",
    detail: "Generates materially different concept routes and selects Fold-Flat Pantry for review.",
  },
  {
    id: "LAB-5",
    label: "Builder",
    agent: "design-strategy-agent",
    run: "07c8295d",
    title: "Mini Bakery Kitchen Corner",
    detail: "Defines a modular pretend-play schema and a demo-only PDP/waitlist block.",
  },
  {
    id: "LAB-6",
    label: "Review",
    agent: "design-director-agent",
    run: "b817927b",
    title: "Design director gate",
    detail: "Scores both concepts, converts risks into iteration prompts, and prevents unreviewed promotion.",
  },
  {
    id: "LAB-7",
    label: "DFM",
    agent: "dfm-safety-preflight-agent",
    run: "fdbb4ffa",
    title: "Safety and cost preflight",
    detail: "Blocks tipping, pinch, small-part, cost, and certification assumptions behind engineering review.",
  },
  {
    id: "LAB-8",
    label: "Assets",
    agent: "concept-to-market-agent",
    run: "babc5941",
    title: "Draft market matrix",
    detail: "Creates PDP, Amazon A+, TikTok, Meta, Google image, and email drafts without launching anything.",
  },
  {
    id: "LAB-9",
    label: "Show",
    agent: "demo-producer-agent",
    run: "60b7a99d",
    title: "Boss demo package",
    detail: "Packages the board walk, artifact trail, risk gates, and 90-second executive narrative.",
  },
];

const board = document.querySelector("#relayBoard");
const selected = document.querySelector("#selectedRun");
let activeIndex = 0;
let timer = null;

function renderBoard() {
  board.innerHTML = "";
  runs.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `relay-item${index === activeIndex ? " active" : ""}`;
    button.innerHTML = `
      <strong>${item.id}</strong>
      <span><b>${item.label}</b><br>${item.agent}</span>
      <em class="relay-status">in_review</em>
    `;
    button.addEventListener("click", () => {
      activeIndex = index;
      renderBoard();
      renderSelected();
      restartTimer();
    });
    board.appendChild(button);
  });
}

function renderSelected() {
  const item = runs[activeIndex];
  selected.innerHTML = `
    <h3>${item.title}</h3>
    <p>${item.detail}</p>
    <div class="meta">
      <span class="pill">${item.id}</span>
      <span class="pill">${item.run}</span>
      <span class="pill">artifact linked</span>
    </div>
  `;
}

function restartTimer() {
  if (timer) window.clearInterval(timer);
  timer = window.setInterval(() => {
    activeIndex = (activeIndex + 1) % runs.length;
    renderBoard();
    renderSelected();
  }, 4200);
}

renderBoard();
renderSelected();
restartTimer();
