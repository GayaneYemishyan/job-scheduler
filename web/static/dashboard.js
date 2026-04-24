(function renderSchedulerGraph() {
  var container = document.getElementById("graph");
  var dataScript = document.getElementById("scheduler-data");
  if (!container || !dataScript) return;

  var payload;
  try {
    payload = JSON.parse(dataScript.textContent || "{}");
  } catch (error) {
    return;
  }

  // ── Colour map matching CSS variables ──
  var COLORS = {
    ready:       { fill: "#0a2040", stroke: "#4da6ff", text: "#4da6ff" },
    pending:     { fill: "#111318", stroke: "#2e3340", text: "#626880" },
    in_progress: { fill: "#3d2800", stroke: "#f5a623", text: "#f5a623" },
    done:        { fill: "#004d3e", stroke: "#00d4aa", text: "#00d4aa" },
    cancelled:   { fill: "#3d0a10", stroke: "#ff4757", text: "#ff4757" },
    delayed:     { fill: "#2a1500", stroke: "#ff6b35", text: "#ff6b35" },
    default:     { fill: "#111318", stroke: "#2e3340", text: "#626880" },
  };

  var CRITICAL_COLOR = { fill: "#2a1a00", stroke: "#f5a623", text: "#f5a623" };

  // ── Build adjacency for layout ──
  var nodes = payload.nodes || [];
  var edges = payload.edges || [];
  var criticalPath = payload.criticalPath || [];
  var criticalSet  = new Set(criticalPath);

  if (!nodes.length) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#626880;font-family:monospace;font-size:0.8rem;letter-spacing:0.1em">NO TASKS IN DAG</div>';
    return;
  }

  // ── Compute hierarchical layout (longest path layering) ──
  var nodeMap = {};
  nodes.forEach(function(n) { nodeMap[n.id] = n; });

  var inDeg = {}, succ = {}, pred = {};
  nodes.forEach(function(n) { inDeg[n.id] = 0; succ[n.id] = []; pred[n.id] = []; });
  edges.forEach(function(e) {
    var from = e[0], to = e[1];
    if (nodeMap[from] && nodeMap[to]) {
      succ[from].push(to);
      pred[to].push(from);
      inDeg[to]++;
    }
  });

  // Kahn's topo sort → longest path level
  var levels = {};
  var queue  = nodes.filter(function(n) { return inDeg[n.id] === 0; }).map(function(n){ return n.id; });
  var tempDeg = Object.assign({}, inDeg);

  queue.forEach(function(id) { levels[id] = 0; });

  var i = 0;
  while (i < queue.length) {
    var cur = queue[i++];
    succ[cur].forEach(function(s) {
      levels[s] = Math.max(levels[s] || 0, levels[cur] + 1);
      tempDeg[s]--;
      if (tempDeg[s] === 0) queue.push(s);
    });
  }

  // Any orphans
  nodes.forEach(function(n) { if (levels[n.id] === undefined) levels[n.id] = 0; });

  // Group by level
  var levelGroups = {};
  nodes.forEach(function(n) {
    var lv = levels[n.id];
    if (!levelGroups[lv]) levelGroups[lv] = [];
    levelGroups[lv].push(n.id);
  });

  var maxLevel = Math.max.apply(null, Object.keys(levelGroups).map(Number));
  var totalLevels = maxLevel + 1;

  // ── SVG dimensions & geometry ──
  var W  = container.clientWidth  || 800;
  var H  = container.clientHeight || 420;
  var R  = 38;   // node radius
  var PAD_X = R + 20;
  var PAD_Y = R + 28;

  var positions = {};
  Object.keys(levelGroups).forEach(function(lv) {
    var group = levelGroups[lv];
    var n     = group.length;
    var lvNum = parseInt(lv, 10);

    group.forEach(function(id, idx) {
      var x = PAD_X + (idx - (n - 1) / 2) * ((W - 2 * PAD_X) / Math.max(n - 1, 1));
      if (n === 1) x = W / 2;
      var y = PAD_Y + lvNum * ((H - 2 * PAD_Y) / Math.max(totalLevels - 1, 1));
      if (totalLevels === 1) y = H / 2;
      positions[id] = { x: x, y: y };
    });
  });

  // ── Build SVG ──
  var svgNS = "http://www.w3.org/2000/svg";

  function el(tag, attrs, parent) {
    var e = document.createElementNS(svgNS, tag);
    Object.keys(attrs).forEach(function(k) { e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }

  var svg = el("svg", {
    width: "100%", height: "100%",
    viewBox: "0 0 " + W + " " + H,
    xmlns: svgNS,
  });

  // Defs: arrowhead markers
  var defs = el("defs", {}, svg);

  function makeArrow(id, color) {
    var marker = el("marker", {
      id: id, markerWidth: "8", markerHeight: "8",
      refX: "6", refY: "3", orient: "auto",
    }, defs);
    el("path", { d: "M0,0 L0,6 L8,3 z", fill: color }, marker);
  }

  makeArrow("arrow-normal",   "#2e3340");
  makeArrow("arrow-critical", "#f5a623");

  // Glow filter for active nodes
  var filter = el("filter", { id: "glow", x: "-30%", y: "-30%", width: "160%", height: "160%" }, defs);
  var fe1 = el("feGaussianBlur", { stdDeviation: "4", result: "coloredBlur" }, filter);
  var feMerge = el("feMerge", {}, filter);
  el("feMergeNode", { in: "coloredBlur" }, feMerge);
  el("feMergeNode", { in: "SourceGraphic" }, feMerge);

  // ── Edges ──
  var edgeGroup = el("g", { class: "edges" }, svg);

  edges.forEach(function(e) {
    var from = e[0], to = e[1];
    var p1   = positions[from], p2 = positions[to];
    if (!p1 || !p2) return;

    var isCritical = criticalSet.has(from) && criticalSet.has(to);

    // Bezier control points
    var dx = p2.x - p1.x, dy = p2.y - p1.y;
    var dist = Math.sqrt(dx * dx + dy * dy);
    var nx = -dy / dist, ny = dx / dist;
    var bend = dist * 0.18;
    var cx = (p1.x + p2.x) / 2 + nx * bend;
    var cy = (p1.y + p2.y) / 2 + ny * bend;

    // Trim endpoints to node edge
    function trim(px, py, tx, ty, r) {
      var ddx = tx - px, ddy = ty - py, d = Math.sqrt(ddx*ddx + ddy*ddy);
      return { x: px + ddx / d * (d - r - 4), y: py + ddy / d * (d - r - 4) };
    }
    var ep = trim(cx, cy, p2.x, p2.y, R);

    el("path", {
      d:    "M" + p1.x + "," + p1.y + " Q" + cx + "," + cy + " " + ep.x + "," + ep.y,
      fill: "none",
      stroke:             isCritical ? "#f5a623" : "#2e3340",
      "stroke-width":     isCritical ? "2" : "1.5",
      "stroke-opacity":   isCritical ? "0.9" : "0.7",
      "marker-end":       isCritical ? "url(#arrow-critical)" : "url(#arrow-normal)",
    }, edgeGroup);
  });

  // ── Nodes ──
  var nodeGroup = el("g", { class: "nodes" }, svg);

  nodes.forEach(function(n) {
    var pos   = positions[n.id];
    if (!pos) return;

    var group = n.group || "default";
    var c     = criticalSet.has(n.id) ? CRITICAL_COLOR : (COLORS[group] || COLORS.default);
    var isActive = group === "in_progress" || group === "ready";

    var g = el("g", {
      transform: "translate(" + pos.x + "," + pos.y + ")",
      style: "cursor: default;",
    }, nodeGroup);

    // Optional glow ring for active tasks
    if (isActive) {
      el("circle", {
        r: R + 5, cx: "0", cy: "0",
        fill: "none",
        stroke: c.stroke,
        "stroke-width": "1",
        "stroke-opacity": "0.3",
        filter: "url(#glow)",
      }, g);
    }

    // Main circle
    el("circle", {
      r: R, cx: "0", cy: "0",
      fill:         c.fill,
      stroke:       c.stroke,
      "stroke-width": criticalSet.has(n.id) ? "2.5" : "1.5",
    }, g);

    // Task name only — centered in the circle, truncated to fit
    var label = (n.label || "").replace(/\\n.*/, "").replace(n.id, "").trim() || n.id;
    if (n.label && n.label.includes("\\n")) {
      label = n.label.split("\\n")[1] || label;
    }
    // Fallback to ID if name is empty
    if (!label) label = n.id;
    // Truncate to ~12 chars
    if (label.length > 12) label = label.slice(0, 11) + "…";

    var nameText = el("text", {
      x: "0", y: "0",
      "text-anchor": "middle",
      "dominant-baseline": "middle",
      "font-family": "'Space Mono', monospace",
      "font-size": "8.5",
      fill: c.text,
    }, g);
    nameText.textContent = label;

    // Tooltip
    var title = document.createElementNS(svgNS, "title");
    title.textContent = (n.title || n.id);
    g.appendChild(title);
  });

  container.innerHTML = "";
  container.appendChild(svg);
})();