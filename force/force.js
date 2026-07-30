
var w = 1400,
    h = Math.min(800, window.innerHeight);
    fill = d3.scale.category20();

var vis = d3.select("#chart")
  .append("svg:svg")
    .attr("width", w)
    .attr("height", h);

d3.json("force.json", function(json) {
  // Initialize force layout

  var force = d3.layout.force()
      .gravity(.15)
      .charge(function(node) {
          var charge = -50;
          if (node.voltage_level == "medium voltage") {
              // Update charge for type
              var type_charge = -100;
              charge = type_charge;
          }
          return charge;
      })
      .linkDistance(function(link) {
          var len = 15;
          if (link.length > 0) {
              len = link.length * 100;
          }
          return len;
      })
      // .charge(-50)
      .nodes(json.nodes)
      .links(json.links)
      .size([w, h])
      // .gravity(0.12)
      // .linkDistance(2)
      .start();

  var link = vis.selectAll("line.link")
      .data(json.links)
      .enter().append("svg:line")
      .attr("class", "link")
      // .style("stroke-width", function(d) { return Math.sqrt(d.value); })
      .style("stroke-width", 3)
      .attr()
      .attr("x1", function(d) { return d.source.x; })
      .attr("y1", function(d) { return d.source.y; })
      .attr("x2", function(d) { return d.target.x; })
      .attr("y2", function(d) { return d.target.y; });

  var node = vis.selectAll("circle.node")
      .data(json.nodes)
      .enter().append("svg:circle")
      .attr("class", "node")
      .attr("cx", function(d) { return d.x; })
      .attr("cy", function(d) { return d.y; })
      .attr("r", 8)
      .style("fill", function(d) { return d.color; })
      .call(force.drag);

  node.append("svg:title")
      .text(function(d) { return d.name; });

  vis.style("opacity", 1e-6)
    .transition()
      .duration(100)
      .style("opacity", 1);

  force.on("tick", function() {
    link.attr("x1", function(d) { return d.source.x; })
        .attr("y1", function(d) { return d.source.y; })
        .attr("x2", function(d) { return d.target.x; })
        .attr("y2", function(d) { return d.target.y; });

    node.attr("cx", function(d) { return d.x; })
        .attr("cy", function(d) { return d.y; });
  });
});
