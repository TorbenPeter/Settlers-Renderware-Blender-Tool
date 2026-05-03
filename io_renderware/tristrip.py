from enum import Enum

# Stripification algorithm by Petr Vaněček and Ivana Kolingerova, slightly modified
# Multi-Path Algorithm for Triangle Strips
# Proceedings of Computer Graphics International Conference, CGI, July 2004
# Basically, a greedy heuristic that distinguishes between free and connected triangles
# TODO: Could improve those strips using Tunneling

# Already sorted by priority for Node selection
class NodeGroup(Enum):
    U0 = 0
    U1 = 1
    C1 = 2
    U2 = 3
    C2 = 4
    U3 = 5
    T = 6

def is_edge_in_triangle(edge, triangle):
    return ((edge[0] == triangle[0] and edge[1] == triangle[1]) or
            (edge[0] == triangle[1] and edge[1] == triangle[2]) or
            (edge[0] == triangle[2] and edge[1] == triangle[0]))

class Node:

    def __init__(self, triangle : tuple[int, int, int]):
        self.triangle = triangle
        self.group : NodeGroup | None = None
        # neighbours are all neighbours that are still available to connect to
        # If a neighboring Node becomes unavailable, it must be removed from the set
        self.neighbours : set[Node] = set()
    
    def get_best_neighbour(self) -> "Node":

        if len(self.neighbours) == 0:
            return None

        best_neighbour = None

        # Prioritize by group
        for group in NodeGroup:
            if group == NodeGroup.T:
                return None
            for neighbour in self.neighbours:
                if neighbour.group == group:
                    if best_neighbour is None:
                        best_neighbour = neighbour

                    # If neighbour has the same rotation, take it immediately
                    common_edge_self = tuple(vertex for vertex in self.triangle if vertex in neighbour.triangle)
                    if not is_edge_in_triangle(common_edge_self, self.triangle): common_edge_self = common_edge_self[::-1]
                    common_edge_other = tuple(vertex for vertex in neighbour.triangle if vertex in self.triangle)
                    if not is_edge_in_triangle(common_edge_other, neighbour.triangle): common_edge_other = common_edge_other[::-1]

                    if common_edge_self == common_edge_other[::-1]:
                        return neighbour

            if best_neighbour is not None:
                return best_neighbour
            
        return None
    
    def connect(self) -> None:

        if self.group is None:
            return
        
        if self.group == NodeGroup.U2:
            self.group = NodeGroup.C1
        elif self.group == NodeGroup.U3:
            self.group = NodeGroup.C2
        else:
            self.group = NodeGroup.T

    def is_connected(self) -> bool:
        return self.group == NodeGroup.C1 or self.group == NodeGroup.C2 or self.group == NodeGroup.T

    def classify(self) -> None:

        number_of_neighbours = len(self.neighbours)

        if self.is_connected():
            if number_of_neighbours == 0:
                self.group = NodeGroup.T
            elif number_of_neighbours == 1:
                self.group = NodeGroup.C1
            elif number_of_neighbours == 2:
                self.group = NodeGroup.C2
            else:
                self.group = NodeGroup.T
        else:
            if number_of_neighbours == 0:
                self.group = NodeGroup.U0
            elif number_of_neighbours == 1:
                self.group = NodeGroup.U1
            elif number_of_neighbours == 2:
                self.group = NodeGroup.U2
            elif number_of_neighbours == 3:
                self.group = NodeGroup.U3
            else:
                self.group = NodeGroup.T
    
class TriangulationDualGraph:
    def __init__(self):
        self.nodes = {group: set() for group in NodeGroup}
        
    def from_triangles(self, triangles : list[tuple]) -> None:

        edges = {}
        nodes = []
        for index, triangle in enumerate(triangles):
            node = Node(triangle)
            edges[(triangle[0], triangle[1])] = index
            edges[(triangle[2], triangle[0])] = index
            edges[(triangle[1], triangle[2])] = index
            nodes.append(node)

        for edge, node_index in edges.items():
            if edge[::-1] in edges:
                nodes[node_index].neighbours.add(nodes[edges[edge[::-1]]])

        for node in nodes:
            node.classify()
            self.nodes[node.group].add(node)
    
    def insert_node(self, node: Node) -> None:
        self.nodes[node.group].add(node)

    def remove_node(self, node: Node) -> None:
        group = self.nodes[node.group]
        if node in group:
            group.remove(node)

    def update_node(self, node: Node) -> None:
        self.remove_node(node)
        node.classify()
        if node.group != NodeGroup.T:
            self.insert_node(node)
        else:
            for neighbour in node.neighbours:
                if node in neighbour.neighbours:
                    neighbour.neighbours.remove(node)
                self.update_node(neighbour)

    def connect_nodes(self, node1: Node, node2: Node) -> None:
        node1.neighbours.remove(node2)
        node2.neighbours.remove(node1)

        for node in (node1, node2):
            self.remove_node(node)
            node.connect()
            if node.group != NodeGroup.T:
                self.insert_node(node)
            else:
                for neighbour in node.neighbours:
                    if node in neighbour.neighbours:
                        neighbour.neighbours.remove(node)
                        self.update_node(neighbour)

    def get_next_node(self) -> Node | None:
        for group in NodeGroup:
            if group == NodeGroup.T:
                return None
            if self.nodes[group]:
                return self.nodes[group].pop()
        return None
    
def add_to_strips(strips : list[list[Node]], node1 : Node, node2 : Node):

    # Check whether both nodes are at the end of some strip
    if node1.is_connected() and node2.is_connected():
        # Shallow copy to change the original list during iteration
        copy = strips.copy()
        for strip in copy:
            if strip[0] == node1:
                node1_strip = strip[::-1]
                strips.remove(strip)
            elif strip[-1] == node1:
                node1_strip = strip
                strips.remove(strip)
            elif strip[0] == node2:
                node2_strip = strip
                strips.remove(strip)
            elif strip[-1] == node2:
                node2_strip = strip[::-1]
                strips.remove(strip)
        strips.append(node1_strip + node2_strip)
        return

    for strip in strips:
        if strip[0] == node1:
            strip.insert(0, node2)
            break
        elif strip[-1] == node1:
            strip.append(node2)
            break
        elif strip[0] == node2:
            strip.insert(0, node1)
            break
        elif strip[-1] == node2:
            strip.append(node1)
            break
    else:
        strips.append([node1, node2])

def avoid_loops(graph : TriangulationDualGraph, strips : list[list[Node]]):

    for strip in strips:
        start_node = strip[0]
        end_node = strip[-1]

        if start_node == end_node:
            continue

        if start_node in end_node.neighbours:
            end_node.neighbours.remove(start_node)
            graph.update_node(end_node)

        if end_node in start_node.neighbours:
            start_node.neighbours.remove(end_node)
            graph.update_node(start_node)

def build_node_strips(triangles) -> list[list[Node]]:
    strips = []
    graph = TriangulationDualGraph()
    graph.from_triangles(triangles)
    while node := graph.get_next_node():
        # (node, next_node) implicitly define an edge to be added to the strip
        next_node = node.get_best_neighbour()
        if next_node is not None:
            add_to_strips(strips, node, next_node)
            graph.connect_nodes(node, next_node)
            avoid_loops(graph, strips)
        else:
            strips.append([node])
            graph.remove_node(node)
            node.connect()
    return strips

# NOTE: There is probably optimization potential if one allows for vertex repitition
# This however would require to look ahead by 2 edges
def extract_triangle_strip(node_list):

    def add_edge_to_strip(strip, edge):
        # Edge goes forwards on even parity
        if len(strip)%2 == 0:
            if edge[0] == strip[-1]:
                strip.append(edge[1])
            else:
                strip += edge[::-1]
        # Else backwards
        else:
            if edge[1] == strip[-1]:
                strip.append(edge[0])
            else:
                strip += edge

    if len(node_list) == 0:
        return []

    if len(node_list) == 1:
        return list(node_list[0].triangle)

    triangle1 = node_list[0].triangle
    triangle2 = node_list[1].triangle
    # First node
    strip = [vertex for vertex in triangle1 if vertex not in triangle2]

    for node1, node2 in zip(node_list[:-1], node_list[1:]):
        triangle1 = node1.triangle
        triangle2 = node2.triangle
        edge = tuple(vertex for vertex in triangle1 if vertex in triangle2)
        if not is_edge_in_triangle(edge, triangle1):
            edge = edge[::-1]
        add_edge_to_strip(strip, edge)

    # Finish it up
    triangle2 = node_list[-1].triangle
    last_node = [vertex for vertex in triangle2 if vertex not in strip[-2:]].pop()
    edge = (strip[-1], last_node)
    if not is_edge_in_triangle(edge, triangle2):
        edge = edge[::-1]
    add_edge_to_strip(strip, edge)
    return strip

# Adapted from NvTriStrip
def concatenate_strips(strips):

    class OrientedStrip:

        def __init__(self, strip):
            self.strip = strip.copy()
            self.reversed = False

        def reverse(self):
            self.strip.reverse()
            if len(self.strip) & 1:
                self.reversed = not self.reversed

        def get_number_of_stitches(self, other : "OrientedStrip"):

            if len(self.strip) & 1:
                winding_penalty = 0 if self.reversed != other.reversed else 1
            else:
                winding_penalty = 0 if self.reversed == other.reversed else 1

            if self.strip[-1] == other.strip[0]:
                return 0 + winding_penalty
            else:
                return 2 + winding_penalty

        def __add__(self, other : "OrientedStrip"):

            result = OrientedStrip(self.strip)
            result.reversed = self.reversed
            num_stitches = self.get_number_of_stitches(other)

            if num_stitches >= 1:
                result.strip.append(self.strip[-1])
            if num_stitches >= 2:
                result.strip.append(other.strip[0])
            if num_stitches >= 3:
                result.strip.append(other.strip[0])

            result.strip.extend(other.strip)
            return result
        
    def get_concatenation_cost(strip1 : OrientedStrip, strip2 : OrientedStrip):
        return strip1.get_number_of_stitches(strip2)

    class MinimizeContainer:

        def __init__(self, func):
            self.best_argument1 = None
            self.best_argument2 = None
            self.best_value = None
            self.best_index = None
            self.function = func

        def consider(self, index, argument1, argument2):
            value = self.function(argument1, argument2)
            if ((self.best_value is None)
                or (value < self.best_value)):
                self.best_argument1 = argument1
                self.best_argument2 = argument2
                self.best_value = value
                self.best_index = index
                

    if len(strips) == 0:
        return []
    
    ostrips = [(OrientedStrip(strip), OrientedStrip(strip)) for strip in strips if len(strip) >= 3]
    for _, reverse_ostrip in ostrips:
        reverse_ostrip.reverse()
    
    result = ostrips.pop()[0]

    while ostrips:

        minimizer = MinimizeContainer(get_concatenation_cost)

        for index, _ in enumerate(ostrips):

            ostrip, ostrip_reverse = ostrips[index]

            minimizer.consider(index, result, ostrip)
            minimizer.consider(index, ostrip, result)
            minimizer.consider(index, result, ostrip_reverse)
            minimizer.consider(index, ostrip_reverse, result)

            if minimizer.best_value == 0:
                break

        result = minimizer.best_argument1 + minimizer.best_argument2
        del ostrips[minimizer.best_index]

    return result.strip

def stripify(triangles):
    node_strips = build_node_strips(triangles)
    strips = [extract_triangle_strip(node_strip) for node_strip in node_strips]
    return concatenate_strips(strips)