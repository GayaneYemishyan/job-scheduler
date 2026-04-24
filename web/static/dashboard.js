(function renderSchedulerGraph() {
  var graph = document.getElementById("graph");
  if (!graph || !window.schedulerNodes) {
    return;
  }

  var nodeData = new vis.DataSet(
    window.schedulerNodes.map(function (node) {
      var palette = {
        ready: "#3b82f6",
        pending: "#9ca3af",
        in_progress: "#e2952d",
        done: "#2a9d8f",
        cancelled: "#b02a37",
        delayed: "#ff7f50",
      };

      return {
        id: node.id,
        label: node.label,
        title: node.title,
        color: {
          background: palette[node.group] || "#9ca3af",
          border: "#111111",
        },
        font: { color: "#111111", size: 13 },
      };
    })
  );

  var edgeData = new vis.DataSet(
    window.schedulerEdges.map(function (edge) {
      return {
        from: edge[0],
        to: edge[1],
        arrows: "to",
        color: { color: "#8f8a80" },
      };
    })
  );

  var options = {
    layout: {
      hierarchical: {
        enabled: true,
        direction: "UD",
        sortMethod: "directed",
      },
    },
    physics: false,
    interaction: { hover: true },
  };

  new vis.Network(graph, { nodes: nodeData, edges: edgeData }, options);
})();
