(() => {
  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const refreshButton = document.querySelector("[data-dashboard-refresh]");
  const countdownNode = document.querySelector("[data-refresh-countdown]");
  const updatedIndicator = document.querySelector("[data-updated-indicator]");
  const isInvestorPage = document.querySelector("[data-updated-indicator]") !== null;
  const jsonDataNode = document.querySelector("[data-json-href]");
  const REFRESH_INTERVAL_MS = 30000;
  let lastUpdateTime = Date.now();
  let refreshInterval = null;
  let cachedJsonData = null;

  const updateTimestamp = () => {
    if (!countdownNode || !isInvestorPage) {
      return;
    }
    const elapsed = Math.floor((Date.now() - lastUpdateTime) / 1000);
    if (elapsed < 60) {
      countdownNode.textContent = `${elapsed}s ago`;
    } else if (elapsed < 3600) {
      countdownNode.textContent = `${Math.floor(elapsed / 60)}m ago`;
    } else {
      countdownNode.textContent = `${Math.floor(elapsed / 3600)}h ago`;
    }
  };

  const fetchStatus = async () => {
    try {
      const response = await window.fetch("/v2/dashboard/api/status", {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      if (payload?.generated_at) {
        lastUpdateTime = payload.generated_at * 1000;
        if (updatedIndicator) {
          updatedIndicator.style.display = "flex";
        }
      }
    } catch (error) {
    }
  };

  const getJsonHref = () => {
    if (jsonDataNode) {
      return jsonDataNode.getAttribute("data-json-href");
    }
    const meta = document.querySelector('meta[name="json-href"]');
    return meta ? meta.getAttribute("content") : null;
  };

  const patchDomWithJson = (newData) => {
    if (!newData || !cachedJsonData) {
      cachedJsonData = newData;
      return;
    }
    const oldData = cachedJsonData;
    cachedJsonData = newData;
    document.querySelectorAll("[data-patch-key]").forEach((el) => {
      const key = el.getAttribute("data-patch-key");
      const path = key.split(".");
      let oldVal = oldData;
      let newVal = newData;
      for (const p of path) {
        oldVal = oldVal?.[p];
        newVal = newVal?.[p];
      }
      if (oldVal !== newVal) {
        const fmt = el.getAttribute("data-patch-format");
        let displayVal = newVal;
        if (fmt === "number" && typeof newVal === "number") {
          displayVal = newVal.toFixed(3);
        } else if (fmt === "timestamp" && newVal) {
          displayVal = new Date(newVal * 1000).toLocaleString();
        }
        if (displayVal !== undefined) {
          el.textContent = String(displayVal);
          el.classList.add("patched");
          setTimeout(() => el.classList.remove("patched"), 500);
        }
      }
    });
  };

  const fetchAndPatch = async () => {
    const jsonHref = getJsonHref();
    if (!jsonHref) {
      return;
    }
    try {
      const response = await window.fetch(jsonHref, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      patchDomWithJson(payload);
      lastUpdateTime = Date.now();
      if (updatedIndicator) {
        updatedIndicator.style.display = "flex";
      }
    } catch (error) {
    }
  };

  const startIncrementalRefresh = () => {
    if (!isInvestorPage) {
      return;
    }
    if (updatedIndicator) {
      updatedIndicator.style.display = "flex";
    }
    refreshInterval = window.setInterval(() => {
      fetchStatus();
      fetchAndPatch();
      updateTimestamp();
    }, REFRESH_INTERVAL_MS);
    fetchStatus();
    fetchAndPatch();
    updateTimestamp();
  };

  if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
      if (isInvestorPage) {
        await fetchStatus();
        await fetchAndPatch();
        lastUpdateTime = Date.now();
        updateTimestamp();
      } else {
        window.location.reload();
      }
    });
  }

  const cognitivePanels = document.querySelectorAll("[data-cognitive-url]");
  cognitivePanels.forEach((panel) => {
    const url = panel.getAttribute("data-cognitive-url");
    if (!url) {
      return;
    }
    window
      .fetch(url, { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        const rows = Array.isArray(payload?.cognitive) ? payload.cognitive : [];
        if (!rows.length) {
          panel.innerHTML = '<div class="empty-state">No cognitive overlay available for this run.</div>';
          return;
        }
        panel.innerHTML = rows
          .map((row) => {
            const summary = Object.entries(row?.summary || {})
              .map(([key, value]) => `<div>${escapeHtml(key)}=${escapeHtml(value)}</div>`)
              .join("");
            return `
              <div class="timeline-item">
                <div class="timeline-meta">
                  <span>${escapeHtml(row.scope || "unknown")}</span>
                  <span>${escapeHtml(row.kind || "snapshot")}</span>
                </div>
                <div class="stack-list compact mono">${summary || "<div>no summary</div>"}</div>
              </div>
            `;
          })
          .join("");
      })
      .catch((error) => {
        panel.innerHTML = `<div class="empty-state">Cognitive overlay unavailable: ${escapeHtml(error.message || "fetch_failed")}</div>`;
      });
  });

  const rawPayloads = document.querySelectorAll("details[data-json-fetch]");
  rawPayloads.forEach((details) => {
    let loaded = false;
    details.addEventListener("toggle", () => {
      if (!details.open || loaded) {
        return;
      }
      loaded = true;
      const url = details.getAttribute("data-json-fetch");
      const node = details.querySelector(".json-block");
      if (!url || !node) {
        return;
      }
      node.textContent = "Loading raw payloads…";
      window
        .fetch(url, { headers: { Accept: "application/json" } })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          return response.json();
        })
        .then((payload) => {
          node.textContent = JSON.stringify(payload, null, 2);
        })
        .catch((error) => {
          node.textContent = `Raw payload fetch failed: ${error.message || "unknown_error"}`;
        });
    });
  });

  if (!isInvestorPage) {
    const secondsRaw = Number(document.body?.dataset?.refreshSeconds || "30");
    const refreshSeconds = Number.isFinite(secondsRaw) && secondsRaw > 0 ? secondsRaw : 30;
    let remaining = refreshSeconds;

    const renderCountdown = () => {
      if (!countdownNode) {
        return;
      }
      countdownNode.textContent = `${remaining}s`;
    };

    renderCountdown();
    window.setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        window.location.reload();
        return;
      }
      renderCountdown();
    }, 1000);
  } else {
    startIncrementalRefresh();
  }

  const graphControls = document.querySelector("[data-graph-api]");
  if (graphControls) {
    const graphApi = graphControls.getAttribute("data-graph-api");
    const neighborhoodApi = graphControls.getAttribute("data-graph-neighborhood-api");
    const graphCanvas = document.querySelector("[data-graph-canvas]");
    const graphRootSelect = document.querySelector("[data-graph-root-select]");
    const neighborhoodButton = document.querySelector("[data-graph-neighborhood]");
    const selectionNode = document.querySelector("[data-graph-selection]");
    let cy = null;
    let selectedNodeId = "";

    const renderSelection = (data) => {
      if (!selectionNode) {
        return;
      }
      if (!data) {
        selectionNode.innerHTML = '<div class="empty-state">Select a node to inspect details here.</div>';
        return;
      }
      selectionNode.innerHTML = `
        <div class="timeline-item">
          <div class="timeline-meta">
            <span>${escapeHtml(data.entity_type || "unknown")}</span>
            <span>${escapeHtml(data.tone || "neutral")}</span>
          </div>
          <strong>${escapeHtml(data.label || data.id || "node")}</strong>
          <div class="subtle">${escapeHtml(data.subtitle || "")}</div>
          <div class="stack-list compact mono">
            <div>id=${escapeHtml(data.id || "")}</div>
            <div>href=${escapeHtml(data.href || "")}</div>
          </div>
        </div>
      `;
    };

    const buildGraph = (graph) => {
      if (!graphCanvas || !window.cytoscape) {
        return;
      }
      if (cy) {
        cy.destroy();
      }
      cy = window.cytoscape({
        container: graphCanvas,
        elements: [...(graph?.nodes || []), ...(graph?.edges || [])],
        style: [
          {
            selector: "node",
            style: {
              "background-color": (ele) => {
                const tone = ele.data("tone");
                if (tone === "danger") return "#d96c6c";
                if (tone === "warning") return "#d8a95f";
                if (tone === "success") return "#5fa879";
                if (tone === "accent") return "#5f87d8";
                return "#8891a7";
              },
              label: "data(label)",
              color: "#eef3ff",
              "font-size": 10,
              "text-wrap": "wrap",
              "text-max-width": 160,
              "text-valign": "center",
              "text-halign": "center",
              width: 42,
              height: 42,
            },
          },
          {
            selector: "edge",
            style: {
              width: 2,
              "line-color": "#556079",
              "target-arrow-color": "#556079",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              label: "data(label)",
              "font-size": 8,
              color: "#aeb7ca",
            },
          },
          {
            selector: ":selected",
            style: {
              "border-width": 3,
              "border-color": "#f2d680",
            },
          },
        ],
        layout: {
          name: "breadthfirst",
          directed: true,
          padding: 20,
          spacingFactor: 1.2,
        },
      });
      cy.on("select", "node", (event) => {
        selectedNodeId = event.target.id();
        renderSelection(event.target.data());
      });
      if (cy.nodes().length) {
        cy.nodes()[0].select();
      }
    };

    const fetchGraph = (url) =>
      window
        .fetch(url, { headers: { Accept: "application/json" } })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          return response.json();
        })
        .then((payload) => {
          buildGraph(payload.graph || { nodes: [], edges: [] });
          if (graphRootSelect && Array.isArray(payload.roots)) {
            graphRootSelect.innerHTML = payload.roots
              .map(
                (item) =>
                  `<option value="${escapeHtml(item.root_run_id)}">${escapeHtml(item.title)} · ${escapeHtml(item.status)} · ${escapeHtml(item.problem_class)}</option>`
              )
              .join("");
            if (payload.selected_root_run_id) {
              graphRootSelect.value = payload.selected_root_run_id;
            }
          }
        })
        .catch((error) => {
          if (graphCanvas) {
            graphCanvas.innerHTML = `<div class="empty-state">Graph load failed: ${escapeHtml(error.message || "unknown_error")}</div>`;
          }
        });

    if (graphCanvas) {
      const seed = graphCanvas.getAttribute("data-graph-seed");
      if (seed) {
        try {
          buildGraph(JSON.parse(seed));
        } catch (_error) {
        }
      }
    }

    if (graphRootSelect && graphApi) {
      graphRootSelect.addEventListener("change", () => {
        fetchGraph(`${graphApi}?root_run_id=${encodeURIComponent(graphRootSelect.value)}`);
      });
    }

    if (neighborhoodButton && neighborhoodApi) {
      neighborhoodButton.addEventListener("click", () => {
        if (!selectedNodeId) {
          renderSelection(null);
          return;
        }
        fetchGraph(`${neighborhoodApi}?id=${encodeURIComponent(selectedNodeId)}&depth=2`);
      });
    }
  }
})();
