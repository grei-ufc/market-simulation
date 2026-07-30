//
// Config
//
var width = 1000;
var height = Math.min(800, window.innerHeight);
var sub_heights = {
    topology: height * 0.7,
    timeline: height * 0.3
}
var default_etype = {
    default: 0,
    min: 0,
    max: 0,
    unit: ''
}
var topology_config = {
    // Nodes
    node_r: 6,

    // Links
    link_length: 15,  // default link length (if link.length == 0)
    link_factor: 100,  // factor for link length (if link.length > 0)

    // Force params
    force_default_charge: -50,
    force_charge: {
        pqbus: -100,
        refbus: -75
    },
    force_gravity: 0.12
}


//
// Global state :-)
//
var etypes = null;  // Entity types (will be set in setup());
var progressbar = ProgressBar();
var topology = Topology(topology_config);
var timeline = Timeline();
var svg = d3.select('#canvas').attr('width', width).attr('height', height);
// var ws = make_websocket();


//
// Functions
//
/**
 * Setup the websocket.
 */
function make_websocket() {
    var callbacks = {
        setup_topology: setup,
        update_data: update
    };

    var ws = new WebSocket('ws://' + location.host + '/websocket');
    ws.onopen = function get_topology(evt) {
        ws.send('get_topology');
    };
    ws.onmessage = function dispatch(evt) {
        var msg = JSON.parse(evt.data);
        var msg_type = callbacks[msg[0]];
        if (msg_type) {
            msg_type(msg[1]);
        }
        else {
            console.log('Unknow message type: ' + msg[0]);
        }
    };
    ws.onclose = function(evt) {
        progressbar.set_progress(0);
    }

    return ws;
}

/**
 * Create and initialize the topology graph.
 *
 * *data* is an object with three attributes:
 *
 * - ``data.etypes`` contaisn the configuration for all entity types.
 * - ``data.nodes`` is a list of node objects for the topology
 * - ``data.links`` is a list of link objects for the topology
 */
function setup(data) {
    etypes = data.etypes;  // Set global variable
    progressbar.set_progress(0);
    topology.create(data);
    timeline.init(data);
}

/**
 * Update the progress bar, topology and (if needed) the timeline
 *
 * *data* is an object with two attributes:
 *
 * - ``data.progress`` is a number with the current sim. progress in [0, 100].
 * - ``data.nodes`` is a dict/object mapping node names to a new "value".
 */
function update(data) {
    progressbar.set_progress(data.progress);
    topology.update(data);
    timeline.update(data);
}


function ProgressBar() {
    var progress_bar = d3.select('#progress');
    var progress_scale = d3.scale.linear()
        .domain([0, 100])
        .range([0, d3.select('html').style('width')]);

    return {
        set_progress: function set_progress(progress) {
            progress_bar.transition()
                .style('width', progress_scale(progress));
        }
    };
}


function Topology(conf) {
    var self = {};
    self.disable_heatmap = false;

    // Colorbar scales
    self.colorbar_gr = d3.scale.linear()
        .range([0, 120]);  // HSL 'hue' from red to green
    self.colorbar_rgr = d3.scale.linear()
        .range([-120, 120]);  // HSL 'hue' from green to red to green

    /**
    * Create and initialize the topology graph.
    *
    * *data* is an object with three attributes:
    *
    * - ``data.etypes`` contaisn the configuration for all entity types.
    * - ``data.nodes`` is a list of node objects for the topology
    * - ``data.links`` is a list of link objects for the topology
    */
    function create(data) {
        self.disable_heatmap = data.disable_heatmap;

        // Set global etypes and initialize the ring buffer.
        var etypes = data.etypes;

        // Initialize force layout
        var force = d3.layout.force()
            .size([width, sub_heights.topology])
            .links(data.links)
            .nodes(data.nodes)
            .charge(function(node) {
                var charge = conf.force_default_charge;
                if (node.type in etypes) {
                    // Update charge for type
                    var type_charge = conf.force_charge[etypes[node.type].cls];
                    if (typeof etype_charge != 'undefined') {
                        charge = type_charge;
                    }
                }
                return charge;
            })
            .gravity(conf.force_gravity)
            .linkDistance(function(link) {
                var len = conf.link_length;
                if (link.length > 0) {
                    len = link.length * conf.link_factor;
                }
                return len;
            })
            .start();

        // Add circle and line elements for the topology
        var topology = svg.append('g')
            .attr('id', 'topology');

        var links = topology.selectAll('.link')
            .data(data.links)
        links.enter().append('line')
            .attr('class', 'link')

        var nodes = topology.selectAll('.node')
            .data(data.nodes)
        nodes.enter().append('circle')
            .attr('class', function(node) {
                var cls = 'node';
                if (node.type in etypes && etypes[node.type].cls) {
                    cls += ' ' + etypes[node.type].cls;
                }
                return cls;
            })
            .attr('r', conf.node_r)
            .on('click', function(d) {
                timeline.create(d, d3.select(this));
            })
            .call(force.drag);
        nodes.append('title').text(function(node) {
            return node.name;
        });

        // Update the position of the SVG elements (circles and lines) at each
        // tick of the force simulation.
        force.on('tick', function() {
            links.attr('x1', function(d) {
                return d.source.x;
            }).attr('y1', function(d) {
                return d.source.y;
            }).attr('x2', function(d) {
                return d.target.x;
            }).attr('y2', function(d) {
                return d.target.y;
            });

            nodes.attr('cx', function(d) {
                return d.x;
            }).attr('cy', function(d) {
                return d.y;
            });
        });

        make_legend(etypes, conf);
    }

    /**
    * Create a legend for the various node types.
    *
    * *etypes* is "data.etypes" the same as in "setup()".
    */
    function make_legend(etypes, conf) {
        var node_r = conf.node_r;
        var legend = svg.append('g')
            .attr('id', 'toplogy_legend')
            .attr('class', 'legend')
            .attr('transform', 'translate(30, 30)');

        var items = d3.entries(etypes)
            .sort(function(a, b) { return a.key > b.key; });

        var li = legend.selectAll('g')
                    .data(items)
                .enter().append('g')
                    .attr('transform', function(d, i) {
                        return 'translate(0, ' + (i * node_r * 4) + ')';
                    });
        li.append('circle')
            .attr('cx', 0)
            .attr('cy', 0)
            .attr('r', node_r)
            .attr('class', function(d) { return 'node ' + d.value.cls; })
        li.append('text')
            .attr('x', node_r * 3.5)
            .attr('y', node_r)
            .text(function(d) { return d.key; });
    }

    /**
    * Update visualization with new data
    */
    function update(data) {
        if (self.disable_heatmap === true) {
            return;
        }
        // Update node data and the ring buffer.
        var node_data = data.node_data[data.node_data.length - 1];
        var nodes = svg.selectAll('#topology .node');
        nodes.data().forEach(function(node, i) {
            node.value = node_data[node.name].value;
        });

        // Update the fill color of all nodes.
        nodes.style('fill', function(node) {
            var etype = etypes[node.type];
            if (typeof etype == 'undefined') {
                return;
            }

            var min = etype.min;
            var max = etype.max;
            // Clip value to [min, max]:
            var value = Math.min(max, Math.max(min, node.value));

            if (etype.min == 0) {
                // Positive values from [0, max]
                var colorbar = self.colorbar_gr.domain([0, etype.max]);
            }
            else if (etype.max == 0) {
                // Negative values from [min, 0]
                var colorbar = self.colorbar_gr.domain([0, etype.min]);
            }
            else {
                // Values in [min, max] with their center in (min + max) / 2
                var colorbar = self.colorbar_rgr.domain([etype.min, etype.max]);
            }
            var cval = colorbar(value);

            // Flip red-green to green-red (e.g, convert '0' to '120'):
            var range_max = colorbar.range()[1];
            cval = -1 * (Math.abs(cval) - range_max);

            return 'hsl(' + cval + ', 100%, 50%)';
        });
    }

    return {
        create: create,
        update: update
    };
}


/**
 * Animated time line of a node's data.
 *
 * Inspired by http://bl.ocks.org/mbostock/1642874
 */
function Timeline() {
    var self = {};
    self.start_date = null;
    self.update_interval = null;
    self.timeline_backlog = null;
    self.time = 0;
    self.timeline_node = null;
    self.timeline_circle = null; // Highlighted circle element of the topo.
    self.backlog_data = {};
    self.timeline_buf = [];  // Buffer for the currently active timeline

    // Margin and size of the actual drawing area
    self.m = {top: 20, right: 20, bottom: 30, left: 110};
    self.w = width - self.m.left - self.m.right;
    self.h = sub_heights.timeline - self.m.top - self.m.bottom;

    // Scale to map data values to the pixel grid
    self.x = d3.time.scale().range([0, self.w]);
    self.y = d3.scale.linear().range([self.h, 0]);

    // Axes
    self.x_axis = null;  // Will be the svg element
    self.y_axis = null;  // Will be the svg element
    self.y_pos = null;  // Vertical position of the x-axis
    self.make_x_axis = d3.svg.axis().scale(self.x)
        .tickFormat(d3.time.format.multi([
            [".%L", function(d) { return d.getMilliseconds(); }],
            [":%S", function(d) { return d.getSeconds(); }],
            ["%H:%M", function(d) { return d.getMinutes(); }],
            ["%H:%M", function(d) { return d.getHours(); }],
            ["%a %d", function(d) { return d.getDay() && d.getDate() != 1; }],
            ["%b %d", function(d) { return d.getDate() != 1; }],
            ["%B", function(d) { return d.getMonth(); }],
            ["%Y", function() { return true; }]
        ]));
    self.make_y_axis = d3.svg.axis().scale(self.y).ticks(5).orient('left');

    // Function mapping data to (x, y) coordinates in the plot, set in init().
    self.make_line = null;

    /**
     * Return the domain based on the current time. This will be like
     * [current_time - backlog_size, current_time].
     */
    function get_domain() {
        var domain_left = self.time -
            (self.timeline_backlog * self.update_interval);
        var domain_right = self.time;
        return [domain_left, domain_right];
    }

    /**
     * Create the ring buffers for node data. This is done once when the
     * app starts.
     */
    function init(data) {
        self.start_date = new Date(data.start_date);
        self.update_interval = data.update_interval * 1000;  // milli seconds
        self.timeline_backlog = data.timeline_hours * 60;  // minutes
        data.nodes.forEach(function(node) {
            self.backlog_data[node.name] = RingBuffer(
                self.timeline_backlog + 1, null);
        });
        self.make_line = d3.svg.line()
            .x(function(d, i) {
                return self.x(self.time -
                    ((self.timeline_backlog - i) * self.update_interval));
            })
            .y(function(d) { return self.y(d); });
    }

    /**
     * Create axes for the timeline. This is done at every click on a node
     * in the topology graph.
     *
     * *node* is a node object from the topology.
     */
    function create(node, circle) {
        svg.selectAll('#timeline').remove();
        if (self.timeline_circle) {
            self.timeline_circle.classed('highlight', false);
        }
        if (self.timeline_node == node.name) {
            self.timeline_node = null;
            self.timeline_circle = null;
            return;
        }
        self.timeline_node = node.name;
        self.timeline_circle = circle.classed('highlight', true);

        var etype_conf = (node.type in etypes) ? etypes[node.type] :
                                                 default_etype;

        var min = etype_conf.min;
        var max = etype_conf.max;
        self.x.domain(get_domain());
        self.y.domain([min, max]);

        // Add an SVG element with the desired dimensions and margin.
        var timeline = svg.append('g')
            .attr('id', 'timeline')
            .attr('class', 'timeline')
            .attr('transform', 'translate(0, ' + sub_heights.topology + ')')
            .attr('width', self.w + self.m.left + self.m.right)
            .attr('height', self.h + self.m.top + self.m.bottom);

        // Title
        var title = node.name;
        if (!(node.type in etypes)) {
            title += ' [not configured]';
        }
        timeline.append('text')
            .attr('class', 'label')
            .attr('text-anchor', 'middle')
            .attr('x', self.m.left + self.w / 2)
            .attr('y', '1em')
            .text(title);

        var graph = timeline.append('g')
            .attr('transform',
                  'translate(' + self.m.left + ', ' + self.m.top + ')');

        // Clip path for animated timeline
        graph.append('defs').append('clipPath')
                .attr('id', 'clip')
            .append('rect')
                .attr('width', self.w)
                .attr('height', self.h);

        // Append the x-axis
        if (min == 0 || max == 0) {
            self.y_pos = 0;
        }
        else {
            // Vertically center x-axis, e.g. for node voltages.
            self.y_pos = (min + max) / 2;
        }
        self.x_axis = graph.append('g')
            .attr('class', 'x axis')
            .attr('transform', 'translate(0, ' + self.y(self.y_pos) + ')')
            .call(self.make_x_axis);

        // Append the y-axis
        self.y_axis = graph.append('g')
                .attr('class', 'y axis')
                .call(self.make_y_axis);
        self.y_axis.append('text')
                .attr('class', 'label')
                .attr('text-anchor', 'end')
                .attr('x', 0)
                .attr('dx', -60)
                .attr('y', self.h / 2)
                .attr('dy', '.32em')  // or: #y_axis -> g[2/5] -> text.dy
                .text(etype_conf.unit);

        graph.append('g')
                .attr('clip-path', 'url(#clip)')
            .append('path')
                .datum(self.backlog_data[node.name].data())
                .attr('class', 'line')
                .attr('d', self.make_line);

        tick();
    }

    /**
     * Redraw the timeline with the new data from the timeline_buf.
     */
    function tick() {
        if (self.timeline_node === null) {
            // Break the recursion
            return;
        }

        var data = self.timeline_buf;
        self.timeline_buf = [];
        var line = svg.select('#timeline .line');
        data.forEach(function(d) { line.datum().push(d); });

        // Update domains
        self.x.domain(get_domain());
        self.y.domain([Math.min(self.y_pos, d3.min(line.datum())),
                       Math.max(self.y_pos, d3.max(line.datum()))]);

        // slide the x-axis left
        self.x_axis.attr('transform', 'translate(0, ' + self.y(self.y_pos) + ')')
        self.x_axis.transition()
            .duration(1000)
            .ease("linear")
            .call(self.make_x_axis);
        self.y_axis.call(self.make_y_axis);

        // Update the line and slide it left
        var translate_x = self.x(self.time -
                ((line.datum().length - 1 )* self.update_interval));
        line.attr('d', self.make_line)
            .attr('transform', null);
        line.transition()
            .duration(1000)
            .ease('linear')
            .attr('transform', 'translate(' + translate_x + ', 0)')
            .each('end', tick);

        while (line.datum().length > (self.timeline_backlog + 1)) {
            line.datum().shift();
        }
    }

    /**
     * Update the timeline with new values.
     */
    function update(data) {
        self.time = self.start_date.getTime() + (data.time * 1000);
        // Update ring buffes with new data
        data.node_data.forEach(function(nodes) {
            d3.map(nodes).forEach(function(k, v) {
                self.backlog_data[k].push(v.value);
            });

            if (self.timeline_node !== null) {
                self.timeline_buf.push(nodes[self.timeline_node].value);
            }
        });
    }

    return {
        init: init,
        create: create,
        update: update
    };
}


/**
 * A simple ring buffer with stores at most *size* elements.
 *
 * If it reaches its capacity and another item is pushed, the oldest item is
 * dropped.
 *
 * ``data()``
 *   Return an array containing all data. The oldest item will be at position
 *   0 and the newest item on the end.
 *
 * ``push(item)``
 *   Push *item* to the buffer removing the oldest item if necessary.
 */
function RingBuffer(size, init_val) {
    var zero = 0;  // Points to element "0"
    var buffer = [];
    for (var i = 0; i < size; i ++) {
        buffer.push(init_val);
    }

    function get(key) {
        key = (size + zero + key) % size;
        return buffer[key];
    }

    return {
        data: function() {
            ret = [];
            for (var i = 0; i < buffer.length; i ++) {
                ret.push(get(i));
            }
            return ret;
        },
        push: function(item) {
            buffer[zero] = item;
            zero = (zero + 1) % size;
        }
    };
}
